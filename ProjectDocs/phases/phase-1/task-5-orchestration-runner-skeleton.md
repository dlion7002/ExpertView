# Task 5 — Orchestration Runner Skeleton

> **Branch suggestion**: `feature/orchestration-skeleton`
> **Parallelism**: **Parallelizable with Tasks 3 and 4.**
> **Depends on**: Task 2 (`orchestration/state.py` provides `ExpertViewState`).

## Purpose

Stand up the LangGraph `StateGraph` scaffolding so the Phase 1 quality-gate command — `python -c "from expertview.orchestration.runner import make_graph; make_graph()"` — compiles a real `CompiledGraph` without error. The graph contains a single placeholder node that returns an empty state patch; real investigator and synthesizer wiring is Phase 2's job.

This task is what proves the LangGraph adoption decision ([decisions.md (2026-05-25)](../../decisions.md)) actually integrates with the project layout. If the import path or the state schema is wrong, the compile call surfaces it immediately rather than during Phase 2's first investigator wire-up.

## Why it matters

- The Phase 1 quality gate ([build_plan.md](../../build_plan.md)) explicitly requires `make_graph()` to compile. This task is what satisfies that gate item.
- LangGraph is the substrate that *replaces* the earlier EvidenceBus design ([decisions.md (2026-05-25 LangGraph adoption)](../../decisions.md)). A compiling skeleton proves the substitution is real, not aspirational.
- The skeleton locks the `make_graph()` import path. Phase 2's CLI (`python -m expertview.cli demo`) and the Phase 6 Streamlit UI both call this function. Establishing the path now prevents a rename cascade later.
- LangSmith tracing setup ([architecture.md §7](../../architecture.md)) is wired here too — env-var-driven, no-op when the key is absent — so Phase 2's first end-to-end run already has tracing enabled.

## Concrete steps (what to produce)

1. **Create `src/expertview/orchestration/runner.py`** exposing a `make_graph()` function that returns a `CompiledGraph`. The graph is built with LangGraph's `StateGraph` using `ExpertViewState` from `orchestration/state.py` as the state schema. Add **one** placeholder node (e.g., a no-op that returns an empty dict patch) wired from `START` to `END` so the compile call has something to compile against. No investigator nodes, no dispatcher, no synthesizer — those are Phase 2+. The function's docstring should briefly describe the target topology (the diagram in [architecture.md §3](../../architecture.md)) so a Phase 2 implementer reads the intent without diving back into docs.
2. **Wire LangSmith tracing** at module load (or factory-call) time using the env vars from `.env.example` (Task 1) — `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT`. Tracing must be a no-op (not an error) when the keys are absent, so unit tests and fresh clones do not require them.
3. **Add a smoke test** in `tests/unit/test_runner_skeleton.py` that calls `make_graph()` and asserts it returns a `CompiledGraph` (or whatever the equivalent compiled type from LangGraph is). The test must not require any provider key — the placeholder node is pure Python, no LLM calls. This test is the local stand-in for the phase quality-gate `python -c "..."` command and runs as part of `uv run pytest`.
4. **Confirm the architecture wall**: `orchestration/runner.py` may import from `orchestration/state.py` and from `langgraph` / `langsmith`. In this skeleton it should **not** import from `agents/` or `rag/` yet — Phase 2 adds those imports when real nodes wire in. Pre-importing them now is dead weight.
5. **Verify quality gates locally**: `uv run pytest tests/unit/test_runner_skeleton.py` green; `uv run python -c "from expertview.orchestration.runner import make_graph; make_graph()"` runs cleanly; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- Step 1 produces the compiling-graph stub. Phase 2 replaces the placeholder node with the real `dispatcher → mechanical → synthesizer` chain. The function signature and import path stay stable through that replacement.
- Step 2 means Phase 2's first end-to-end run shows up in the LangSmith dashboard without any additional setup — every node and LLM call is captured per [architecture.md §7](../../architecture.md). The no-op-without-keys behavior keeps Phase 1 tests provider-key-free.
- Step 3 makes the quality-gate compile check a permanent regression test rather than a one-off shell command. Future schema changes to `ExpertViewState` that break `make_graph()` fail in `uv run pytest`.
- Step 4 keeps the dependency graph clean for Phase 2 — when investigator and synthesizer imports do land here, they replace the placeholder rather than join it.
- Step 5 is the local quality gate.

## Code locations

- `src/expertview/orchestration/runner.py` (new).
- `tests/unit/test_runner_skeleton.py` (new).

## Connections

**Upstream**:

- Imports `ExpertViewState` from Task 2's `orchestration/state.py`.
- Reads `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` env vars documented in Task 1's `.env.example`.
- Project skeleton from Task 1 must exist.

**Downstream**:

- **Phase 2** replaces the placeholder node with the real wiring: `dispatcher` node → one investigator node → `synthesizer` node. This is the *moment* the architecture's data-flow diagram ([architecture.md §4](../../architecture.md)) becomes executable.
- **Phase 2's CLI** (`cli.py`) calls `make_graph()` to obtain the runnable graph for `python -m expertview.cli demo`.
- **Phase 3** extends the dispatcher node to emit 5 `Send(...)` calls and the topology to fan out across 5 investigators.
- **Phase 4** adds the `_should_spawn(state)` conditional-edge function and the sub-investigator node.
- **Phase 6** Streamlit UI calls `compiled_graph.get_graph().draw_mermaid()` (per [decisions.md (2026-05-25 Streamlit)](../../decisions.md)) to render the topology — the function returned by `make_graph()` is what powers that.
- **Phase 7** trace export and replay path use the LangSmith tracing initialized here.

## Parallelism rationale

- Tasks 3, 4, and 5 each import only from `evidence/` (and stdlib / third-party libraries). They do not import from each other.
- The architecture rule "module boundaries are walls" ([architecture.md §5](../../architecture.md)) is what makes the fan-out safe — `orchestration/runner.py` in *this* skeleton does not depend on `agents/` or `rag/` yet (Phase 2 introduces those deps).
- A second agent can take Task 3 and a third can take Task 4 at the same time on separate `feature/*` branches. Merge order does not matter among Tasks 3/4/5.

## Risks / constraints / assumptions

- **Risk**: defining the placeholder node so loosely that Phase 2's replacement requires changing `make_graph()`'s signature. Mitigation: the public surface here is `make_graph() -> CompiledGraph` with no parameters. Phase 2 swaps the *body*, not the signature.
- **Risk**: requiring `LANGSMITH_API_KEY` to be set for `make_graph()` to even compile. That breaks the quality gate on machines without keys. Mitigation: tracing setup must be a no-op when keys are absent (step 2 explicitly).
- **Risk**: LangGraph version drift. The pinned `langgraph` version in Task 1's `pyproject.toml` governs the `StateGraph` / `Send` / `CompiledGraph` API surface; a version mismatch here will surface immediately as a compile failure. Log the resolution in [decisions.md](../../decisions.md) if a pin change is required.
- **Constraint**: LangGraph nodes are pure async functions `(State) -> dict` returning state patches ([CLAUDE.md architecture rules](../../../CLAUDE.md), [architecture.md §5](../../architecture.md)). The placeholder node must follow this signature so Phase 2 inherits the pattern.
- **Constraint**: the synthesizer is side-effect-free and the *sole* reader of the final state snapshot ([CLAUDE.md architecture rules](../../../CLAUDE.md), [architecture.md §5](../../architecture.md)). This skeleton does not include a synthesizer node, but the topology shape established here (single linear `START → placeholder → END`) must not paint Phase 2 into a corner that violates this rule.
- **Constraint**: `orchestration/runner.py` may not instantiate any LLM client. The Phase 2 nodes that the placeholder will be replaced with import their clients from `agents/llms.py` (Task 4). This skeleton imports no LLM library directly.
- **Assumption**: LangGraph's `StateGraph.compile()` accepts a TypedDict with `Annotated[list[...], operator.add]` reducer fields as defined in Task 2. If it does not, the integration constraint surfaces here — log it in [decisions.md](../../decisions.md) and adjust the state schema in Task 2 the same turn (architecture-affecting change → ask the user per [CLAUDE.md decision-making meta-rules](../../../CLAUDE.md)).

## Definition of done

- `make_graph()` exists in `orchestration/runner.py`, compiles a `StateGraph` over `ExpertViewState`, and returns a `CompiledGraph`.
- LangSmith tracing setup is wired and is a no-op when keys are absent.
- Smoke test in `tests/unit/test_runner_skeleton.py` passes without any provider key set.
- `uv run python -c "from expertview.orchestration.runner import make_graph; make_graph()"` runs cleanly — the Phase 1 quality gate's compile check.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- No imports from `agents/` or `rag/` in `runner.py` yet (Phase 2 adds those).
- PR opened on `feature/orchestration-skeleton` per [branching_strategy.md §5](../../branching_strategy.md).
