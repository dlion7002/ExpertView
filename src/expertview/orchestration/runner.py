"""LangGraph runner construction for ExpertView.

Phase 3 topology::

    START → dispatcher → [mechanical | process | supply_chain |
                          environmental | human_factors] → synthesizer → END

The five-way fan-out uses LangGraph's :class:`~langgraph.types.Send` API via
a conditional edge function whose body emits one ``Send`` per investigator
domain. The investigators run as parallel branches and their ``findings``
patches merge into shared state through the ``operator.add`` reducer on
:class:`expertview.orchestration.state.ExpertViewState`.

The dispatcher node itself is a no-op anchor; the routing function attached
to its conditional edge does the fan-out work. Phase 4 will extend that
routing function with a sixth target for dynamically spawned
sub-investigations.
"""

import os
from typing import Final

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from expertview.agents.investigators.environmental import (
    make_environmental_investigator_node,
)
from expertview.agents.investigators.human_factors import (
    make_human_factors_investigator_node,
)
from expertview.agents.investigators.mechanical import make_mechanical_investigator_node
from expertview.agents.investigators.process import make_process_investigator_node
from expertview.agents.investigators.supply_chain import (
    make_supply_chain_investigator_node,
)
from expertview.agents.llms import (
    create_embeddings,
    create_investigator_llm,
    create_synthesizer_llm,
)
from expertview.agents.synthesizer import make_synthesizer_node
from expertview.orchestration.state import ExpertViewState
from expertview.rag.domains.environmental import load_environmental_store
from expertview.rag.domains.human_factors import load_human_factors_store
from expertview.rag.domains.mechanical import load_mechanical_store
from expertview.rag.domains.process import load_process_store
from expertview.rag.domains.supply_chain import load_supply_chain_store

LANGSMITH_API_KEY_ENV: Final = "LANGSMITH_API_KEY"
LANGSMITH_PROJECT_ENV: Final = "LANGSMITH_PROJECT"
LANGSMITH_TRACING_ENV: Final = "LANGSMITH_TRACING"

DISPATCHER_NODE: Final = "dispatcher"
MECHANICAL_NODE: Final = "mechanical"
PROCESS_NODE: Final = "process"
SUPPLY_CHAIN_NODE: Final = "supply_chain"
ENVIRONMENTAL_NODE: Final = "environmental"
HUMAN_FACTORS_NODE: Final = "human_factors"
SYNTHESIZER_NODE: Final = "synthesizer"

INVESTIGATOR_NODES: Final[tuple[str, ...]] = (
    MECHANICAL_NODE,
    PROCESS_NODE,
    SUPPLY_CHAIN_NODE,
    ENVIRONMENTAL_NODE,
    HUMAN_FACTORS_NODE,
)


def _configure_langsmith_tracing() -> None:
    api_key = os.environ.get(LANGSMITH_API_KEY_ENV)
    if api_key is None or api_key.strip() == "":
        return

    project = os.environ.get(LANGSMITH_PROJECT_ENV)
    if project is not None and project.strip() != "":
        os.environ[LANGSMITH_PROJECT_ENV] = project.strip()

    os.environ.setdefault(LANGSMITH_TRACING_ENV, "true")


async def _dispatcher_node(_state: ExpertViewState) -> dict[str, object]:
    # No-op anchor. The fan-out happens on the dispatcher's conditional edge
    # (``_dispatcher_fanout``) rather than in the node body so that Phase 4
    # can extend the same routing function with a spawned-subinvestigation
    # target without restructuring the graph.
    return {}


def _dispatcher_fanout(state: ExpertViewState) -> list[Send]:
    # Each investigator branch starts from the same incident and contributes
    # its findings back through the ``operator.add`` reducer on
    # ``ExpertViewState.findings``. Passing the full state keeps the
    # investigator-node signature uniform with non-fanout invocation.
    return [Send(node, state) for node in INVESTIGATOR_NODES]


def make_graph() -> CompiledStateGraph:
    """Compile the Phase 3 graph: dispatcher fans out to five investigators."""
    _configure_langsmith_tracing()

    embeddings = create_embeddings()
    investigator_llm = create_investigator_llm()
    synthesizer_llm = create_synthesizer_llm()

    mechanical_store = load_mechanical_store(embeddings)
    process_store = load_process_store(embeddings)
    supply_chain_store = load_supply_chain_store(embeddings)
    environmental_store = load_environmental_store(embeddings)
    human_factors_store = load_human_factors_store(embeddings)

    mechanical_node = make_mechanical_investigator_node(mechanical_store, investigator_llm)
    process_node = make_process_investigator_node(process_store, investigator_llm)
    supply_chain_node = make_supply_chain_investigator_node(supply_chain_store, investigator_llm)
    environmental_node = make_environmental_investigator_node(environmental_store, investigator_llm)
    human_factors_node = make_human_factors_investigator_node(human_factors_store, investigator_llm)
    synthesizer_node = make_synthesizer_node(synthesizer_llm)

    graph = StateGraph(ExpertViewState)
    graph.add_node(DISPATCHER_NODE, _dispatcher_node)
    graph.add_node(MECHANICAL_NODE, mechanical_node)
    graph.add_node(PROCESS_NODE, process_node)
    graph.add_node(SUPPLY_CHAIN_NODE, supply_chain_node)
    graph.add_node(ENVIRONMENTAL_NODE, environmental_node)
    graph.add_node(HUMAN_FACTORS_NODE, human_factors_node)
    graph.add_node(SYNTHESIZER_NODE, synthesizer_node)

    graph.add_edge(START, DISPATCHER_NODE)
    graph.add_conditional_edges(
        DISPATCHER_NODE,
        _dispatcher_fanout,
        list(INVESTIGATOR_NODES),
    )
    for investigator in INVESTIGATOR_NODES:
        graph.add_edge(investigator, SYNTHESIZER_NODE)
    graph.add_edge(SYNTHESIZER_NODE, END)

    return graph.compile()
