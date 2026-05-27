# Task 1 — Run-Progress Streaming Core + Topology Helper

> **Branch suggestion**: `feature/run-progress-streaming-core`
> **Parallelism**: **Sequential.** Blocks Tasks 2 and 3 — both the Streamlit app and the live CLI mode consume this module.
> **Depends on**: Phase 5 complete (`v0.6.0-demo` tagged).

## Purpose

Build the one piece of plumbing both demo surfaces need: a surface-agnostic adapter that drives a graph run and emits incremental progress as each node finishes, plus a helper that turns the compiled graph into a labelled Mermaid topology string. Today the entry point in `cli.py` calls blocking `compiled_graph.ainvoke(...)` and renders only the final report — there is no way to show investigators "lighting up" as they complete. This task adds `orchestration/streaming.py`: a typed progress-event model, an async generator that wraps `compiled_graph.astream(...)` and yields one event per node update, and a `render_topology_mermaid(...)` function that wraps `compiled_graph.get_graph().draw_mermaid()` and maps raw node names (`dispatcher`, `spawning_join`, `mechanical`, …) to human-readable demo labels.

This task produces **no UI and no CLI changes**. It does not touch `cli.py`, does not create `src/expertview/ui/`, and does not alter the graph topology, the nodes, or `make_graph()`. It is a pure addition inside `orchestration/`, unit-tested against a fake compiled graph that yields canned stream chunks — no OpenRouter call, no LangSmith dependency.

## Why it matters

- [build_plan.md §Phase 6](../../build_plan.md) requires "a UI showing parallel execution live." Live execution is impossible on `ainvoke` (it returns once, at the end); the `astream`-based adapter is the structural prerequisite for every "live" element in the phase.
- The Phase 6 README locks the live feed to in-process `graph.astream(...)` rather than LangSmith polling. Concentrating that decision in one module means the Streamlit app (Task 2) and the live CLI (Task 3) share one tested implementation instead of two divergent async bridges.
- [architecture.md §5](../../architecture.md) keeps `orchestration/` as the owner of the graph; an `astream` wrapper and a `draw_mermaid` wrapper are graph-shaped concerns, so they belong here, not in `ui/`. This keeps `cli.py` and `ui/` both able to import the core without either importing the other.
- The phase quality gate says "the Mermaid topology diagram is visible and labels match the actual code." Generating the Mermaid string from the *actual compiled graph* (not a hand-drawn diagram) is what guarantees the labels cannot drift from the code.

## Concrete steps (what to produce)

1. **Define the progress-event shape** — add a frozen pydantic model in `evidence/models.py` (or a small dedicated model local to `orchestration/streaming.py` if it is orchestration-only state, not cross-agent data) capturing one node-completion event: the node name, a human label, a status (e.g., `started` / `completed`), and the findings count contributed so far. Keep it minimal — the surfaces decide presentation; the event only carries facts.
2. **Write the async streaming driver** — in `orchestration/streaming.py`, an `async def stream_run(compiled_graph, initial_state, config=...) -> AsyncIterator[ProgressEvent]` that calls `compiled_graph.astream(initial_state, stream_mode="updates", config=config)` and translates each per-node update chunk into a `ProgressEvent`. The driver yields events as nodes complete and yields the terminal `causal_report` (or surfaces it via a final event / return) so callers can render both the live feed and the final report from one pass.
3. **Write the topology helper** — `render_topology_mermaid(compiled_graph) -> str` wrapping `compiled_graph.get_graph().draw_mermaid()`, with a single source-of-truth mapping from the runner's node-name constants (`DISPATCHER_NODE`, `MECHANICAL_NODE`, …, imported from `orchestration/runner.py`) to demo labels. The mapping reuses the runner's exported constants so a node rename cannot silently desync the labels.
4. **Map node names to investigator labels once** — expose the node-name → label mapping (and the ordered list of investigator nodes) as module constants other surfaces import, so the Streamlit panel and the CLI table show identical labels without each re-deriving them.
5. **Unit-test against a fake compiled graph** — `tests/unit/test_streaming.py` builds a fake object whose `astream` yields canned update chunks (one per investigator, then the synthesizer) and whose `get_graph().draw_mermaid()` returns a fixed string. Assert: `stream_run` yields one `ProgressEvent` per node in completion order; the terminal report is surfaced; `render_topology_mermaid` returns a string containing every demo label and no raw node name that lacks a mapping. No real graph, no network.
6. **Verify locally**: `uv run pytest tests/unit/test_streaming.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** fixes the contract between the run and the surfaces so the panel/table code in Tasks 2 and 3 reads typed facts, not raw LangGraph chunks.
- **Step 2** is the core of the task: it converts a blocking run into an incremental event stream, which is the only thing that makes a "live" view possible.
- **Step 3** produces the topology diagram from the real graph, satisfying the gate's "labels match the actual code" clause by construction.
- **Step 4** guarantees the two surfaces show the same labels by giving them one mapping to import rather than two to keep in sync.
- **Step 5** proves the driver and the helper work without spending OpenRouter budget or depending on a live graph — fakes make the async stream deterministic and CI-safe.
- **Step 6** is the local quality gate.

## Code locations

- `src/expertview/orchestration/streaming.py` (new — progress-event driver over `astream`, topology Mermaid helper, node→label mapping constants).
- `src/expertview/evidence/models.py` (edit *if* the progress event is modelled as cross-agent data — add a frozen `ProgressEvent` model; otherwise keep the event local to `streaming.py` and leave `models.py` untouched).
- `tests/unit/test_streaming.py` (new — fake-graph unit tests for the driver and the topology helper).

## Connections

**Upstream**:

- `orchestration/runner.py` — `make_graph()` return type (`CompiledStateGraph`) and the node-name constants (`DISPATCHER_NODE`, `MECHANICAL_NODE`, `PROCESS_NODE`, `SUPPLY_CHAIN_NODE`, `ENVIRONMENTAL_NODE`, `HUMAN_FACTORS_NODE`, `SPAWNING_JOIN_NODE`, `SUB_INVESTIGATOR_NODE`, `SYNTHESIZER_NODE`) reused for the label mapping (Phase 4).
- `orchestration/state.py` — `ExpertViewState` (the shape of the initial state and the per-node patches the stream carries) (Phase 1).
- `evidence/models.py` — `CausalReport`, `Finding` (the terminal report and the findings counted per event) (Phase 1).

**Downstream**:

- [[task-2-streamlit-demo-app]] imports `stream_run` to drive the live investigator-status panel and `render_topology_mermaid` for the `st.mermaid` topology tab.
- [[task-3-cli-live-mode-and-verify]] imports `stream_run` to drive the `rich.live` incremental table.
- Phase 7's rehearsal exercises both surfaces; the streaming core is model-agnostic, so the synthesizer swap to a paid frontier model changes nothing here.
- The in-process-`astream` live-feed decision is logged in [decisions.md](../../decisions.md) when this task lands (per [CLAUDE.md workflow rule 5](../../../CLAUDE.md) — log the decision the turn it locks).

## Parallelism rationale

- This task touches only `src/expertview/orchestration/streaming.py`, `tests/unit/test_streaming.py`, and (optionally) one new model in `evidence/models.py`. None of those files is edited by Tasks 2 or 3.
- It is **sequential because it is a prerequisite**, not because it shares a surface: Tasks 2 and 3 both import this module, so it must be on `main` before either can render a live view.
- It respects [architecture.md §5](../../architecture.md)'s walls: `orchestration/` legitimately imports `evidence/models.py`, and the module stays inside `orchestration/` — it does not reach into `agents/` or `rag/`.

## Risks / constraints / assumptions

- **Constraint**: module boundaries are walls ([architecture.md §5](../../architecture.md)). `streaming.py` lives in `orchestration/` and imports only from `orchestration/` and `evidence/models.py`. It does not import `agents/`, `rag/`, `ui/`, or `cli.py`.
- **Constraint**: cross-agent data goes through pydantic models in `evidence/models.py` ([CLAUDE.md](../../../CLAUDE.md)). If the progress event is shared across module boundaries it is a pydantic model, not a raw dict; if it is orchestration-internal only, it may stay local to `streaming.py` — pick one and state it in the PR.
- **Constraint**: no LLM client is constructed here ([CLAUDE.md architecture rules](../../../CLAUDE.md)); `agents/llms.py` remains the sole construction site. The driver consumes a graph that `make_graph()` already wired.
- **Risk — `astream` chunk shape differs from expectation**: LangGraph's `stream_mode="updates"` yields `{node_name: state_patch}` dicts; the exact key/value shape must be confirmed against the installed LangGraph version, not assumed. Mitigation: the fake-graph test pins the shape the driver expects, and the executing agent confirms it against a real `make_graph()` run before opening the PR (one throwaway `astream` print is enough; it need not ship).
- **Risk — `draw_mermaid()` emits raw node names the panel cannot read**: if a node is added later without a label-mapping entry, the topology shows an internal name. Mitigation: step 5 asserts every node in the mapping appears and flags any unmapped raw node; the mapping is keyed off the runner's exported constants so a rename surfaces as an import error, not a silent mislabel.
- **Risk — terminal report not surfaced by `stream_mode="updates"`**: `updates` mode carries patches, and the synthesizer's patch is `{"causal_report": ...}`, so the report arrives as the final update — but confirm it is fully formed there rather than requiring a separate `values` pass. Mitigation: if `updates` does not carry the assembled report cleanly, the driver does one final `compiled_graph.aget_state(...)` or switches to a combined stream mode; the test asserts the report is surfaced regardless of mechanism.
- **Assumption**: `make_graph()` and the node-name constants in `orchestration/runner.py` are stable as of `v0.6.0-demo`. If a constant is renamed, this module's import breaks loudly (the intended behavior), not silently.

## Definition of done

- `orchestration/streaming.py` exists with: a typed progress-event representation, `stream_run(...)` driving `compiled_graph.astream(...)` and yielding one event per node completion plus surfacing the terminal `CausalReport`, and `render_topology_mermaid(...)` producing a labelled Mermaid string from the real compiled graph.
- The node-name → demo-label mapping is defined once (keyed off `orchestration/runner.py`'s exported constants) and importable by both surfaces.
- `tests/unit/test_streaming.py` passes against a fake compiled graph with no network and no real LLM: it asserts event count/order, terminal-report surfacing, and that the Mermaid string contains every label with no unmapped raw node name.
- The module imports nothing from `agents/`, `rag/`, `ui/`, or `cli.py`.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/run-progress-streaming-core` per [branching_strategy.md §5](../../branching_strategy.md). PR description states whether the progress event is a shared `evidence/models.py` model or orchestration-local, names the confirmed LangGraph `astream` chunk shape, and notes that the in-process-`astream` live-feed decision should be logged in [decisions.md](../../decisions.md) on merge.
