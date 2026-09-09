"""Timing-based regression guard for the five-way investigator fan-out.

Compiles the real graph with the real ``Send``-based conditional edge but
swaps the LLM clients and domain loaders for fakes that sleep for a fixed
interval. The wall-time assertion catches the failure mode the phase quality
gate cares about most: a future refactor that silently collapses the
parallel branches to sequential execution.

This test does not hit OpenRouter or load embeddings, so it runs on every
CI invocation without network or quota dependence.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime

import pytest

from expertview.evidence.models import CausalReport, Document, Incident
from expertview.orchestration.runner import INVESTIGATOR_NODES, make_graph
from expertview.orchestration.state import ExpertViewState

_FAKE_LLM_SLEEP_SECONDS = 0.5
# 1.5x the fake-LLM sleep gives true parallelism a wide margin while still
# catching a sequential collapse, which would land at ~5 * 0.5s = 2.5s.
_MAX_WALL_TIME_SECONDS = 0.75


class _FakeStore:
    def __init__(self, domain: str) -> None:
        self.domain = domain
        self._document = Document(
            id=f"{domain}-doc-001",
            content=f"Fake {domain} document for parallel-fanout test.",
            source=f"data/domains/{domain}/fake.md",
            domain=domain,
            metadata={},
        )

    def search(self, query: str, k: int = 5) -> list[Document]:
        return [self._document]


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeInvestigatorLlm:
    """Sleeps to simulate latency, then returns a domain-appropriate finding.

    Detects the calling domain by scanning the rendered prompt for the
    quoted domain marker that each investigator prompt template hardcodes
    (``"mechanical"`` / ``"process"`` / ...). Sharing one fake LLM across
    all five investigators is what lets the wall-time assertion measure the
    real fan-out instead of per-branch fixture overhead.
    """

    def __init__(self, sleep_seconds: float) -> None:
        self._sleep_seconds = sleep_seconds

    async def ainvoke(self, input: str) -> _FakeResponse:
        await asyncio.sleep(self._sleep_seconds)
        domain = self._detect_domain(input)
        body = json.dumps(
            [
                {
                    "investigator_domain": domain,
                    "claim": f"Fake {domain} finding for parallel-fanout test.",
                    "confidence": 0.5,
                    "citations": [f"{domain}-doc-001"],
                }
            ]
        )
        return _FakeResponse(body)

    @staticmethod
    def _detect_domain(prompt: str) -> str:
        for domain in INVESTIGATOR_NODES:
            if f'"{domain}"' in prompt:
                return domain
        raise AssertionError(
            "could not detect investigator domain in rendered prompt; "
            f"prompt head: {prompt[:200]!r}"
        )


# The synthesizer runs two passes: a draft CausalReport, then a grounded
# reasoning narrative. The fakes below answer them in call order.
_REASONING_NARRATIVE = {
    "verdict_reasoning": "Fake narrative for the parallel-fanout harness.",
    "alternatives_summary": "",
}


class _FakeSynthesizerLlm:
    """Answers the synthesizer's two passes in call order: draft, then narrative."""

    def __init__(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._calls = 0

    async def ainvoke(self, input: str) -> _FakeResponse:
        self._calls += 1
        if self._calls > 1:
            return _FakeResponse(json.dumps(_REASONING_NARRATIVE))
        report = {
            "incident_id": self._incident_id,
            "top_hypotheses": [
                {
                    "claim": "fake synthesizer hypothesis",
                    "supporting_findings": [
                        {
                            "investigator_domain": "mechanical",
                            "claim": "fake supporting finding",
                            "confidence": 0.5,
                            "citations": ["mechanical-doc-001"],
                        }
                    ],
                    "confidence": 0.5,
                    "domain_origin": "mechanical",
                }
            ],
            "causal_chain": [],
            "confidence_summary": "Synthesized from parallel-fanout fake LLMs.",
        }
        return _FakeResponse(json.dumps(report))


def _incident() -> Incident:
    return Incident(
        id="parallel-fanout-test-incident",
        summary="Timing regression incident for the five-way investigator fan-out.",
        observed_at=datetime(2026, 5, 24, 3, 15, tzinfo=UTC),
        symptoms=["timing symptom"],
        affected_assets=["test-asset-01"],
    )


@pytest.fixture
def patched_graph(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    incident_id = _incident().id
    fake_investigator = _FakeInvestigatorLlm(_FAKE_LLM_SLEEP_SECONDS)
    fake_synthesizer = _FakeSynthesizerLlm(incident_id)

    monkeypatch.setattr(
        "expertview.orchestration.runner.create_embeddings",
        lambda: object(),
    )
    monkeypatch.setattr(
        "expertview.orchestration.runner.create_investigator_llm",
        lambda: fake_investigator,
    )
    monkeypatch.setattr(
        "expertview.orchestration.runner.create_synthesizer_llm",
        lambda: fake_synthesizer,
    )

    for domain in INVESTIGATOR_NODES:
        loader_name = f"load_{domain}_store"
        monkeypatch.setattr(
            f"expertview.orchestration.runner.{loader_name}",
            lambda _embeddings, _domain=domain: _FakeStore(_domain),
        )

    return make_graph()


@pytest.mark.asyncio
async def test_parallel_fanout_completes_within_parallel_wall_time_budget(
    patched_graph,  # type: ignore[no-untyped-def]
) -> None:
    incident = _incident()
    initial_state: ExpertViewState = {
        "incident": incident,
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }

    started_at = time.perf_counter()
    final_state = await patched_graph.ainvoke(initial_state)
    elapsed = time.perf_counter() - started_at

    assert elapsed < _MAX_WALL_TIME_SECONDS, (
        "Five-way investigator fan-out should run in parallel; expected < "
        f"{_MAX_WALL_TIME_SECONDS:.2f}s (1.5x {_FAKE_LLM_SLEEP_SECONDS:.2f}s), "
        f"got {elapsed:.3f}s. A sequential collapse would land at "
        f"~{5 * _FAKE_LLM_SLEEP_SECONDS:.2f}s."
    )

    findings = final_state["findings"]
    domains_found = {finding.investigator_domain for finding in findings}
    assert domains_found == set(INVESTIGATOR_NODES), (
        "Findings should cover all five investigator domains after fan-out; "
        f"got {sorted(domains_found)!r}, expected {sorted(INVESTIGATOR_NODES)!r}."
    )

    report = final_state["causal_report"]
    assert isinstance(report, CausalReport)
    assert report.incident_id == incident.id
