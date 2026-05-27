"""Unit tests for surface-agnostic graph streaming helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from expertview.evidence.models import CausalReport, Finding, Incident
from expertview.orchestration.runner import (
    DISPATCHER_NODE,
    MECHANICAL_NODE,
    SPAWNING_JOIN_NODE,
    SUB_INVESTIGATOR_NODE,
    SYNTHESIZER_NODE,
)
from expertview.orchestration.state import ExpertViewState
from expertview.orchestration.streaming import NODE_LABELS, render_topology_mermaid, stream_run

_OBSERVED_AT = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)


class _FakeDrawableGraph:
    def __init__(self, nodes: Mapping[str, object], mermaid: str) -> None:
        self.nodes = nodes
        self._mermaid = mermaid

    def draw_mermaid(self) -> str:
        return self._mermaid


class _FakeCompiledGraph:
    def __init__(
        self,
        updates: list[dict[str, dict[str, object] | None]] | None = None,
        nodes: Mapping[str, object] | None = None,
        mermaid: str = "graph TD;\n",
    ) -> None:
        self._updates = updates or []
        self._drawable_graph = _FakeDrawableGraph(nodes or {}, mermaid)
        self.seen_input: ExpertViewState | None = None
        self.seen_config: object | None = None
        self.seen_stream_mode: str | None = None

    async def astream(
        self,
        input: ExpertViewState,
        config: object | None = None,
        *,
        stream_mode: str,
    ) -> AsyncIterator[dict[str, dict[str, object] | None]]:
        self.seen_input = input
        self.seen_config = config
        self.seen_stream_mode = stream_mode
        for update in self._updates:
            yield update

    def get_graph(self) -> _FakeDrawableGraph:
        return self._drawable_graph


def _incident() -> Incident:
    return Incident(
        id="streaming-test-incident",
        summary="Incident for streaming adapter tests.",
        observed_at=_OBSERVED_AT,
        symptoms=["test symptom"],
        affected_assets=["asset-1"],
    )


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
        incident_id="streaming-test-incident",
        top_hypotheses=[],
        causal_chain=[],
        confidence_summary="Streaming adapter surfaced the terminal report.",
        generated_at=_OBSERVED_AT,
    )


def _initial_state() -> ExpertViewState:
    return {
        "incident": _incident(),
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }


async def _collect_events(
    graph: _FakeCompiledGraph,
    initial_state: ExpertViewState,
    config: object | None = None,
):
    return [event async for event in stream_run(graph, initial_state, config=config)]  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_stream_run_yields_events_in_node_completion_order_and_passes_config() -> None:
    report = _report()
    updates: list[dict[str, dict[str, object] | None]] = [
        {DISPATCHER_NODE: None},
        {MECHANICAL_NODE: {"findings": [_finding("mechanical", "bearing chatter")]}},
        {SPAWNING_JOIN_NODE: None},
        {
            SUB_INVESTIGATOR_NODE: {
                "findings": [
                    _finding("supply_chain", "supplier batch anomaly"),
                    _finding("supply_chain", "expedite lot missing inspection"),
                ]
            }
        },
        {SYNTHESIZER_NODE: {"causal_report": report}},
    ]
    graph = _FakeCompiledGraph(updates=updates)
    initial_state = _initial_state()
    config = {"callbacks": ["collector"]}

    events = await _collect_events(graph, initial_state, config=config)

    assert graph.seen_input is initial_state
    assert graph.seen_config is config
    assert graph.seen_stream_mode == "updates"
    assert [event.node_name for event in events] == [
        DISPATCHER_NODE,
        MECHANICAL_NODE,
        SPAWNING_JOIN_NODE,
        SUB_INVESTIGATOR_NODE,
        SYNTHESIZER_NODE,
    ]
    assert [event.label for event in events] == [
        NODE_LABELS[DISPATCHER_NODE],
        NODE_LABELS[MECHANICAL_NODE],
        NODE_LABELS[SPAWNING_JOIN_NODE],
        NODE_LABELS[SUB_INVESTIGATOR_NODE],
        NODE_LABELS[SYNTHESIZER_NODE],
    ]
    assert [event.findings_count for event in events] == [0, 1, 1, 3, 3]
    assert events[-1].causal_report == report
    assert all(event.status == "completed" for event in events)


@pytest.mark.asyncio
async def test_stream_run_counts_findings_already_present_in_initial_state() -> None:
    initial_state = _initial_state()
    initial_state["findings"] = [_finding("mechanical", "pre-existing finding")]
    graph = _FakeCompiledGraph(
        updates=[{MECHANICAL_NODE: {"findings": [_finding("mechanical", "new finding")]}}],
    )

    events = await _collect_events(graph, initial_state)

    assert events[0].findings_count == 2


def test_render_topology_mermaid_replaces_every_demo_node_label() -> None:
    nodes: dict[str, Any] = {
        "__start__": object(),
        **{node_name: object() for node_name in NODE_LABELS},
        "__end__": object(),
    }
    raw_mermaid = "\n".join(
        [
            "graph TD;",
            "\t__start__([<p>__start__</p>]):::first",
            *(f"\t{node_name}({node_name})" for node_name in NODE_LABELS),
            "\t__end__([<p>__end__</p>]):::last",
            f"\t__start__ --> {DISPATCHER_NODE};",
            f"\t{DISPATCHER_NODE} --> {SYNTHESIZER_NODE};",
            f"\t{SYNTHESIZER_NODE} --> __end__;",
        ]
    )
    graph = _FakeCompiledGraph(nodes=nodes, mermaid=raw_mermaid)

    rendered = render_topology_mermaid(graph)

    assert "Start" in rendered
    assert "End" in rendered
    for node_name, label in NODE_LABELS.items():
        assert label in rendered
        assert f"{node_name}({node_name})" not in rendered
    assert f"\t{DISPATCHER_NODE} --> {SYNTHESIZER_NODE};" in rendered


def test_render_topology_mermaid_fails_for_unmapped_non_system_node() -> None:
    graph = _FakeCompiledGraph(
        nodes={
            "__start__": object(),
            DISPATCHER_NODE: object(),
            "quality_shadow_board": object(),
            "__end__": object(),
        },
        mermaid="graph TD;",
    )

    with pytest.raises(ValueError, match="quality_shadow_board"):
        render_topology_mermaid(graph)
