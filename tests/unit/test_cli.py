"""Unit tests for the CLI demo command — focused on the live (`--live`) path.

No network: the live path is driven against a fake compiled graph whose
``astream`` yields hard-coded update chunks (same shape as the streaming-core
tests). The blocking non-live path is covered by the end-to-end integration test.
"""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from rich.console import Console

from expertview.cli import _build_parser, _status_table, _stream_demo_live
from expertview.evidence.models import CausalReport, Finding, Hypothesis, Incident
from expertview.orchestration.runner import (
    DISPATCHER_NODE,
    MECHANICAL_NODE,
    SPAWNING_JOIN_NODE,
    SUB_INVESTIGATOR_NODE,
    SYNTHESIZER_NODE,
)
from expertview.orchestration.state import ExpertViewState
from expertview.orchestration.streaming import NODE_LABELS

_OBSERVED_AT = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)


class _FakeCompiledGraph:
    """Minimal graph exposing the ``astream`` surface ``stream_run`` consumes."""

    def __init__(self, updates: list[dict[str, dict[str, object] | None]]) -> None:
        self._updates = updates

    async def astream(
        self,
        input: ExpertViewState,
        config: object | None = None,
        *,
        stream_mode: str,
    ) -> AsyncIterator[dict[str, dict[str, object] | None]]:
        for update in self._updates:
            yield update


def _finding(domain: str, claim: str) -> Finding:
    return Finding(
        investigator_domain=domain,
        claim=claim,
        confidence=0.7,
        citations=[f"{domain}-doc-001"],
        raised_at=_OBSERVED_AT,
    )


def _report() -> CausalReport:
    return CausalReport(
        incident_id="cli-live-test-incident",
        top_hypotheses=[
            Hypothesis(
                claim="Spindle bearing wear drove the out-of-tolerance bore.",
                confidence=0.81,
                domain_origin="mechanical",
                supporting_findings=[_finding("mechanical", "bearing chatter")],
            )
        ],
        causal_chain=[],
        confidence_summary="Mechanical wear is the dominant cause.",
        generated_at=_OBSERVED_AT,
    )


def _incident() -> Incident:
    return Incident(
        id="cli-live-test-incident",
        summary="Incident for CLI live-path tests.",
        observed_at=_OBSERVED_AT,
        symptoms=["test symptom"],
        affected_assets=["asset-1"],
    )


def _initial_state() -> ExpertViewState:
    return {
        "incident": _incident(),
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }


def test_demo_subparser_accepts_live_flag() -> None:
    parser = _build_parser()

    with_flag = parser.parse_args(["demo", "--incident", "x.yaml", "--live"])
    without_flag = parser.parse_args(["demo", "--incident", "x.yaml"])

    assert with_flag.live is True
    assert without_flag.live is False


@pytest.mark.asyncio
async def test_live_path_returns_terminal_report_from_fake_stream() -> None:
    report = _report()
    updates: list[dict[str, dict[str, object] | None]] = [
        {DISPATCHER_NODE: None},
        {MECHANICAL_NODE: {"findings": [_finding("mechanical", "bearing chatter")]}},
        {SPAWNING_JOIN_NODE: None},
        {SUB_INVESTIGATOR_NODE: {"findings": [_finding("supply_chain", "batch anomaly")]}},
        {SYNTHESIZER_NODE: {"causal_report": report}},
    ]
    graph = _FakeCompiledGraph(updates)
    console = Console(file=io.StringIO(), width=100)

    result = await _stream_demo_live(graph, _initial_state(), {}, console)

    assert result == report


def test_status_table_marks_completed_nodes() -> None:
    status_by_node = {node_name: "Waiting" for node_name in NODE_LABELS}
    status_by_node[MECHANICAL_NODE] = "Complete"

    console = Console(record=True, width=100)
    console.print(_status_table(status_by_node, findings_count=3))
    rendered = console.export_text()

    assert NODE_LABELS[MECHANICAL_NODE] in rendered
    assert NODE_LABELS[SYNTHESIZER_NODE] in rendered
    assert "3 findings" in rendered
