# Phase 1 Guide Index

## Purpose

This folder explains the implemented Phase 1 flow for ExpertView. Phase 1 is the skeleton-and-contracts layer: the project can be imported, core schemas exist, the RAG protocol has a v1 in-memory implementation, agent protocols and provider factories exist, and `make_graph()` compiles a LangGraph skeleton.

These guides are written as context for a teaching model. They describe how the implemented files connect, where data starts, where it moves next, and which file to inspect when extending the system later.

## Current Phase 1 Shape

1. Project configuration and package layout make `expertview` importable.
2. Pydantic evidence models define every cross-agent payload.
3. `ExpertViewState` defines the shared LangGraph state and reducer behavior.
4. RAG code exposes a `KnowledgeStore` protocol and a LangChain-backed in-memory store.
5. Agent code exposes `Investigator` and `Synthesizer` protocols plus the single LLM/retrieval client factory.
6. Orchestration code compiles a placeholder LangGraph graph over `ExpertViewState`.
7. Tests lock importability, schema round trips, reducer annotations, RAG translation, provider factory connectivity, and graph compilation.

## Reading Order

- `01-bootstrap-and-layout.md`: package, config, env vars, data placeholders, and initial smoke test.
- `02-evidence-models-and-state.md`: pydantic models and `ExpertViewState` reducers.
- `03-rag-knowledge-store.md`: `KnowledgeStore`, `InMemoryKnowledgeStore`, and LangChain-to-pydantic document translation.
- `04-agent-protocols-and-llm-factory.md`: agent protocols, provider constructors, model IDs, env selection, and live provider smoke tests.
- `05-orchestration-runner-and-quality-gates.md`: `make_graph()`, LangSmith tracing setup, graph compilation, and Phase 1 verification path.

## Relevant Files by Layer

- `pyproject.toml`: dependency, script, ruff, and pytest configuration.
- `.python-version`: uv interpreter target.
- `.env.example`: provider and tracing environment contract.
- `.gitignore`: local artifact and secret hygiene.
- `data/domains/*/.gitkeep`, `data/incidents/.gitkeep`: placeholder data layout for later phases.
- `src/expertview/evidence/models.py`: immutable pydantic cross-agent models.
- `src/expertview/orchestration/state.py`: `ExpertViewState` shared state schema.
- `src/expertview/rag/base.py`: `KnowledgeStore` protocol.
- `src/expertview/rag/inmemory.py`: v1 LangChain `InMemoryVectorStore` wrapper.
- `src/expertview/agents/base.py`: `Investigator` and `Synthesizer` protocols.
- `src/expertview/agents/llms.py`: only legal LLM, embedding, and reranker construction site.
- `src/expertview/orchestration/runner.py`: LangGraph skeleton factory.
- `tests/unit/*`: offline contract and skeleton tests.
- `tests/integration/test_provider_keys.py`: env-gated live provider checks.

## Phase 1 Flow Summary

The implemented flow starts with repository configuration. `pyproject.toml` tells uv how to install the package and tells pytest/ruff how to validate it. The `src/expertview` package is importable, and the empty package folders mirror the architecture boundaries that later phases will fill.

The first real data contract is in `src/expertview/evidence/models.py`. Those pydantic models are then imported by `src/expertview/orchestration/state.py`, where `ExpertViewState` defines the LangGraph state. List fields on that state use `operator.add` reducers so later parallel investigator branches can merge findings and hypotheses instead of overwriting each other.

The RAG layer depends on the evidence `Document` model. `src/expertview/rag/base.py` exposes the protocol investigators will use, and `src/expertview/rag/inmemory.py` wraps LangChain's vector store while translating back into ExpertView's pydantic `Document`.

The agent layer also depends on the evidence models. `src/expertview/agents/base.py` defines what investigators and synthesizers must implement later. `src/expertview/agents/llms.py` constructs all model clients and retrieval clients, using environment variables from `.env.example`.

Finally, `src/expertview/orchestration/runner.py` imports `ExpertViewState`, creates a LangGraph `StateGraph`, wires one no-op placeholder node from `START` to `END`, configures LangSmith tracing when its env var is available, and returns a compiled graph. Phase 2 will replace the placeholder body with real dispatcher, investigator, and synthesizer nodes while keeping the `make_graph()` import path stable.

## Where to Extend After Phase 1

- Add concrete investigator nodes under `src/expertview/agents/investigators/`.
- Add prompt files under `src/expertview/prompts/`; do not inline prompts in agent code.
- Add domain loaders under `src/expertview/rag/domains/` that return `KnowledgeStore` implementations.
- Replace the placeholder graph wiring in `src/expertview/orchestration/runner.py`.
- Keep new cross-agent fields in `src/expertview/evidence/models.py` and update `ExpertViewState` only when the graph needs new shared state.
