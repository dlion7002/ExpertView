"""End-to-end integration test for the Phase 2 vertical slice.

Compiles the real graph (real OpenRouter LLM clients, real local embeddings,
real mechanical corpus), invokes it against the rehearsed CNC incident YAML,
and asserts the resulting :class:`CausalReport` round-trips the incident id,
contains at least one hypothesis, and cites at least one document from the
mechanical corpus.

Skips cleanly when ``OPENROUTER_API_KEY`` is absent, matching the pattern in
:mod:`tests.integration.test_provider_keys`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from expertview.agents.llms import OPENROUTER_API_KEY_ENV
from expertview.evidence.models import CausalReport, Incident
from expertview.orchestration.runner import make_graph
from expertview.orchestration.state import ExpertViewState
from expertview.rag.domains.mechanical import CORPUS_DIR

_INCIDENT_PATH = Path("data/incidents/cnc_out_of_tolerance.yaml")


def _require_openrouter_key() -> None:
    value = os.environ.get(OPENROUTER_API_KEY_ENV)
    if value is None or value.strip() == "":
        pytest.skip(f"{OPENROUTER_API_KEY_ENV} is not set")


@pytest.fixture(scope="module")
def incident() -> Incident:
    raw = yaml.safe_load(_INCIDENT_PATH.read_text(encoding="utf-8"))
    return Incident.model_validate(raw)


@pytest.fixture(scope="module")
def mechanical_citation_pool() -> set[str]:
    pool: set[str] = set()
    for path in CORPUS_DIR.glob("*.md"):
        pool.add(path.stem)
        pool.add(path.as_posix())
    return pool


@pytest.fixture(scope="module")
def compiled_graph():  # type: ignore[no-untyped-def]
    _require_openrouter_key()
    return make_graph()


@pytest.mark.asyncio
async def test_demo_end_to_end_produces_cited_causal_report(
    compiled_graph,  # type: ignore[no-untyped-def]
    incident: Incident,
    mechanical_citation_pool: set[str],
) -> None:
    initial_state: ExpertViewState = {
        "incident": incident,
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }

    final_state = await compiled_graph.ainvoke(initial_state)

    report = final_state["causal_report"]
    assert isinstance(report, CausalReport)
    assert report.incident_id == incident.id
    assert report.top_hypotheses, "synthesizer must produce at least one hypothesis"

    all_citations = [
        citation
        for hypothesis in report.top_hypotheses
        for finding in hypothesis.supporting_findings
        for citation in finding.citations
    ]
    assert all_citations, "at least one supporting finding must include citations"

    grounded = [citation for citation in all_citations if citation in mechanical_citation_pool]
    assert grounded, (
        "at least one citation must resolve to a mechanical-corpus document "
        f"(got: {all_citations!r})"
    )
