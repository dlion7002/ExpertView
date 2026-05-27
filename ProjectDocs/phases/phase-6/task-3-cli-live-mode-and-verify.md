# Task 3 — Live CLI Mode + Cross-Surface `/verify`

> **Branch suggestion**: `feature/phase-6-cli-live-and-verify`
> **Parallelism**: **Sequential.** Final merge point of Phase 6. The CLI code depends only on Task 1, but the cross-surface `/verify` that closes this task — and the phase — requires Task 2's Streamlit app merged.
> **Depends on**: Task 1 merged (`orchestration/streaming.py` exports `stream_run`) and Task 2 merged (the Streamlit app is on `main`, so the watched-demo quality gate can be exercised).

## Purpose

Give the CLI a live view so the rich-terminal Plan B mirrors the Streamlit surface, then run the cross-surface `/verify` that is the phase quality gate. Today `cli.py demo` calls blocking `ainvoke` and prints only the final report. This task adds a live mode — a `rich.live`-driven incremental table that lights up each investigator as its node completes, driven by Task 1's `stream_run(...)` — so the venue-failure fallback shows the same parallel-execution story the Streamlit app does, not just the end result. Then it runs the full `/verify`: a third party watches the Streamlit demo and describes what is happening unprompted, and the live CLI is confirmed as the working Plan B.

This task edits `cli.py` only (plus any thin CLI test). It does **not** modify the Streamlit app, the streaming core, the graph, the nodes, or the convergence math. The existing final-report rendering in `cli.py` stays; the live mode is additive.

## Why it matters

- [build_plan.md §Phase 6](../../build_plan.md) lists "a `--cli` mode with `rich` live tables … kept wired as Plan B" among the phase outputs, and [decisions.md (2026-05-25)](../../decisions.md) locks the CLI rich-live mode as the venue-laptop fallback if Streamlit misbehaves. Phase 6 was chosen (planning Q&A) to build the *live* CLI now rather than defer it to Phase 7, on the shared streaming core.
- The phase quality gate is a *watched demo* gate: it can only be closed by a real third-party watch, which requires the merged Streamlit app. Making this task own that `/verify` is what turns three merged PRs into a passed phase.
- A live CLI built on the same `stream_run` core as the Streamlit app means the Plan B is not a divergent code path — it renders the identical progress events and labels, so the fallback tells the same story (the [risk register](../../build_plan.md)'s venue-network and Streamlit-failure mitigations both lean on this).
- Reusing the existing rich render helpers in `cli.py` for the final report keeps the live mode and the current `demo` output consistent.

## Concrete steps (what to produce)

1. **Add a live flag to the `demo` command** — extend the argparse `demo` subparser with a `--live` (or `--stream`) flag. Default behavior (no flag) stays exactly as today: blocking `ainvoke` + final render, so the Phase 5 `/verify` path is untouched. With the flag, the run uses the live path.
2. **Drive the run through `stream_run` under `rich.live`** — when `--live` is set, build the initial state (as `_run_demo` does today), then consume `stream_run(make_graph(), initial_state)` inside a `rich.live.Live` context, updating a per-investigator status table as each `ProgressEvent` arrives. Use the node→label mapping from Task 1's streaming module so the CLI labels match the Streamlit labels exactly. Show the spawned sub-investigator row when its event arrives.
3. **Render the final report through the existing helpers** — when the terminal `CausalReport` is surfaced by the stream, render it with the existing `_render_report(...)` (and emit the LangSmith trace notice via the existing `_render_trace_notice(...)`), so the live mode's end state matches the current `demo` output. No second copy of the report-rendering code.
4. **Run the cross-surface `/verify`** (the phase quality gate):
   - **Streamlit (primary)**: launch `uv run streamlit run src/expertview/ui/app.py`, run the rehearsed CNC incident end-to-end, and have a third party (or a stand-in following the no-prompting rule) watch and describe what is happening — the parallel fan-out, the spawn, the convergence result — without coaching. Confirm the Mermaid topology is visible and its labels match the node names in `orchestration/runner.py`.
   - **Live CLI (Plan B)**: run `uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml --live` and confirm the investigators light up incrementally and the final report matches the non-live output.
   - Run the **second (process-led) incident** through at least one surface to confirm the demo is not CNC-only.
   - Confirm both surfaces show the convergence-computed numbers from Phase 5 (the top cause and confidence summary the synthesizer returned), and that the LangSmith trace still captures the run.
5. **Verify locally**: `uv run pytest` green; `uv run ruff check .` and `uv run ruff format --check .` clean; the live and non-live `demo` paths both produce a coherent report.

## What each step does

- **Step 1** adds the live mode without disturbing the existing blocking demo path, so Phase 5's verified behavior and any scripts relying on it keep working.
- **Step 2** is the CLI's live view: the same incremental story as Streamlit, rendered in the terminal via the shared streaming core, so the Plan B is a true mirror not a re-implementation.
- **Step 3** keeps a single report-rendering implementation in `cli.py` — the live mode and the default mode end identically.
- **Step 4** is the phase quality gate itself: the watched Streamlit demo is the primary gate, the live CLI confirms the fallback, and the second incident proves the surface is scenario-general.
- **Step 5** is the local check before opening the PR.

## Code locations

- `src/expertview/cli.py` (edit — add the `--live` flag to the `demo` subparser; add a live run path that consumes `stream_run` under `rich.live.Live`; reuse `_render_report` / `_render_trace_notice` for the end state).
- `tests/unit/test_cli.py` or `tests/integration/test_cli_live.py` (new if absent — a thin test that the `--live` flag parses and the live path renders a report against a fake stream; keep it light, the streaming core is already tested in Task 1).

## Connections

**Upstream**:

- [[task-1-run-progress-streaming-core]] — `stream_run` drives the `rich.live` table; the node→label mapping keeps CLI labels identical to the Streamlit labels.
- [[task-2-streamlit-demo-app]] — must be merged so the watched-demo `/verify` (the phase gate) can run against the Streamlit app.
- `cli.py` (Phase 2, iterated through Phase 5) — the existing `demo` command, `_run_demo`, `_render_report`, `_render_trace_notice`, and the initial-state construction are reused; the live path is additive.
- `orchestration/runner.py` — `make_graph()` (Phase 4); `evidence/models.py` — `CausalReport`, `Incident` (Phase 1).

**Downstream**:

- Phase 7's rehearsal runs three consecutive clean demos on the actual demo laptop, at least one with `EXPERTVIEW_SYNTH_MODEL` set to a paid frontier ID; both the Streamlit app and this live CLI are the surfaces exercised, and the LangSmith trace export uses the same runs.
- The build_plan's demo-script outline is drafted in this phase and rehearsed in Phase 7; the watched-demo `/verify` here is the first run-through of that script.

## Parallelism rationale

- The CLI code touches only `cli.py` (and a thin CLI test); Task 2 touches only `src/expertview/ui/*`. The two never edit the same file, so the CLI build can proceed in parallel with Task 2 once Task 1 is merged.
- This task is nonetheless the **final merge point** because its `/verify` is a watched-demo gate against the Streamlit app — the gate, not the code, is what depends on Task 2.
- It introduces no new module boundary: `cli.py` is already the top-of-stack entry point importing `orchestration/` and `evidence/models`; adding the streaming-core import stays within that established surface ([architecture.md §5](../../architecture.md)).

## Risks / constraints / assumptions

- **Constraint**: the default (no-flag) `demo` behavior is unchanged — the live mode is opt-in via `--live`, so Phase 5's verified path and any dependent scripts keep working.
- **Constraint**: no second copy of report rendering — the live mode reuses `cli.py`'s existing `_render_report` / `_render_trace_notice`. The report-render duplication tracked in the Phase 6 README is the `cli.py`↔`ui/` pair (Task 2), not a third copy here.
- **Constraint**: no LLM client constructed in `cli.py` beyond what `make_graph()` already wires ([CLAUDE.md architecture rules](../../../CLAUDE.md)).
- **Risk — `rich.live` redraw fights the async generator**: `rich.live.Live` is synchronous; `stream_run` is async. Mitigation: drive the async generator with `asyncio.run` (or `async for` inside the existing `asyncio.run(_run_demo(...))` entry) and update the `Live` renderable per event — `_run_demo` is already an async function invoked via `asyncio.run`, so the live path stays inside that existing async context rather than nesting event loops.
- **Risk — the watched-demo gate is subjective**: "a third party can describe what is happening without prompting" has no assertion. Mitigation: run it as a real observation — note in the PR what the observer said unprompted (which regions they understood, whether they recognized the parallel fan-out and the spawn); if they needed prompting, that is a UI-legibility fix in Task 2's surface, surfaced back as a follow-up before the phase is tagged.
- **Risk — OpenRouter free-tier limits during repeated `/verify` runs**: the watched demo plus the live CLI plus the second incident is several end-to-end runs, each up to ~12 investigator-class calls + a synthesizer call. Phase 3's `asyncio.Semaphore(5)` caps per-run concurrency. Mitigation: run incidents sequentially, not concurrently; if 429s appear, lower the cap as in Phase 3; Phase 7's retry/backoff is the real fix.
- **Risk — Mermaid labels drift from code (gate clause)**: the gate explicitly requires labels match the actual code. Mitigation: the Streamlit topology is generated by `render_topology_mermaid` from the real graph (Task 1); the `/verify` step checks the rendered labels against `orchestration/runner.py`'s node-name constants directly.
- **Assumption**: both rehearsed incidents (CNC and the Phase 5 process-led incident) are on `main` and produce distinct re-scored reports (the Phase 5 gate guarantees this). If a `/verify` run shows them collapsed, that is a Phase 5 regression, not a Phase 6 bug — stop and flag it.

## Definition of done

- `cli.py demo` accepts a `--live` flag; without it, behavior is byte-for-byte the current blocking `ainvoke` + final render; with it, the run streams through `stream_run` under `rich.live` and lights up investigators incrementally before rendering the final report via the existing helpers.
- CLI live-mode labels match the Streamlit labels (both import Task 1's node→label mapping); the spawned sub-investigator appears live in both surfaces.
- The cross-surface `/verify` passes: a third party watches the Streamlit CNC demo and describes the fan-out, spawn, and result unprompted; the Mermaid topology is visible with labels matching `orchestration/runner.py`; the live CLI run mirrors it; the second (process-led) incident runs through at least one surface; both surfaces show the Phase 5 convergence-computed numbers; the LangSmith trace is captured.
- A thin CLI test confirms the `--live` flag parses and the live path renders a report against a fake stream (no network).
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/phase-6-cli-live-and-verify` per [branching_strategy.md §5](../../branching_strategy.md). PR description: records the watched-demo observation (what the third party said unprompted), confirms the Mermaid-labels-match-code check, notes the chosen async↔`rich.live` driving pattern, and lists the incidents `/verify`'d.
- Once merged, confirm the Phase 6 quality gate is green and tag `v0.7.0-demo` per [branching_strategy.md §8](../../branching_strategy.md). Phase 7 (polish + rehearsal) is unblocked.
