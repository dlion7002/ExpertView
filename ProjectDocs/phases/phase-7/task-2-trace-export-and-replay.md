# Task 2 — LangSmith Trace Export Tooling + Documented Replay Path

> **Branch suggestion**: `feature/phase-7-trace-export-and-replay`
> **Parallelism**: **Parallelizable with Task 1.** Both unblock immediately on Phase 6 close; they edit disjoint surfaces. No shared editing surface with Task 1.
> **Depends on**: Phase 6 complete (`v0.7.0-demo` tagged).

## Purpose

Land the tooling the user will fire post-merge to capture a successful run's LangSmith trace as a vendored artifact, and a replay command that re-renders the captured run's `CausalReport` from that artifact without re-invoking the graph. Today the CLI already collects a `RunCollectorCallbackHandler` and surfaces the trace URL (see `_render_trace_notice` in [src/expertview/cli.py](../../../src/expertview/cli.py)), but there is no way to *save* the trace locally or to reconstruct the report from a saved one — which means the [build_plan.md §Phase 7](../../build_plan.md) line "LangSmith trace replay path as the final fallback" has no executable form.

This task ships:

1. An **export command** the user runs after a successful demo to download the rehearsed run's trace into a vendored artifact under `data/traces/`. Implementation is left to the executing agent — a `cli.py` subcommand (e.g., `expertview trace-export --run-id <id> --out data/traces/<slug>.json`) or a small standalone script under `scripts/` is fine. The artifact format is a JSON snapshot of the run tree sufficient to reproduce the final `CausalReport` render (the full run as `langsmith.Client().read_run(...)` returns it, with child runs flattened or referenced).
2. A **replay command** the user runs when the live LLM path is unavailable, that reads a vendored artifact and re-renders the same `CausalReport` (and trace-notice line) the live run would have produced — via the existing `_render_report` and `_render_trace_notice` helpers in `cli.py`. No graph invocation, no OpenRouter call, no embedding load. The replay is a pure presentation of a captured run.
3. A `data/traces/` directory established on `main` with a short `README.md` inside it documenting the artifact format, the naming convention (e.g., `<incident-slug>__<synth-model-slug>__<UTC-timestamp>.json`), and which committed artifacts exist. The actual rehearsal artifact is *not* produced here — the user captures it post-merge via the export command Task 3's runbook walks them through.
4. Unit tests covering the export round-trip (write → read) and the replay rendering path against a captured fixture (a small hand-crafted JSON snapshot that exercises the same `CausalReport` shape the synthesizer returns).

This task does **not** touch `agents/llms.py`, the graph topology, the investigator nodes, the synthesizer body, the convergence math, the prompts, the streaming core, the Streamlit app, or the live `--live` CLI mode. It edits `cli.py` only to add the new subcommands and their renderers; the existing `demo` subcommand and its `--live` flag are untouched.

## Why it matters

- [build_plan.md §Phase 7](../../build_plan.md) requires "a saved trace from a successful rehearsal run, with a documented `replay` command path so the demo can be reconstructed from the trace if all networks are down at the venue." The replay command + the documented format are the executable form of that line.
- The [risk register](../../build_plan.md) names "venue network outage" and "OpenRouter rate-limit during live demo" as in-event risks. The replay path is the documented secondary fallback after the cellular hotspot ([decisions.md 2026-05-25 — cloud-only with hotspot mitigation](../../decisions.md)).
- [[task-3-paid-synth-rehearsal-and-readme]] embeds the export command in the rehearsal runbook (the user runs it after their successful paid-synth run) and lists the replay command in the top-level `README.md`'s 1-minute guide. Both are user-facing surfaces; this task is what makes them point at real tooling.
- The `agent-trace-replay` skill candidate in [open_questions.md §Skill candidates](../../open_questions.md) has been blocked on the absence of such a path. This task does not draft the skill (per the Phase 7 README's skill-candidacy flag), but it removes the blocker and makes the candidate ready for a future ≥3-repetition trigger.

## Concrete steps (what to produce)

1. **Add an export subcommand or script.** Pick one of:
   - **Option A** — extend `cli.py` with a `trace-export` subcommand: `expertview trace-export --run-id <UUID> --out <path>`. It instantiates `LangSmithClient()`, calls `read_run(run_id, load_child_runs=True)` (or the equivalent in the installed `langsmith` version), and serializes the result to JSON at `--out`. If `--run-id` is omitted, attempt to read the most recent run from the current `LANGSMITH_PROJECT` and prompt the user (printed to stderr) with the candidate; the user passes `--run-id` to commit. No interactive prompts in argparse — print and exit non-zero if ambiguous, so the user re-runs with `--run-id`.
   - **Option B** — a standalone script under `scripts/trace_export.py` (or `.ps1` wrapping the Python script) that takes the same flags. Use this only if the executing agent judges that a CLI subcommand would balloon `cli.py` beyond its current shape.
   The chosen option is documented in the PR description. The exported JSON is sufficient to reconstruct the `CausalReport` render — at minimum: the final synthesizer-node output, the per-investigator finding outputs, the run's metadata (project, timestamps, model identifiers), and any error rows. Do not include raw API keys, raw prompt text *if* it carries secrets (prompt text from versioned files is fine), or any environment-variable values.
2. **Add a replay subcommand or script** with the same option choice as step 1: `expertview replay --trace <path>` reads the JSON artifact, reconstructs the `CausalReport` pydantic model from the captured synthesizer output, and renders it via the existing `_render_report(...)` in `cli.py`. The replay also prints a clearly-labeled "(replay from <path>)" line where the live mode prints the LangSmith URL via `_render_trace_notice(...)`, so the user knows they are looking at a captured run, not a live one. If the artifact is malformed or its captured `CausalReport` fails pydantic validation, fail loudly with the validation error — no silent fallback to a partial render.
3. **Establish `data/traces/` on `main`** with a `README.md` (kept short) inside it documenting:
   - The artifact format (a JSON object with the keys the export command writes).
   - The naming convention (suggested: `<incident-slug>__<synth-model-slug>__<UTC-timestamp>.json`).
   - The fact that the directory is committed but its contents are produced by the user's post-merge rehearsal run, not by the executing agent.
   - A short list of guarantees ("preserves citations verbatim; reproduces the same `CausalReport` render as the live run"; "does *not* re-invoke the graph or any LLM").
   Leave the directory committed via either an empty `.gitkeep` or the `README.md` itself; no real trace artifacts are committed in this task.
4. **Add unit tests** under `tests/unit/test_trace_export.py` (or `test_trace_replay.py` — name it for the surface it exercises). Cover:
   - **Export round-trip**: given a fake `LangSmithClient` whose `read_run` returns a hand-crafted run-tree dict, the export command writes a JSON file at the target path whose contents round-trip back to an equivalent dict.
   - **Replay renders the same report shape**: given a hand-crafted artifact JSON containing a known `CausalReport`-shaped synthesizer output, the replay subcommand prints a stdout payload whose key sections (verdict, top-hypothesis count, citations count) match what `_render_report` would print for the same `CausalReport` invoked directly. Capture stdout via `capsys` or `rich.console.Console(record=True)`; do not assert byte-for-byte rich output — assert on the content shape.
   - **Replay fails on malformed artifact**: malformed JSON or a captured `CausalReport` missing required fields raises `ValidationError` (or the wrapping `SystemExit` with non-zero exit code if the subcommand catches and re-prints).
   - **No live HTTP**: tests must patch `LangSmithClient` so no real network call happens. Tests must be deterministic and fast.
5. **Verify locally**: `uv run pytest tests/unit/test_trace_*` green; `uv run pytest` green overall; `uv run ruff check .` and `uv run ruff format --check .` clean. As a documentation-only sanity check (not a test), confirm the export subcommand's `--help` output and the replay subcommand's `--help` output read cleanly and would be copy-pasteable into the Task 3 runbook.

## What each step does

- **Step 1** ships the export capability the rehearsal runbook will instruct the user to fire after their successful paid-synth run. The chosen surface (subcommand vs script) is the user's entry point.
- **Step 2** is the offline-replay capability — the actual fallback when networks fail at a venue. The labeled `(replay from <path>)` line distinguishes a replay from a live run so the user (and any observer) is never misled.
- **Step 3** ensures the artifact directory exists on `main` with a self-documenting README so the user does not have to invent a naming convention at rehearsal time. The runbook in Task 3 will reference both the format and the convention from here.
- **Step 4** is the regression guard that proves export and replay match without consuming OpenRouter quota and without depending on a live LangSmith project.
- **Step 5** is the local quality gate.

## Code locations

- `src/expertview/cli.py` (edit if Option A is chosen — add the `trace-export` and `replay` subparsers and their handlers; reuse `_render_report` and add a labeled replay-notice; do not modify the `demo` subcommand or `--live` path) **or** `scripts/trace_export.py` + `scripts/trace_replay.py` (new if Option B is chosen; both small).
- `data/traces/README.md` (new — format, naming convention, guarantees).
- `data/traces/.gitkeep` (new, only if the README alone is not sufficient to keep the directory tracked).
- `tests/unit/test_trace_export.py` and/or `tests/unit/test_trace_replay.py` (new — fake-client + capsys fixtures; no live HTTP).

## Connections

**Upstream**:

- `cli.py` (Phase 2 → iterated through Phase 6) — `_render_report`, `_render_trace_notice`, the argparse scaffolding, the rich `Console` use. The new subcommands sit alongside `demo`; report rendering is reused, not duplicated.
- `evidence/models.py` (Phase 1) — `CausalReport` pydantic model is what the replay reconstructs from the JSON artifact.
- `langsmith` (Phase 1 — already a dependency via Phase 1's `pyproject.toml` set) — `LangSmithClient.read_run(...)` is the export's data source.
- `orchestration/runner.py` constants (`LANGSMITH_PROJECT_ENV`, etc.) — used by the export to default the project lookup.

**Downstream**:

- [[task-3-paid-synth-rehearsal-and-readme]] — the rehearsal runbook quotes the export command (with example flags) and the replay command. The top-level `README.md` 1-minute guide names the replay command as the offline fallback.
- The build_plan's [risk register](../../build_plan.md) — "venue network outage" and "OpenRouter rate-limit during live demo" both reference the replay path as the documented secondary mitigation.
- The `agent-trace-replay` skill candidate in [open_questions.md §Skill candidates](../../open_questions.md) — this task unblocks it for a future ≥3-occurrence trigger; the skill itself is not drafted in Phase 7 per the README skill-candidacy flag.

## Parallelism rationale

- This task edits `cli.py` (subcommand additions only; no edit to `demo` or `_stream_demo_live` paths) and adds `data/traces/` + `tests/unit/test_trace_*`. [[task-1-llm-hardening]] edits `agents/llms.py` and `tests/unit/test_llms.py`. No file overlap.
- Per [architecture.md §5](../../architecture.md)'s *"module boundaries are walls"* rule, `cli.py` is an entry-point layer that may import `orchestration/`, `evidence/`, and `langsmith`; this task stays within that surface — it does not reach into `agents/`, `rag/`, or `ui/` internals.
- Tests use fake `LangSmithClient` instances and hand-crafted JSON — they consume no OpenRouter quota and run offline, so Task 2 can be developed and verified without coordinating with Task 1.

## Risks / constraints / assumptions

- **Constraint**: LLM clients are constructed only in `agents/llms.py` ([CLAUDE.md architecture rules](../../../CLAUDE.md)). This task constructs no LLM. The replay path is deliberately LLM-free.
- **Constraint**: prompts live as files under `src/expertview/prompts/` ([CLAUDE.md hard rules](../../../CLAUDE.md)). This task touches no prompt.
- **Constraint**: no new dependency in `pyproject.toml` ([CLAUDE.md hard rules](../../../CLAUDE.md)). `langsmith` is already a dependency; `langchain-openai`'s collector is already imported in `cli.py`; standard-library JSON is sufficient for the artifact format. If the executing agent finds a real need for a new dependency, that is a `decisions.md`-gated change, not a silent add.
- **Constraint**: the artifact must not contain secrets. Mitigation: serialize only the run's structural fields (inputs, outputs, model identifiers, timestamps, child runs); do not serialize environment-variable snapshots or API keys.
- **Risk — LangSmith run shape drift**: the `langsmith` library may change `read_run`'s return shape between versions, breaking the export format. Mitigation: pin the artifact format to a small set of fields the export extracts explicitly, not to `read_run`'s raw return; version the artifact with a `"schema_version": 1` field so a future migration is visible.
- **Risk — replay drift from live render**: if the live rendering in `_render_report` later evolves (Phase 8+), the replay path renders the new format automatically (it calls the same function). That is the desired coupling. If a future phase wants to *keep* an older replay rendering stable, that is a follow-up not a Phase 7 concern.
- **Risk — large artifact size**: a fully-flattened trace tree for a Phase 5+ run with five investigator branches + sub-investigator + synthesizer + two-pass reasoning can run into hundreds of KB of JSON. [CLAUDE.md hard rules](../../../CLAUDE.md) forbid committing generated mock data >1MB; per-trace artifacts must stay under that ceiling. Mitigation: the export command rejects (with an exit-non-zero message) any artifact write that would exceed ~512 KB compressed-equivalent; the user picks which run to keep.
- **Risk — replay claimed as a live run**: if the labeled `(replay from <path>)` line is dropped or hidden, an observer could mistake a replay for a live demo. Mitigation: the labeled line is the first stdout output of the replay subcommand; a unit test asserts its presence.
- **Assumption**: the user will fire the export command once per rehearsal, against a known `--run-id` they read off the live `_render_trace_notice` output. The runbook in [[task-3-paid-synth-rehearsal-and-readme]] walks through this. No daemon, no background pull.
- **Assumption**: the `data/traces/` directory stays small (one or two artifacts at a time). If the directory grows beyond a handful of artifacts, that is a housekeeping concern for a future phase, not a Phase 7 task.

## Definition of done

- An export command (subcommand on `cli.py` or a script under `scripts/`) downloads a LangSmith run by `--run-id` to a JSON artifact at `--out`. The artifact is sufficient to reconstruct the run's `CausalReport`. Secrets are not serialized.
- A replay command (matching surface) reads such an artifact and renders the captured `CausalReport` via the existing `_render_report`, plus a labeled `(replay from <path>)` notice that replaces the live LangSmith-URL line. No graph invocation, no OpenRouter call.
- `data/traces/` exists on `main` with a short `README.md` documenting the artifact format, the naming convention, the "no committed real traces" rule, and the replay guarantees. A real trace artifact is *not* committed in this task.
- `tests/unit/test_trace_*` exists and passes: export round-trip; replay rendering matches the live render's section shape; malformed artifact fails loudly; no live HTTP. Tests are deterministic and offline.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/phase-7-trace-export-and-replay` per [branching_strategy.md §5](../../branching_strategy.md). PR description:
  - States the chosen surface (CLI subcommand vs standalone script) and the rationale in one sentence.
  - Quotes the export `--help` and the replay `--help` output so reviewers see the exact user surface the runbook will reference.
  - Lists the artifact JSON schema's top-level keys (including `"schema_version"`) and confirms no secrets are serialized.
  - Notes that no real trace artifact is committed; the rehearsal artifact is captured by the user post-merge via the runbook in Task 3.
