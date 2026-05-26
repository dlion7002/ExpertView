"""LangGraph runner construction for ExpertView."""

import os
from typing import Final

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from expertview.orchestration.state import ExpertViewState

LANGSMITH_API_KEY_ENV: Final = "LANGSMITH_API_KEY"
LANGSMITH_PROJECT_ENV: Final = "LANGSMITH_PROJECT"
LANGSMITH_TRACING_ENV: Final = "LANGSMITH_TRACING"

_PLACEHOLDER_NODE: Final = "placeholder"


def _configure_langsmith_tracing() -> None:
    api_key = os.environ.get(LANGSMITH_API_KEY_ENV)
    if api_key is None or api_key.strip() == "":
        return

    project = os.environ.get(LANGSMITH_PROJECT_ENV)
    if project is not None and project.strip() != "":
        os.environ[LANGSMITH_PROJECT_ENV] = project.strip()

    os.environ.setdefault(LANGSMITH_TRACING_ENV, "true")


async def _placeholder_node(_state: ExpertViewState) -> dict[str, object]:
    return {}


def make_graph() -> CompiledStateGraph:
    """Build the Phase 1 graph skeleton.

    The target topology is the architecture's eventual fan-out/fan-in shape:
    dispatcher -> parallel domain investigators -> optional sub-investigations
    -> synthesizer. Phase 1 compiles only a single no-op node so Phase 2 can
    replace the body without changing this public import path.
    """
    _configure_langsmith_tracing()

    graph = StateGraph(ExpertViewState)
    graph.add_node(_PLACEHOLDER_NODE, _placeholder_node)
    graph.add_edge(START, _PLACEHOLDER_NODE)
    graph.add_edge(_PLACEHOLDER_NODE, END)

    return graph.compile()
