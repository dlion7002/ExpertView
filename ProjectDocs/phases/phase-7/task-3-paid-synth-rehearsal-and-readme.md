# Task 3 — Rehearsal Materials, Top-Level README, and the Human-Checklist Hand-Off

> **Branch suggestion**: `feature/phase-7-rehearsal-and-readme`
> **Parallelism**: **Sequential.** Final merge point of Phase 7. References commands and behaviors that Tasks 1 and 2 introduce; must run after both are merged to `main`.
> **Depends on**: Task 1 merged (`agents/llms.py` carries retry/backoff + deterministic seed + cache-invalidation docstring) and Task 2 merged (the trace-export + replay commands exist and `data/traces/` is on `main`).

## Purpose

Land everything the user needs so they can fire the Phase 7 rehearsal — the paid-synthesizer swap, the three demo runs, the trace export, and the watched observation — in **one short sitting at the keyboard**, with no implementation work left to do. The executing agent does **not** perform the paid-synth swap, the three rehearsal runs, the trace capture from a live run, or any watched observation; those require the user deciding when to spend OpenRouter budget and observing behavior the agent cannot evaluate. The deliverables of this task are all automatable: a top-level `README.md`, a step-by-step rehearsal runbook with copy-paste commands, optional helper scripts that bundle the env-var setup and the demo invocations, and any thin pre-flight check that confirms the environment is ready before the user starts spending paid-tier credit.

This task does **not** modify `agents/llms.py`, the graph topology, the investigator nodes, the synthesizer body, the convergence math, the prompts, the streaming core, the Streamlit app, the live `--live` CLI mode, or the trace export/replay subcommands introduced in [[task-2-trace-export-and-replay]]. It is documentation, runbooks, and (optionally) thin glue.

After merge, the user runs the rehearsal runbook against the merged code. The phase tag (`v0.8.0-demo`) is cut on the **automatable-work merge**, not on the human rehearsal — the rehearsal is a downstream checkpoint, not a gate on the tag.

## Why it matters

- [build_plan.md §Phase 7](../../build_plan.md) names the rehearsal outputs explicitly: "synthesizer swap rehearsal" on the demo laptop, "LangSmith trace export" of a successful rehearsal run, and a "`README.md` with a 1-minute run-it-yourself guide (lists the two env vars: `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`)." Tasks 1 and 2 ship the underlying capabilities; this task is the user-facing surface that turns them into a fireable rehearsal.
- The 2026-05-27 user direction "do not include that. I wont be using the laptop for now" (recorded in the [Phase 7 README pre-flight](README.md)) means the human-only steps are deferred to a future sitting. Without the runbook landing now, the user has no captured plan to follow when they re-engage. Writing the runbook *during* Phase 7 (while the system is fresh) is the right time to capture it.
- The top-level `README.md` is the project's front door for any reader landing in the repo cold — judges at the hackathon, recruiters reading the CV link, future-Claude in a fresh session. The 1-minute guide is the load-bearing first impression.
- The [risk register](../../build_plan.md)'s "venue network outage", "OpenRouter rate-limit during live demo", and "judge asks an off-script question" lines all reference materials this task produces: the replay path documented in the README, the runbook's "what to say when X happens" notes, and the architecture/Mermaid pointers.

## Concrete steps (what to produce)

1. **Write the top-level `README.md` (1-minute run-it-yourself guide)** at the repo root. Required content, kept short:
   - One-paragraph project description (RCA over industrial-manufacturing incidents; LangGraph + OpenRouter + local embeddings; CV/portfolio asset that also targets a shapeX hackathon milestone — match the framing in [project_introduction.md](../../project_introduction.md) without restating it).
   - Two env vars to set before running: `OPENROUTER_API_KEY` (required) and `LANGSMITH_API_KEY` (recommended, enables traces). Also note the optional `LANGSMITH_PROJECT` and the optional `EXPERTVIEW_SYNTH_MODEL` (default = build-phase free synth; set to a paid frontier ID for demo runs).
   - Three commands the user can fire end-to-end:
     - `uv sync` (one-time install).
     - `uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml` — the canonical demo run.
     - `uv run streamlit run src/expertview/ui/app.py` — the Streamlit surface.
   - A short "Offline replay" section pointing at the Task 2 replay command (`uv run python -m expertview.cli replay --trace data/traces/<artifact>.json`, or the script equivalent — exact form depends on Task 2's chosen surface), explaining it is the fallback when live LLM access is unavailable.
   - A short "Demo rehearsal" section pointing at the rehearsal runbook (step 2 below) for anyone preparing for a live demo.
   - A "Documentation map" stub with one-line pointers to [vision.md](../../vision.md), [architecture.md](../../architecture.md), and [build_plan.md](../../build_plan.md).
   Keep the README under ~150 lines. No emojis. Match the matter-of-fact tone of the existing `ProjectDocs/*.md`.
2. **Write the rehearsal runbook** under `ProjectDocs/runbooks/phase-7-rehearsal.md` (new — establish the `runbooks/` subfolder if absent). This is **the human checklist for the user to fire post-merge.** Structure:
   - **Pre-flight** (≤5 minutes): set `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`; confirm `EXPERTVIEW_SYNTH_MODEL` is unset (build-phase default) for the warm-up run; confirm OpenRouter dashboard shows budget headroom (link in the runbook); confirm a clean working tree on `main` at the v0.8.0-demo tag.
   - **Warm-up run (free synth)** — one demo invocation per incident on the free build-phase synthesizer, to confirm the environment works end-to-end before spending paid credit. Both commands quoted verbatim, with `--live` flag included so the live CLI surface is exercised. Confirm each prints a coherent `CausalReport`.
   - **Paid-synth swap** — set `EXPERTVIEW_SYNTH_MODEL=anthropic/claude-opus-4.7` (or the current paid frontier ID OpenRouter lists at rehearsal time; the runbook says "check OpenRouter's catalog for the current paid frontier ID" rather than hard-coding a specific model that may be retired). One demo invocation per incident **plus one Streamlit run** on the paid frontier — the watched-demo gate is satisfied against the Streamlit surface, the CLI surface is the Plan B. That makes three paid runs total (CLI-CNC, CLI-process-led, Streamlit-CNC), matching [build_plan.md §Phase 7](../../build_plan.md)'s "three consecutive clean runs" verbiage. Each run's expected outputs are described: top-cause domain, confidence-bar visual, citations panel, LangSmith trace URL.
   - **Trace export** — for the third (Streamlit) run, fire the Task 2 export command with the LangSmith run ID printed by the CLI/UI, writing to `data/traces/<incident-slug>__<paid-synth-slug>__<UTC-timestamp>.json` per the convention in [`data/traces/README.md`](../../../data/traces/README.md). Confirm the artifact is under the size ceiling (≤512 KB per Task 2). Optionally commit the artifact (the runbook flags that committing is the user's call — it makes the replay fallback portable, but adds to repo size; ≤1 MB per [CLAUDE.md hard rules](../../../CLAUDE.md)).
   - **Replay sanity check** — run the Task 2 replay command against the just-captured artifact and confirm the rendered `CausalReport` matches the live render (verdict, top hypothesis, citations, confidence summary). The labeled `(replay from <path>)` line confirms it is a replay, not a live invocation.
   - **Watched observation** — the runbook lists what a third-party observer should be able to describe unprompted (fan-out across five investigators; the spawned sub-investigator appearing or being skipped with a reason; the top cause and its confidence; the LangSmith URL). If the observer needs prompting, the runbook records that as feedback for a follow-up UI fix and notes the observation in the rehearsal log section (step 3).
   - **What to do when X happens** — three short subsections: (a) OpenRouter 429 mid-run → the retry/backoff from [[task-1-llm-hardening]] handles it; if it exhausts, lower the semaphore cap and re-run, the runbook gives the exact code-pointer line; (b) venue network outage → fire the replay command on the most recent vendored artifact; (c) judge asks an off-script question → open the Mermaid topology in the Streamlit "Topology" tab and the architecture diagram in [architecture.md §4](../../architecture.md).
   - **Rehearsal log** — a short table at the bottom the user fills in by hand after each run (date, incident, synth model, top cause, observed runtime, observer-comment one-liner). Empty rows pre-populated.
   The runbook is copy-paste-ready: every command is in a fenced block, exactly as the user will type it. Variables (run IDs, artifact filenames) are bracketed placeholders so the user knows what to substitute.
3. **(Optional) Helper scripts** under `scripts/`. Pick at most one, only if the executing agent judges it materially reduces the human time-cost of the rehearsal:
   - `scripts/rehearse.ps1` (PowerShell — primary; matches the user's shell) and/or `scripts/rehearse.sh` (Bash, for the Bash tool). The script reads `$env:EXPERTVIEW_SYNTH_MODEL`, prints what it is about to do (the incident path, the synth model), pauses for an explicit user `y` confirmation (the script's only interactive prompt — print to stderr, read from stdin), then fires the CLI demo command. It does **not** auto-fire the next run; the user re-runs the script per incident. The goal is "fewer typos, no autopilot" — not automation of the rehearsal itself.
   - Skip the script entirely if the runbook's fenced commands are already copy-paste-trivial. The executing agent picks; the PR description explains the choice in one sentence.
4. **(Optional) `expertview doctor` pre-flight subcommand or script.** A thin check (≤50 LOC) that verifies the rehearsal-readiness state without running the graph. Checks to include:
   - `OPENROUTER_API_KEY` and `LANGSMITH_API_KEY` are set and non-empty.
   - `EXPERTVIEW_SYNTH_MODEL`'s current value is printed back (so the user sees "free build synth" vs "paid frontier" before firing).
   - The `data/incidents/cnc_out_of_tolerance.yaml` and the second (process-led) incident YAML exist and parse as `Incident`.
   - The Streamlit + `streamlit-mermaid` dependencies import successfully.
   - The local embedding model (`BAAI/bge-small-en-v1.5`) is downloadable / cached (a quick `HuggingFaceEmbeddings(...).embed_query("ping")` round-trip; ≤2 seconds).
   - The `langsmith` client connects with the current API key (a lightweight `LangSmithClient().list_projects(limit=1)` or equivalent; ≤2 seconds).
   - The trace-export and replay subcommands print their `--help` without error.
   The doctor exits 0 if all checks pass, non-zero with a list of which check failed if any fail. Skip this entirely if the executing agent judges it gold-plating; the runbook's pre-flight section covers the same ground manually. The PR explains the choice.
5. **Decisions log + phase close**: when the PR is approved, the executing agent's *summary* (per [workflow.md §1](../../workflow.md)) records that two entries should be appended to [decisions.md](../../decisions.md) at merge time — one logging the Phase 7 deferral of the laptop-bound 3-run observational portion of the quality gate (referencing the 2026-05-27 direction), and one logging the human-checklist hand-off pattern that this task establishes. The executing agent does **not** edit [decisions.md](../../decisions.md) itself during the task (it is one of the gated files per [CLAUDE.md hard rules](../../../CLAUDE.md)); the entries are written by the user at merge time or in the merge commit message.
6. **Verify locally**: `uv run pytest` green (this task adds no new test code unless a doctor command or helper script needs one — keep tests minimal); `uv run ruff check .` and `uv run ruff format --check .` clean. Confirm every command quoted in the runbook and README is copy-pasteable: open a fresh PowerShell, copy each fenced block into it, and confirm at minimum the `--help` form runs without a `command not found` or argument error. Live LLM calls are *not* part of this verification — they are the user's downstream rehearsal step.

## What each step does

- **Step 1** is the project's front door. A reader who lands on the repo can run the demo in under a minute without reading any other doc.
- **Step 2** is the load-bearing deliverable for the user's perspective: a single-page checklist that turns "I should rehearse the demo" into a sequence of copy-paste commands with expected outputs. It absorbs every Phase 7 build_plan line that requires human action.
- **Step 3 (optional)** removes the chance of a typo in a one-shot rehearsal command. Skip if not warranted.
- **Step 4 (optional)** lets the user confirm the environment is rehearsal-ready before spending paid credit on a doomed run. Skip if not warranted.
- **Step 5** captures the two decisions the merge produces, without violating the rule that the executing agent does not edit `decisions.md` mid-task.
- **Step 6** is the local quality gate — minimal because the task is primarily documentation.

## Code locations

- `README.md` (new, at the repo root — top-level run-it-yourself guide).
- `ProjectDocs/runbooks/phase-7-rehearsal.md` (new — establish the `ProjectDocs/runbooks/` subfolder).
- `scripts/rehearse.ps1` and/or `scripts/rehearse.sh` (new, optional — wrap the env-var setup + demo command with an explicit-confirm prompt; ≤30 LOC each).
- `src/expertview/cli.py` (edit, optional — only if step 4 lands as a CLI subcommand: `doctor` subparser + handler) **or** `scripts/doctor.py` (new, optional — standalone alternative).
- `tests/unit/test_doctor.py` (new, only if step 4 lands and is non-trivial; minimal coverage: each check returns the expected result against fakes).

## Connections

**Upstream**:

- [[task-1-llm-hardening]] — the runbook's "What to do when OpenRouter 429" subsection references the retry/backoff this task ships. The deterministic-seed reproducibility hedge is also referenced in the runbook.
- [[task-2-trace-export-and-replay]] — the runbook quotes the export and replay commands verbatim; the README's "Offline replay" section points at the replay command; the `data/traces/` directory and its `README.md` (artifact format + naming convention) are referenced from the runbook.
- `cli.py` (Phase 2 → iterated through Phase 6) — the rehearsal commands are `uv run python -m expertview.cli demo --incident ... [--live]` and the trace subcommands; no edits beyond the optional `doctor` subcommand in step 4.
- `src/expertview/ui/app.py` (Phase 6) — referenced in the runbook's "paid-synth swap" step as the watched-demo surface.
- [build_plan.md §Phase 7](../../build_plan.md) — every step in the runbook traces back to a phase-7 output or risk-register entry.

**Downstream**:

- The user's post-merge rehearsal sitting — the runbook is its only document. When the user re-engages with a demo laptop, the runbook is the playbook.
- The at-hackathon usage plan in [build_plan.md §At-hackathon usage plan](../../build_plan.md) — the runbook's "Watched observation" and "What to do when X happens" subsections feed directly into the Path A adaptation playbook.
- [decisions.md](../../decisions.md) gains two entries at phase close (laptop-gate deferral; human-checklist hand-off pattern), written by the user.

## Parallelism rationale

- This task is **sequential by necessity**: the runbook and README reference commands (retry/backoff behavior, trace-export and replay surface) that Tasks 1 and 2 introduce. Writing them before those PRs merge would leave dangling references that turn into doc drift.
- It edits no module-boundary surface and adds no Python under `src/expertview/` beyond the optional `doctor` subcommand (which, if landed, stays inside `cli.py` per the entry-point-layer convention established in Phase 6). [architecture.md §5](../../architecture.md)'s walls are respected by default.
- It introduces no new top-level package; `scripts/` and `ProjectDocs/runbooks/` are conventional siblings of existing folders, not module-tree additions.

## Risks / constraints / assumptions

- **Constraint**: this task adds **no** LLM client construction and **no** prompt file ([CLAUDE.md hard rules](../../../CLAUDE.md) + [architecture.md §5](../../architecture.md)). The optional `doctor` checks construct embedding and LangSmith clients only through the existing factories.
- **Constraint**: no new dependency in `pyproject.toml` ([CLAUDE.md hard rules](../../../CLAUDE.md)). Helper scripts use the existing CLI; the doctor uses only already-installed libraries.
- **Constraint**: the executing agent does **not** edit [decisions.md](../../decisions.md) or [open_questions.md](../../open_questions.md) inside this task ([CLAUDE.md hard rules](../../../CLAUDE.md)); the two decision entries this task references are appended by the user at merge time.
- **Constraint**: the executing agent does **not** fire a paid-synth call, does **not** run the three rehearsal demos, and does **not** capture a real trace artifact. Any verification step that requires those is the user's downstream action; the runbook is the artifact this task delivers.
- **Risk — runbook drift from code**: if Task 1's retry policy or Task 2's command surface changes after merge, the runbook's quoted commands and references become stale. Mitigation: write the runbook *only after* Tasks 1 and 2 land on `main`, and quote `--help` output rather than inventing flag names. A doctor check (if landed) catches the simplest drifts (missing subcommand, missing env var).
- **Risk — README oversells the system**: a 1-minute guide can claim more than the code can deliver if it does not lean on the demo command's actual output. Mitigation: the README's "three commands" section is literally three commands and one expected-output sentence each — no marketing prose. The matter-of-fact tone of [project_introduction.md](../../project_introduction.md) and [vision.md](../../vision.md) is the reference style.
- **Risk — over-scripting reduces flexibility**: an aggressive helper script that fires all three rehearsal runs in sequence would remove the user's per-run decision and reduce the rehearsal to autopilot. Mitigation: any helper script (step 3) fires *one* run per invocation, with an explicit confirm prompt, and never chains. The runbook is the orchestration layer, not a script.
- **Risk — paid frontier model ID rot**: OpenRouter's catalog rotates; `anthropic/claude-opus-4.7` may not be the current paid frontier ID at rehearsal time. Mitigation: the runbook says "the current paid frontier ID OpenRouter lists at rehearsal time" with a link to the OpenRouter dashboard, and gives the example `anthropic/claude-opus-4.7` as illustrative. The user picks the live ID when they fire the rehearsal.
- **Risk — trace artifact committed with secrets**: if the user commits a captured trace artifact, it must not contain secrets. Mitigation: Task 2's export command is responsible for stripping secrets (Task 2 DoD); the runbook's trace-export step says "the export command does not serialize env-var values" and points at the artifact JSON's `"schema_version"` field.
- **Assumption**: the user will read the runbook end-to-end before firing the first paid-synth run. The runbook's structure assumes a single linear pass.
- **Assumption**: Task 1's retry/backoff is sufficient for one-shot rehearsal runs against the paid lane. If a future rehearsal exposes a 429 storm even with retry, that is a Phase 7 follow-up (raise the retry cap or lower concurrency), not a Phase 7 blocker.

## Definition of done

- `README.md` exists at the repo root with the project description, the two required env vars (`OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`), the three end-to-end commands (`uv sync`, the demo CLI invocation, the Streamlit invocation), the offline-replay pointer, the rehearsal-runbook pointer, and the documentation map. Under ~150 lines.
- `ProjectDocs/runbooks/phase-7-rehearsal.md` exists with the seven subsections from step 2: pre-flight, warm-up runs, paid-synth swap (three runs), trace export, replay sanity check, watched observation, "what to do when X happens", rehearsal log. Every command is in a copy-paste fenced block.
- Helper scripts under `scripts/` exist **or** the PR description explains why they were skipped. If they exist, each fires one run per invocation with an explicit confirm prompt and never chains.
- The optional `doctor` pre-flight (CLI subcommand or `scripts/doctor.py`) exists **or** the PR description explains why it was skipped. If it exists, it verifies env vars, incident YAMLs, Streamlit imports, embedding round-trip, and LangSmith connectivity, and exits non-zero on any failure.
- Every quoted command in the README and runbook is verified copy-pasteable (the `--help` form at minimum runs without error in a fresh PowerShell).
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- The executing agent has **not** fired a paid-synth call, has **not** run the three rehearsal demos, has **not** captured a live trace artifact, and has **not** edited `decisions.md` or `open_questions.md`.
- PR opened on `feature/phase-7-rehearsal-and-readme` per [branching_strategy.md §5](../../branching_strategy.md). PR description:
  - Lists the files landed (README, runbook, optional scripts, optional doctor) with one-line summaries.
  - States whether helper scripts and the doctor command were landed or skipped, with the rationale in one sentence each.
  - Quotes the runbook's table of contents so reviewers see the human-checklist shape at a glance.
  - Calls out the two [decisions.md](../../decisions.md) entries the user should append at merge time (laptop-gate deferral; human-checklist hand-off pattern).
  - Confirms in one line that the executing agent did *not* perform any of the human-only rehearsal steps.
- Once merged, the user appends the two decision entries to [decisions.md](../../decisions.md), tags `v0.8.0-demo` per [branching_strategy.md §8](../../branching_strategy.md), and fires the rehearsal runbook against a demo laptop when one is in use. The rehearsal log section of the runbook captures the post-rehearsal observations.
