# Task 2 — Streamlit Single-Screen Demo App

> **Branch suggestion**: `feature/streamlit-demo-app`
> **Parallelism**: **Parallelizable with Task 3's CLI build.** Touches only the new `src/expertview/ui/` package; shares no file with Task 3's `cli.py` edits. Both depend on Task 1.
> **Depends on**: Task 1 merged (`orchestration/streaming.py` exports `stream_run` and `render_topology_mermaid`).

## Purpose

Build the demo surface a non-technical viewer watches: a single-screen Streamlit app with three regions — incident input, a live investigator-status panel beside the Mermaid topology diagram, and the final causal-report render with confidence bars and citations. The app loads an incident, compiles the graph via `make_graph()`, drives it through Task 1's `stream_run(...)`, lights up each investigator as its node completes, shows the LangGraph topology from `render_topology_mermaid(...)` via `st.mermaid`, and renders the re-scored `CausalReport` the synthesizer produced.

This task creates the new `src/expertview/ui/` package and nothing outside it. It does **not** edit `cli.py` (Task 3 owns the live CLI), does **not** modify the graph, the nodes, or the streaming core, and does **not** change `agents/`, `rag/`, or `evidence/`. The single screen with exactly three regions is the hard cap — the build_plan's named mitigation against UI scope creep.

## Why it matters

- [build_plan.md §Phase 6](../../build_plan.md) names the three regions and the Mermaid topology tab as the phase outputs; this task is where they exist.
- The phase quality gate — "a third party can watch the demo and describe what is happening without prompting; the Mermaid topology diagram is visible and labels match the actual code" — is satisfied against *this* app. The live panel makes the parallel fan-out legible; the Mermaid tab makes the LangGraph shape legible; the report region makes the convergence result legible.
- [decisions.md (2026-05-25)](../../decisions.md) locks Streamlit and the `st.mermaid` rendering of `compiled_graph.get_graph().draw_mermaid()`. This task is the realization of that locked choice.
- Keeping the app behind its own `ui/` package ([decisions.md (2026-05-25)](../../decisions.md): "UI lives in its own `src/expertview/ui/` package behind no other module") preserves the Path B lift story — the app can be swapped or dropped without touching orchestration, agents, or rag.

## Concrete steps (what to produce)

1. **Obtain approval to add `streamlit` as a dependency, then add it with a decision entry.** `streamlit` is not in `pyproject.toml`. Before any app code, get explicit user approval and add a [decisions.md](../../decisions.md) entry (per [CLAUDE.md](../../../CLAUDE.md)'s hard rule on dependency changes) recording the add and the version constraint. Add it to the main runtime dependencies (the app is runtime, not dev). Do not silently edit `pyproject.toml`.
2. **Create the `ui/` package** — `src/expertview/ui/__init__.py` and `src/expertview/ui/app.py`. The app is the single screen; if region renderers grow large, factor private render helpers into a sibling module (e.g., `ui/render.py`) rather than letting one file sprawl — but keep all three regions on one screen.
3. **Region 1 — incident input** — let the viewer pick or load an incident (a selector over `data/incidents/*.yaml`, or a path/upload), parse it into an `Incident` via the existing model, and show its summary/symptoms so the audience sees what is being investigated before the run starts. A "Run investigation" control kicks off the graph.
4. **Region 2 — live investigator status + topology** — on run, drive `stream_run(make_graph(), initial_state)` and update a per-investigator status panel as each `ProgressEvent` arrives, using `st.empty()` + `st.fragment` for cheap incremental redraws (the build_plan's named mechanism). Beside or behind a tab, render `render_topology_mermaid(compiled_graph)` via `st.mermaid` so the LangGraph topology is visible with labels that match the code. Show the dynamically spawned sub-investigator when its event arrives, so the spawn is visible live.
5. **Region 3 — final causal report** — when the terminal `CausalReport` is surfaced, render it on one screen: top hypotheses with confidence bars, the `confidence_summary`, the causal chain, and citations linking back to source documents. The numbers shown are the convergence-computed ones from Phase 5 — render them, do not recompute.
6. **Document the launch command** — the app runs via `uv run streamlit run src/expertview/ui/app.py` (not `python -m`). State this in the PR description and, if a short usage note belongs anywhere, the app's module docstring — not a new top-level doc.
7. **Verify locally**: launch the app, run the rehearsed CNC incident end-to-end, confirm all three regions populate and the Mermaid topology renders; `uv run ruff check .` and `uv run ruff format --check .` clean. (The watched-by-a-third-party gate is Task 3's cross-surface `/verify`.)

## What each step does

- **Step 1** clears the dependency gate honestly: Streamlit cannot enter the repo without approval and a logged decision, so this is the first action, not an afterthought.
- **Step 2** establishes the `ui/` package as a self-contained, liftable surface behind no other module.
- **Step 3** gives the audience the "what are we investigating" framing before the machinery starts — the opening beat of the demo script.
- **Step 4** is the phase's headline: parallel investigators lighting up live next to the actual LangGraph topology, which is what makes the multi-agent architecture legible to a non-technical viewer.
- **Step 5** closes the loop with the evidence-weighted result, reusing Phase 5's computed numbers so the UI never disagrees with the convergence math.
- **Step 6** records how to start the app, since Streamlit's launcher differs from the CLI entry point.
- **Step 7** is the local check; the formal third-party watch is the phase gate in Task 3.

## Code locations

- `src/expertview/ui/__init__.py` (new — package marker).
- `src/expertview/ui/app.py` (new — the single-screen Streamlit app: three regions, live stream consumption, `st.mermaid` topology).
- `src/expertview/ui/render.py` (new if absent — private render helpers for the report region, only if `app.py` would otherwise sprawl).
- `pyproject.toml` (edit — add `streamlit`; **gated on Step 1's approval + decision entry**, not done unilaterally).

## Connections

**Upstream**:

- [[task-1-run-progress-streaming-core]] — `stream_run` (drives the live panel) and `render_topology_mermaid` (feeds `st.mermaid`), plus the node→label mapping.
- `orchestration/runner.py` — `make_graph()` compiles the graph the app runs (Phase 4).
- `orchestration/state.py` — `ExpertViewState` for the initial-state construction (Phase 1), mirroring how `cli.py` builds it.
- `evidence/models.py` — `Incident` (parsed from the selected YAML), `CausalReport`, `Hypothesis`, `CausalLink`, `Finding` (rendered in Region 3) (Phase 1).

**Downstream**:

- [[task-3-cli-live-mode-and-verify]]'s cross-surface `/verify` watches this app to satisfy the phase quality gate; the live CLI mode is the Plan-B mirror of this surface.
- Phase 7's rehearsal runs this app with `EXPERTVIEW_SYNTH_MODEL` set to a paid frontier ID; the app is model-agnostic (it renders whatever `CausalReport` the synthesizer returns), so the swap needs no UI change.

## Parallelism rationale

- This task touches only `src/expertview/ui/*` (new) and `pyproject.toml` (the gated `streamlit` add). Task 3 touches `cli.py`. The two share no editing surface and can proceed concurrently once Task 1 is merged.
- The one shared file is `pyproject.toml`: if Task 3 also needs a dependency, coordinate the edits — but Task 3's live CLI uses `rich` (already a dependency from Phase 1) and the streaming core, so it is expected to add nothing to `pyproject.toml`.
- `ui/` is a new top-of-stack package: it imports `orchestration/` and `evidence/models` only — never `agents/` or `rag/` internals — establishing the wall the Phase 6 README flags for a possible [architecture.md §5](../../architecture.md) update. This keeps `ui/` liftable and respects the boundary rule by analogy with `cli.py`.

## Risks / constraints / assumptions

- **Constraint**: `streamlit` is a dependency change — explicit user approval **and** a [decisions.md](../../decisions.md) entry are required before `pyproject.toml` is touched ([CLAUDE.md](../../../CLAUDE.md) hard rules). This is Step 1 and blocks the rest of the task.
- **Constraint**: hard-cap the UI to one screen with three regions ([build_plan.md §Phase 6](../../build_plan.md) scope-creep mitigation). No multi-page app, no extra dashboards, no settings screens.
- **Constraint**: `ui/` imports `orchestration/` and `evidence/models` only; nothing from `agents/` or `rag/`. The app does not recompute convergence — it renders the synthesizer's `CausalReport` as-is.
- **Constraint**: no LLM client is constructed in `ui/` ([CLAUDE.md architecture rules](../../../CLAUDE.md)); the app calls `make_graph()`, which constructs clients via `agents/llms.py`.
- **Risk — async `astream` ↔ synchronous Streamlit bridge**: Streamlit reruns scripts top-to-bottom and is synchronous; `stream_run` is an async generator. Bridging (e.g., `asyncio.run` over the generator while pushing updates into an `st.empty()`/`st.fragment` placeholder, or consuming the generator inside a fragment) is the genuine technical risk of the phase. Mitigation: Task 1 isolated the async logic so the app only consumes typed events; spike the bridge against the CNC incident early, and if `st.fragment` incremental updates fight the event loop, fall back to draining the generator and snapshotting state per fragment tick. Record the chosen bridge pattern in the PR.
- **Risk — live panel updates feel laggy or batch at the end**: if Streamlit only redraws after the run completes, the "parallel execution live" goal is lost. Mitigation: verify mid-run redraws actually appear during a real run (Step 7); the five investigators should visibly populate before the synthesizer row.
- **Risk — Mermaid labels drift from code**: the gate requires labels match the actual code. Mitigation: the Mermaid string comes from `render_topology_mermaid(compiled_graph)` (Task 1), generated from the real graph with constant-keyed labels — the app renders it verbatim and never hand-edits node names.
- **Risk — report-render duplication with `cli.py`**: confidence-bar/citation rendering already exists privately in `cli.py`. Mitigation: this is the **second** occurrence (below the ≥3 threshold) — write `ui/`'s own render helpers; do **not** import `cli.py` internals (that would couple the entry points) and do **not** extract a shared module yet. The Phase 6 README tracks the duplication for the ≥3 trigger.
- **Assumption**: the rehearsed incidents under `data/incidents/` (CNC and the Phase 5 process-led incident) are on `main` and load cleanly. If the incident selector finds none, the input region surfaces that rather than crashing.

## Definition of done

- `streamlit` is added to `pyproject.toml` **only after** user approval, with a [decisions.md](../../decisions.md) entry recording the add and version constraint.
- `src/expertview/ui/` exists as a self-contained package: a single-screen app with three regions (incident input; live investigator-status panel + `st.mermaid` topology; final causal-report render with confidence bars + citations).
- The live panel updates incrementally during a real run (investigators populate before the synthesizer), driven by Task 1's `stream_run`; the topology renders from `render_topology_mermaid` with labels matching the code; the dynamically spawned sub-investigator appears when its event arrives.
- The report region renders the synthesizer's re-scored `CausalReport` numbers as-is (no recomputation in the UI).
- `ui/` imports only `orchestration/` and `evidence/models`; it does not import `cli.py` internals, `agents/`, or `rag/`.
- The launch command (`uv run streamlit run src/expertview/ui/app.py`) is documented in the PR description and the app docstring.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/streamlit-demo-app` per [branching_strategy.md §5](../../branching_strategy.md). PR description: links the `streamlit` decision entry; records the async↔Streamlit bridge pattern chosen; confirms the three-region cap held and the live panel updates mid-run; notes the report-render duplication is a deliberate second occurrence, not an extraction candidate yet.
