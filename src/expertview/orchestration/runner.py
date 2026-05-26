"""LangGraph runner construction for ExpertView.

Phase 2 topology: ``START → dispatcher → mechanical → synthesizer → END``.
The dispatcher is intentionally a no-op anchor; Phase 3 rewrites its body to
emit ``Send(...)`` calls for the five-way investigator fan-out without
touching the graph shape.
"""

import os
from typing import Final

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from expertview.agents.investigators.mechanical import make_mechanical_investigator_node
from expertview.agents.llms import (
    create_embeddings,
    create_investigator_llm,
    create_synthesizer_llm,
)
from expertview.agents.synthesizer import make_synthesizer_node
from expertview.orchestration.state import ExpertViewState
from expertview.rag.domains.mechanical import load_mechanical_store

LANGSMITH_API_KEY_ENV: Final = "LANGSMITH_API_KEY"
LANGSMITH_PROJECT_ENV: Final = "LANGSMITH_PROJECT"
LANGSMITH_TRACING_ENV: Final = "LANGSMITH_TRACING"

DISPATCHER_NODE: Final = "dispatcher"
MECHANICAL_NODE: Final = "mechanical"
SYNTHESIZER_NODE: Final = "synthesizer"


def _configure_langsmith_tracing() -> None:
    api_key = os.environ.get(LANGSMITH_API_KEY_ENV)
    if api_key is None or api_key.strip() == "":
        return

    project = os.environ.get(LANGSMITH_PROJECT_ENV)
    if project is not None and project.strip() != "":
        os.environ[LANGSMITH_PROJECT_ENV] = project.strip()

    os.environ.setdefault(LANGSMITH_TRACING_ENV, "true")


async def _dispatcher_node(_state: ExpertViewState) -> dict[str, object]:
    # Phase 2 no-op anchor. Phase 3 rewrites this body to emit Send(...) calls
    # for the five-way investigator fan-out; the graph shape stays the same.
    return {}


def make_graph() -> CompiledStateGraph:
    """Compile the Phase 2 graph: dispatcher → mechanical → synthesizer."""
    _configure_langsmith_tracing()

    embeddings = create_embeddings()
    mechanical_store = load_mechanical_store(embeddings)
    investigator_llm = create_investigator_llm()
    synthesizer_llm = create_synthesizer_llm()

    mechanical_node = make_mechanical_investigator_node(mechanical_store, investigator_llm)
    synthesizer_node = make_synthesizer_node(synthesizer_llm)

    graph = StateGraph(ExpertViewState)
    graph.add_node(DISPATCHER_NODE, _dispatcher_node)
    graph.add_node(MECHANICAL_NODE, mechanical_node)
    graph.add_node(SYNTHESIZER_NODE, synthesizer_node)
    graph.add_edge(START, DISPATCHER_NODE)
    graph.add_edge(DISPATCHER_NODE, MECHANICAL_NODE)
    graph.add_edge(MECHANICAL_NODE, SYNTHESIZER_NODE)
    graph.add_edge(SYNTHESIZER_NODE, END)

    return graph.compile()
