"""Regression tests for Phase 4 dynamic sub-investigation routing."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from expertview.evidence.models import CausalReport, Document, Incident
from expertview.orchestration.runner import INVESTIGATOR_NODES, make_graph
from expertview.orchestration.state import ExpertViewState

_SPAWNED_CLAIM = "Supplier-history controls remained monitored for the implicated bearing lot."


class _FakeStore:
    def __init__(self, domain: str) -> None:
        self.domain = domain
        self._document = Document(
            id=f"{domain}-doc-001",
            content=f"Fake {domain} document for dynamic-spawning test.",
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
    def __init__(self, *, spawn: bool, events: list[str]) -> None:
        self._spawn = spawn
        self._events = events

    async def ainvoke(self, input: str) -> _FakeResponse:
        if "supplier-history sub-investigator" in input:
            self._events.append("sub_investigator")
            return _FakeResponse(
                json.dumps(
                    [
                        {
                            "investigator_domain": "supply_chain",
                            "claim": _SPAWNED_CLAIM,
                            "confidence": 0.78,
                            "citations": ["supply_chain-doc-001"],
                        }
                    ]
                )
            )

        domain = self._detect_domain(input)
        self._events.append(domain)
        claim = self._claim(domain)
        return _FakeResponse(
            json.dumps(
                [
                    {
                        "investigator_domain": domain,
                        "claim": claim,
                        "confidence": 0.6,
                        "citations": [f"{domain}-doc-001"],
                    }
                ]
            )
        )

    def _claim(self, domain: str) -> str:
        if domain != "mechanical":
            return f"Fake {domain} finding for dynamic-spawning test."
        if self._spawn:
            return "Warm runout growth points to bearing preload loss on spindle-04."
        return "Hydraulic clamp pressure remained inside the maintenance envelope."

    @staticmethod
    def _detect_domain(prompt: str) -> str:
        for domain in INVESTIGATOR_NODES:
            if f'"{domain}"' in prompt:
                return domain
        raise AssertionError(
            "could not detect investigator domain in rendered prompt; "
            f"prompt head: {prompt[:200]!r}"
        )


class _FakeSynthesizerLlm:
    def __init__(self, incident_id: str, events: list[str]) -> None:
        self._incident_id = incident_id
        self._events = events
        self.prompts: list[str] = []

    async def ainvoke(self, input: str) -> _FakeResponse:
        self._events.append("synthesizer")
        self.prompts.append(input)
        report = {
            "incident_id": self._incident_id,
            "top_hypotheses": [
                {
                    "id": "hyp-dynamic-spawning-test",
                    "claim": "Fake dynamic-spawning hypothesis.",
                    "supporting_findings": [
                        {
                            "investigator_domain": "mechanical",
                            "claim": "Fake supporting finding.",
                            "confidence": 0.5,
                            "citations": ["mechanical-doc-001"],
                        }
                    ],
                    "confidence": 0.5,
                    "domain_origin": "mechanical",
                }
            ],
            "causal_chain": [],
            "confidence_summary": "Synthesized from dynamic-spawning fake LLMs.",
        }
        return _FakeResponse(json.dumps(report))


def _incident() -> Incident:
    return Incident(
        id="dynamic-spawning-test-incident",
        summary="CNC line 2 produced out-of-tolerance parts after a bearing lot change.",
        observed_at=datetime(2026, 5, 24, 22, 40, tzinfo=UTC),
        symptoms=["audible bearing chatter", "dimensional drift above 0.05mm"],
        affected_assets=["cnc-line-2", "spindle-04"],
    )


def _initial_state(incident: Incident) -> ExpertViewState:
    return {
        "incident": incident,
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }


@pytest.fixture
def graph_harness(monkeypatch: pytest.MonkeyPatch):
    def build(*, spawn: bool):  # type: ignore[no-untyped-def]
        incident = _incident()
        events: list[str] = []
        fake_investigator = _FakeInvestigatorLlm(spawn=spawn, events=events)
        fake_synthesizer = _FakeSynthesizerLlm(incident.id, events)

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

        return make_graph(), incident, events, fake_synthesizer

    return build


@pytest.mark.asyncio
async def test_dynamic_spawning_runs_sub_investigator_before_synthesizer(
    graph_harness,  # type: ignore[no-untyped-def]
) -> None:
    graph, incident, events, fake_synthesizer = graph_harness(spawn=True)

    final_state = await graph.ainvoke(_initial_state(incident))

    findings = final_state["findings"]
    assert len(findings) == 6
    assert any(finding.claim == _SPAWNED_CLAIM for finding in findings)
    assert events.index("sub_investigator") < events.index("synthesizer")
    assert _SPAWNED_CLAIM in fake_synthesizer.prompts[0]

    report = final_state["causal_report"]
    assert isinstance(report, CausalReport)
    assert report.incident_id == incident.id


@pytest.mark.asyncio
async def test_dynamic_spawning_falls_through_without_bearing_anomaly(
    graph_harness,  # type: ignore[no-untyped-def]
) -> None:
    graph, incident, events, fake_synthesizer = graph_harness(spawn=False)

    final_state = await graph.ainvoke(_initial_state(incident))

    findings = final_state["findings"]
    assert len(findings) == 5
    assert not any(finding.claim == _SPAWNED_CLAIM for finding in findings)
    assert "sub_investigator" not in events
    assert "synthesizer" in events
    assert _SPAWNED_CLAIM not in fake_synthesizer.prompts[0]

    report = final_state["causal_report"]
    assert isinstance(report, CausalReport)
    assert report.incident_id == incident.id
