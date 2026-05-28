"""Surface-agnostic run-progress streaming helpers."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping
from typing import Any, Final, Literal, Protocol

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from expertview.agents.spawning import is_bearing_anomaly
from expertview.evidence.models import CausalReport, Finding
from expertview.orchestration.runner import (
    DISPATCHER_NODE,
    ENVIRONMENTAL_NODE,
    HUMAN_FACTORS_NODE,
    INVESTIGATOR_NODES,
    MECHANICAL_NODE,
    PROCESS_NODE,
    SPAWNING_JOIN_NODE,
    SUB_INVESTIGATOR_NODE,
    SUPPLY_CHAIN_NODE,
    SYNTHESIZER_NODE,
)
from expertview.orchestration.state import ExpertViewState

_SYSTEM_NODE_LABELS: Final[Mapping[str, str]] = {
    "__start__": "Start",
    "__end__": "End",
}

NODE_LABELS: Final[Mapping[str, str]] = {
    DISPATCHER_NODE: "Parallel Dispatcher",
    MECHANICAL_NODE: "Mechanical Investigator",
    PROCESS_NODE: "Process Investigator",
    SUPPLY_CHAIN_NODE: "Supply Chain Investigator",
    ENVIRONMENTAL_NODE: "Environmental Investigator",
    HUMAN_FACTORS_NODE: "Human Factors Investigator",
    SPAWNING_JOIN_NODE: "Spawn Decision",
    SUB_INVESTIGATOR_NODE: "Sub-Investigator",
    SYNTHESIZER_NODE: "Causal Synthesizer",
}

INVESTIGATOR_PROGRESS_NODES: Final[tuple[str, ...]] = INVESTIGATOR_NODES

_MERMAID_CLASS_SUFFIX = r"(?::{3}[A-Za-z0-9_-]+)?"

# Surface-agnostic live-flow status labels. Both the Streamlit app and the CLI
# render these strings directly; ``advance_status`` is their single source of
# truth for transitions, so the two surfaces never drift.
WAITING: Final = "Waiting"
ACTIVE: Final = "Active"
COMPLETE: Final = "Complete"
SKIPPED: Final = "Skipped"

_CLAIM_SUMMARY_CHARS: Final = 80


class SpawnDecision(BaseModel):
    """Outcome of the dynamic spawn predicate, attached to the join event."""

    model_config = ConfigDict(frozen=True)

    spawned: bool
    reason: str


class ProgressEvent(BaseModel):
    """One completed LangGraph node update for demo surfaces."""

    model_config = ConfigDict(frozen=True)

    node_name: str
    label: str
    findings_count: int = Field(ge=0)
    status: Literal["completed"] = "completed"
    causal_report: CausalReport | None = None
    # Additive enrichment (default-empty/None so existing callers stay valid):
    # the findings this node contributed, and — only on the spawning-join
    # event — the spawn predicate's outcome.
    findings: list[Finding] = Field(default_factory=list)
    spawn_decision: SpawnDecision | None = None


class _StreamableGraph(Protocol):
    def astream(
        self,
        input: ExpertViewState,
        config: RunnableConfig | None = None,
        *,
        stream_mode: Literal["updates"],
    ) -> AsyncIterator[Mapping[str, Mapping[str, Any] | None]]: ...


class _DrawableGraph(Protocol):
    nodes: Mapping[str, object]

    def draw_mermaid(self) -> str: ...


class _GraphWithTopology(Protocol):
    def get_graph(self) -> _DrawableGraph: ...


async def stream_run(
    compiled_graph: _StreamableGraph,
    initial_state: ExpertViewState,
    config: RunnableConfig | None = None,
) -> AsyncIterator[ProgressEvent]:
    """Yield one progress event per LangGraph update chunk."""

    accumulated: list[Finding] = list(initial_state["findings"])
    async for chunk in compiled_graph.astream(
        initial_state,
        config=config,
        stream_mode="updates",
    ):
        for node_name, patch in chunk.items():
            state_patch = patch or {}
            node_findings = list(state_patch.get("findings", []))
            accumulated.extend(node_findings)
            causal_report = state_patch.get("causal_report")
            spawn_decision = (
                _spawn_decision(accumulated) if node_name == SPAWNING_JOIN_NODE else None
            )
            yield ProgressEvent(
                node_name=node_name,
                label=NODE_LABELS[node_name],
                findings_count=len(accumulated),
                causal_report=causal_report if isinstance(causal_report, CausalReport) else None,
                findings=node_findings,
                spawn_decision=spawn_decision,
            )


def _spawn_decision(findings: list[Finding]) -> SpawnDecision:
    # Single-sourced from the runner predicate so the demo label can never
    # disagree with the routing the graph actually took.
    trigger = next((finding for finding in findings if is_bearing_anomaly(finding)), None)
    if trigger is not None:
        return SpawnDecision(
            spawned=True,
            reason=(
                "Mechanical investigator flagged a bearing anomaly "
                f'("{_summarize_claim(trigger.claim)}") — '
                "spawned a supply-chain sub-investigation."
            ),
        )
    return SpawnDecision(
        spawned=False,
        reason="No bearing anomaly in the investigator findings — proceeded directly to synthesis.",
    )


def _summarize_claim(claim: str, *, limit: int = _CLAIM_SUMMARY_CHARS) -> str:
    claim = claim.strip()
    if len(claim) <= limit:
        return claim
    return f"{claim[: limit - 1].rstrip()}…"


def initial_status() -> dict[str, str]:
    """Return the all-``Waiting`` status map for every demo node."""

    return {node_name: WAITING for node_name in NODE_LABELS}


def advance_status(status: Mapping[str, str], event: ProgressEvent) -> dict[str, str]:
    """Mark the completed node ``Complete`` and flip known successors ``Active``.

    This is the single source of the live-flow transitions consumed by both the
    Streamlit app and the CLI. It encodes the runner topology by hand and is
    presentation-only: it never affects routing.
    """

    updated = dict(status)
    updated[event.node_name] = COMPLETE

    if event.node_name == DISPATCHER_NODE:
        for node in INVESTIGATOR_NODES:
            if updated.get(node) == WAITING:
                updated[node] = ACTIVE
    elif event.node_name == SPAWNING_JOIN_NODE:
        if event.spawn_decision is not None and event.spawn_decision.spawned:
            updated[SUB_INVESTIGATOR_NODE] = ACTIVE
        else:
            updated[SUB_INVESTIGATOR_NODE] = SKIPPED
            updated[SYNTHESIZER_NODE] = ACTIVE
    elif event.node_name == SUB_INVESTIGATOR_NODE:
        updated[SYNTHESIZER_NODE] = ACTIVE

    return updated


def render_topology_mermaid(compiled_graph: _GraphWithTopology) -> str:
    """Return the compiled graph Mermaid topology with demo-readable labels."""

    graph = compiled_graph.get_graph()
    _validate_node_labels(graph.nodes)

    mermaid = graph.draw_mermaid()
    for node_name, label in {**_SYSTEM_NODE_LABELS, **NODE_LABELS}.items():
        mermaid = _replace_node_label(mermaid, node_name, label)
    return mermaid


def _validate_node_labels(nodes: Mapping[str, object]) -> None:
    unmapped = sorted(
        node_name
        for node_name in nodes
        if node_name not in NODE_LABELS and node_name not in _SYSTEM_NODE_LABELS
    )
    if unmapped:
        raise ValueError(f"Missing demo labels for graph nodes: {', '.join(unmapped)}")


def _replace_node_label(mermaid: str, node_name: str, label: str) -> str:
    escaped_node_name = re.escape(node_name)
    pattern = re.compile(
        rf"^(\s*{escaped_node_name})(\(\[?)(.*?)(\]?\){_MERMAID_CLASS_SUFFIX}\s*)$",
        re.MULTILINE,
    )
    return pattern.sub(rf"\1\2{label}\4", mermaid)
