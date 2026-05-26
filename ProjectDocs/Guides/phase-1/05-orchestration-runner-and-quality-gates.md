# Orchestration Runner And Quality Gates

## Purpose

This guide explains the Phase 1 LangGraph runner skeleton and the verification flow that proves the implemented contracts compile together. The graph does not run real investigators yet; it compiles a placeholder node over the real `ExpertViewState`.

## Flow Summary

1. Caller imports `make_graph()` from `src/expertview/orchestration/runner.py`.
2. `make_graph()` calls `_configure_langsmith_tracing()`.
3. Tracing setup checks `LANGSMITH_API_KEY`; if absent, it does nothing.
4. A `StateGraph` is built using `ExpertViewState`.
5. A no-op async placeholder node is added.
6. Edges wire `START -> placeholder -> END`.
7. `graph.compile()` returns a `CompiledStateGraph`.
8. Tests verify the graph compiles with no provider keys and that fake LangSmith env vars enable tracing without network calls.

## Relevant Files

- `src/expertview/orchestration/runner.py`: graph factory and LangSmith tracing setup.
- `src/expertview/orchestration/state.py`: state schema passed into `StateGraph`.
- `.env.example`: documents LangSmith env vars used here.
- `tests/unit/test_runner_skeleton.py`: graph compilation and tracing env tests.
- `tests/unit/test_state.py`: state shape and reducer tests that support graph construction.

## Step 1 - Graph Factory And LangSmith Setup

### Location

`src/expertview/orchestration/runner.py`

### Code

```python
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
```

### What it does

`_configure_langsmith_tracing()` checks the runtime environment. If `LANGSMITH_API_KEY` is absent or blank, the function returns without changing anything. If a key exists, it trims `LANGSMITH_PROJECT` if provided and sets `LANGSMITH_TRACING=true` only if that variable was not already set.

`_placeholder_node()` is an async LangGraph node with the intended node signature: it receives `ExpertViewState` and returns a state patch. In Phase 1, the patch is empty.

`make_graph()` builds the graph:

1. Configure tracing.
2. Create `StateGraph(ExpertViewState)`.
3. Add the placeholder node.
4. Add `START -> placeholder`.
5. Add `placeholder -> END`.
6. Compile and return a `CompiledStateGraph`.

### What it receives or depends on

- `ExpertViewState` from `orchestration/state.py`.
- LangGraph `StateGraph`, `START`, and `END`.
- Optional LangSmith environment variables from `os.environ`.

### What it produces or changes

- Produces a compiled LangGraph object.
- May set `LANGSMITH_TRACING=true` in `os.environ` when `LANGSMITH_API_KEY` exists.
- Does not instantiate LLM clients.
- Does not import RAG or agent modules yet.

### What it connects to

- `orchestration/state.py`: the state schema used by the graph.
- `.env.example`: documents the LangSmith env vars.
- Future Phase 2 graph wiring: the placeholder will be replaced by dispatcher, investigator, and synthesizer nodes.
- Future CLI/UI: should call this same `make_graph()` path.

### Why it matters

This file proves the architecture can compile with LangGraph using the actual shared state schema. It also establishes the public graph factory path that later phases should keep stable.

## Step 2 - Runner Skeleton Tests

### Location

`tests/unit/test_runner_skeleton.py`

### Code

```python
"""Smoke tests for the Phase 1 LangGraph runner skeleton."""

import os

from langgraph.graph.state import CompiledStateGraph
from pytest import MonkeyPatch

from expertview.orchestration import runner


def test_make_graph_returns_compiled_state_graph() -> None:
    compiled = runner.make_graph()

    assert isinstance(compiled, CompiledStateGraph)


def test_make_graph_compiles_without_provider_keys(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv(runner.LANGSMITH_API_KEY_ENV, raising=False)
    monkeypatch.delenv(runner.LANGSMITH_TRACING_ENV, raising=False)

    compiled = runner.make_graph()

    assert isinstance(compiled, CompiledStateGraph)
    assert runner.LANGSMITH_TRACING_ENV not in os.environ


def test_fake_langsmith_key_enables_tracing_without_network(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(runner.LANGSMITH_API_KEY_ENV, "fake-langsmith-key")
    monkeypatch.setenv(runner.LANGSMITH_PROJECT_ENV, " expertview-test ")
    monkeypatch.delenv(runner.LANGSMITH_TRACING_ENV, raising=False)

    compiled = runner.make_graph()

    assert isinstance(compiled, CompiledStateGraph)
    assert os.environ[runner.LANGSMITH_TRACING_ENV] == "true"
    assert os.environ[runner.LANGSMITH_PROJECT_ENV] == "expertview-test"
```

### What it does

The tests prove the graph factory returns a compiled LangGraph object.

The second test removes provider and tracing keys to prove `make_graph()` does not require OpenRouter or LangSmith credentials.

The third test uses a fake LangSmith key to prove tracing environment setup is local-only and trims the project name. It does not make a network call because the graph is only compiled, not invoked.

### What it connects to

- `runner.make_graph()`: the public graph construction function.
- `runner.LANGSMITH_*` constants: env var names.
- `CompiledStateGraph`: expected return type.

### Why it matters

Graph compilation is the Phase 1 integration point. These tests catch broken state schemas, LangGraph API drift, and accidental provider dependencies in the graph factory.

## Step 3 - Phase 1 Verification Flow

### Location

Repository root.

### Code

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -c "from expertview.orchestration.runner import make_graph; make_graph()"
```

### What it does

These are the Phase 1 verification commands.

- `uv run pytest`: runs import, schema, state, RAG, runner, and env-gated provider tests.
- `uv run ruff check .`: checks lint rules.
- `uv run ruff format --check .`: checks formatting.
- `uv run python -c ...`: directly verifies the public graph factory import path and compilation behavior.

### What it receives or depends on

- A uv environment with dependencies installed.
- Provider env vars only if live provider tests should run. Without keys, those integration tests skip.

### What it produces or changes

The commands produce verification output. They should not change source files when run in check mode.

### What it connects to

- `pyproject.toml`: defines pytest/ruff behavior.
- `tests/unit/*`: offline tests.
- `tests/integration/test_provider_keys.py`: provider tests that skip without keys.
- `orchestration/runner.py`: graph compile command imports this directly.

### Why it matters

This command set proves the Phase 1 skeleton is internally connected even though no real RCA workflow runs yet.

## How The Full Implemented Flow Connects

1. `pyproject.toml` makes the package importable and installs LangGraph, LangChain, pydantic, pytest, and ruff.
2. `models.py` defines the pydantic data shapes.
3. `state.py` imports those shapes into the graph state.
4. `rag/base.py` and `rag/inmemory.py` use `Document` from the model layer.
5. `agents/base.py` uses evidence models in public agent protocols.
6. `agents/llms.py` constructs provider clients from environment variables.
7. `runner.py` compiles a LangGraph graph over `ExpertViewState`.
8. Tests verify each boundary independently and the graph compile path as a whole.

## Where To Look Next

For Phase 2 implementation, start here:

- Replace `_placeholder_node` wiring in `src/expertview/orchestration/runner.py`.
- Add concrete investigator nodes under `src/expertview/agents/investigators/`.
- Add prompt files under `src/expertview/prompts/`.
- Add mechanical domain loader under `src/expertview/rag/domains/`.
- Add incident data under `data/incidents/`.
- Keep `make_graph()` as the public graph factory.
