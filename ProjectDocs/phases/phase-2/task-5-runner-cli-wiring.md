# Task 5 — Runner Wiring + CLI + End-to-End /verify

> **Branch suggestion**: `feature/phase-2-wiring`
> **Parallelism**: **Sequential (final merge point).**
> **Depends on**: Tasks 1, 2, 3, 4 all merged to `main`. Phase 1's Task 5 (the placeholder runner skeleton) must also be on `main`.

## Purpose

Replace Phase 1's placeholder node with the real `dispatcher → mechanical → synthesizer` graph, add the `python -m expertview.cli demo` entry point that drives a `CausalReport` end-to-end from the rehearsed CNC incident YAML, and run `/verify` to confirm the Phase 2 quality gate passes against the real OpenRouter API and a real LangSmith trace.

This is the **first end-to-end execution in the project's history**. Everything before this was contracts and stubs.

## Why it matters

- The Phase 2 quality gate [(build_plan.md)](../../build_plan.md) is exactly the artifact this task produces: "the CLI command runs against the rehearsed incident, prints a coherent causal report with at least one citation back to the corpus, and a LangSmith trace appears in the project dashboard showing every node + LLM call."
- The CLI's existence is what makes every subsequent phase demoable. Phase 3's parallelism, Phase 4's spawn, Phase 5's convergence, Phase 6's UI, Phase 7's rehearsals all build on this entry point.
- `make_graph()` is the wiring **single point of truth** — Phase 3 extends it with four more investigators, Phase 4 adds the conditional spawn edge, Phase 5 enhances the synthesizer's input. Getting the wiring shape right here saves four touches downstream.

## Concrete steps (what to produce)

1. **Replace the body of `src/expertview/orchestration/runner.py`** — rewrite `make_graph()` to compile the real Phase 2 topology:
   - Build the mechanical `KnowledgeStore` once at graph-build time via Task 2's loader (`load_mechanical_store()`).
   - Build the investigator LLM once via `create_investigator_llm()`.
   - Build the synthesizer LLM once via `create_synthesizer_llm()`.
   - Construct the mechanical investigator node via Task 3's factory, binding the store + investigator LLM.
   - Construct the synthesizer node via Task 4's factory, binding the synthesizer LLM.
   - Add a thin `dispatcher` node that is a no-op for Phase 2 (returns `{}`) — its purpose is to be the fan-out point Phase 3 will repurpose with the `Send` API. Wiring it now means Phase 3 doesn't touch the graph shape, only the dispatcher body.
   - Wire `START → dispatcher → mechanical → synthesizer → END`.
   - Keep `_configure_langsmith_tracing()` intact — Phase 1's no-op-without-keys behavior remains correct.
2. **Create `src/expertview/cli.py`** exposing a `demo` command runnable via `python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml`:
   - Load the YAML and validate against `Incident`.
   - Compile the graph via `make_graph()`.
   - Build the initial `ExpertViewState` (incident populated; lists empty; `causal_report=None`).
   - Invoke the graph (`await compiled_graph.ainvoke(initial_state)`).
   - Render the resulting `CausalReport` to stdout — use `rich` (already a dep) for readable formatting: top hypotheses with confidence bars, causal chain, confidence summary, and the citations.
   - If LangSmith tracing is enabled, print the trace URL after the report (LangSmith exposes the run URL on the result; fall back to a print noting tracing is disabled if not).
   - Exit non-zero on any pydantic validation failure or LLM error so `/verify` and CI catch regressions.
3. **Add `pyproject.toml` script entry** `expertview = "expertview.cli:main"` (or equivalent) so the CLI is also runnable as `uv run expertview demo --incident ...`. This is a one-line `[project.scripts]` addition — *not* a dependency addition, so it doesn't require a `decisions.md` entry under [CLAUDE.md hard rules](../../../CLAUDE.md). Confirm with the user if uncertain.
4. **Add an end-to-end integration test** in `tests/integration/test_demo_end_to_end.py` that:
   - Skips gracefully if `OPENROUTER_API_KEY` is not set (mirrors the pattern in Phase 1's `tests/integration/test_provider_keys.py`).
   - Invokes the compiled graph against the CNC incident YAML.
   - Asserts the returned state's `causal_report` is a populated `CausalReport` whose `incident_id` matches, `top_hypotheses` is non-empty, and at least one `Hypothesis.supporting_findings[*].citations` is non-empty (the "citation back to the corpus" gate).
5. **Run `/verify`** to drive the CLI end-to-end on the actual machine with real OpenRouter + real LangSmith credentials. The /verify run is the **definition of done** for this task — not a code change, but a recorded successful execution.
   - Confirm a coherent CausalReport prints to stdout.
   - Confirm a LangSmith trace URL prints and the trace is visible in the dashboard showing every node + every LLM call.
   - Confirm citations in the report reference real document `source`s from `data/domains/mechanical/`.
6. **Verify locally**: `uv run pytest` green (the integration test runs only when the OpenRouter key is present; CI runs it); `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** replaces the placeholder graph with the real Phase 2 graph. The dispatcher-as-no-op-anchor is a small bet that pays off in Phase 3 (where it becomes the `Send` API fan-out point) and Phase 4 (where the conditional spawn edge attaches near it).
- **Step 2** is the demo's front door. Every audience interaction with ExpertView goes through this command in Phase 2; later phases swap or layer over it.
- **Step 3** makes the `uv run expertview demo` form work alongside `python -m expertview.cli demo`. Small ergonomics with a large impact on the README and the at-event rehearsal.
- **Step 4** is the automated regression gate. CI catches structural breakage; the `/verify` run catches semantic breakage (citations missing, report incoherent).
- **Step 5** is the **phase gate**. Without a successful `/verify` run, Phase 2 is not done regardless of green tests.
- **Step 6** is the local quality gate for code-level checks.

## Code locations

- `src/expertview/orchestration/runner.py` (modify — replace placeholder body).
- `src/expertview/cli.py` (new).
- `pyproject.toml` (modify — add `[project.scripts]` entry; no dependency changes).
- `tests/integration/test_demo_end_to_end.py` (new).

## Connections

**Upstream**:

- [[task-1-data-authoring]] — corpus files + CNC incident YAML.
- [[task-2-mechanical-rag-loader]] — `load_mechanical_store()`.
- [[task-3-mechanical-investigator]] — `make_mechanical_investigator_node()`.
- [[task-4-synthesizer]] — `make_synthesizer_node()`.
- Phase 1: `agents/llms.create_investigator_llm/create_synthesizer_llm`, `orchestration/state.ExpertViewState`, `evidence/models` (Incident, CausalReport).

**Downstream**:

- Phase 3 modifies the `dispatcher` node body to emit five `Send(...)` calls (one per domain investigator). The graph shape — START → dispatcher → investigators → synthesizer → END — stays put; only the dispatcher's body and the investigator set expand.
- Phase 4 attaches a `conditional_edges` call near the dispatcher / investigator boundary for dynamic spawn.
- Phase 5 enhances the synthesizer prompt and may introduce a pre-synthesizer convergence node; the wiring file changes are local.
- Phase 6's Streamlit UI imports `make_graph()` and the same incident-loading helper from `cli.py`; the CLI stays as the `--cli` Plan B mode per [decisions.md](../../decisions.md).
- Phase 7's retry/backoff wraps the LLM calls inside `agents/llms.py`; this wiring file doesn't change.

## Risks / constraints / assumptions

- **Constraint**: per [CLAUDE.md hard rules](../../../CLAUDE.md), **no dependency additions** without a `decisions.md` entry. `rich`, `pyyaml`, `langgraph`, `langchain-openai` are already in `pyproject.toml`; the script entry is a metadata change, not a dependency change.
- **Constraint**: the synthesizer node returns only `{"causal_report": ...}`. The CLI reads it from state — do not have the CLI write to disk or call the synthesizer directly.
- **Risk**: the OpenRouter free-tier quota gets exhausted during iteration. Mitigation: prefer the unit tests for inner-loop iteration; reserve full `/verify` runs for when the report shape is plausible. Track usage in the OpenRouter dashboard per [decisions.md](../../decisions.md).
- **Risk**: the LLM produces a report without citations, failing the quality gate. Mitigation: tighten the investigator prompt (Task 3) before re-running; if the synthesizer is dropping citations from coherent findings, tighten Task 4's prompt. Both are prompt iterations, not wiring changes.
- **Risk**: LangSmith tracing silently fails to activate. Mitigation: the CLI prints the trace URL on success or a clear "tracing disabled" notice if the env var is absent — no silent failure.
- **Risk**: `/verify` reveals semantic incoherence (the report cites the right doc but the hypothesis is nonsense). Mitigation: this is a prompt iteration loop, not a re-architecting; iterate on the investigator + synthesizer prompts and re-run `/verify` until the report reads coherently. The `EXPERTVIEW_SYNTH_MODEL=deepseek/deepseek-v4-flash:free` default keeps iteration cost at $0 per the user's [free-tier-first feedback memory](../../../CLAUDE.md).
- **Risk**: the dispatcher-as-no-op feels like dead code. Mitigation: the comment in `runner.py` should call out that Phase 3 fills the dispatcher body with `Send(...)` calls — this is intentional pre-wiring for the next phase, not over-engineering.
- **Assumption**: the executing agent will *not* attempt to wire Phase 3's parallel fan-out or Phase 4's spawning logic here. Stay within Phase 2's vertical-slice scope per [build_plan.md](../../build_plan.md).

## Definition of done

- `make_graph()` compiles a graph with the real `START → dispatcher → mechanical → synthesizer → END` topology.
- `python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml` prints a coherent `CausalReport` and a LangSmith trace URL.
- `uv run expertview demo --incident ...` works equivalently via the `[project.scripts]` entry.
- `tests/integration/test_demo_end_to_end.py` passes when `OPENROUTER_API_KEY` is set, skips cleanly when it isn't.
- **`/verify` has been run and confirms** the CausalReport is coherent, contains at least one citation back to `data/domains/mechanical/`, and the LangSmith trace is visible in the project dashboard with every node + LLM call captured.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- No `ChatOpenAI(...)` or `HuggingFaceEmbeddings(...)` constructed outside `agents/llms.py`.
- No prompt strings inlined.
- PR opened on `feature/phase-2-wiring` per [branching_strategy.md §5](../../branching_strategy.md), with the `/verify` transcript or trace URL pasted into the PR description as evidence the quality gate passed.
- Once merged, tag `v0.3.0-demo` per [branching_strategy.md §8](../../branching_strategy.md).
