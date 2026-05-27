"""Surface-agnostic run-progress streaming helpers."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping
from typing import Any, Final, Literal, Protocol

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from expertview.evidence.models import CausalReport
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


class ProgressEvent(BaseModel):
    """One completed LangGraph node update for demo surfaces."""

    model_config = ConfigDict(frozen=True)

    node_name: str
    label: str
    findings_count: int = Field(ge=0)
    status: Literal["completed"] = "completed"
    causal_report: CausalReport | None = None


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

    findings_count = len(initial_state["findings"])
    async for chunk in compiled_graph.astream(
        initial_state,
        config=config,
        stream_mode="updates",
    ):
        for node_name, patch in chunk.items():
            state_patch = patch or {}
            findings_count += len(state_patch.get("findings", []))
            causal_report = state_patch.get("causal_report")
            yield ProgressEvent(
                node_name=node_name,
                label=NODE_LABELS[node_name],
                findings_count=findings_count,
                causal_report=causal_report if isinstance(causal_report, CausalReport) else None,
            )


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
