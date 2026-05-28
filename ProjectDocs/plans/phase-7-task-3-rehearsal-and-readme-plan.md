# Plan — Phase 7 Task 3: Rehearsal Materials, Top-Level README, Human-Checklist Hand-Off

> Source task: [ProjectDocs/phases/phase-7/task-3-paid-synth-rehearsal-and-readme.md](../phases/phase-7/task-3-paid-synth-rehearsal-and-readme.md)
> Branch: `feature/phase-7-rehearsal-and-readme`
> Discretion already resolved with the user: **skip** helper scripts, **ship** the `doctor` CLI subcommand, **replace** the existing top-level README.

## Context

Phase 7 Tasks 1 and 2 are now on `main`. They ship the resilience (retry/backoff + deterministic seed + cache-invalidation docstring in `agents/llms.py`) and the offline fallback (`trace-export` / `replay` CLI subcommands + `data/traces/` artifact format) that the paid-synth rehearsal will lean on. What is missing is the user-facing surface that turns those capabilities into a one-sitting rehearsal: a top-level `README.md` (1-minute run-it-yourself guide), a copy-paste rehearsal runbook with the seven subsections the task spec calls for, and a thin `expertview doctor` pre-flight check the user fires before spending paid OpenRouter credit.

The executing agent does **not** perform the paid-synth swap, the three rehearsal runs, the live trace capture, or the watched observation — all four are human steps performed against the merged code per the 2026-05-27 deferral recorded in [ProjectDocs/phases/phase-7/README.md](../phases/phase-7/README.md). The agent also does **not** edit `decisions.md` or `open_questions.md` mid-task ([CLAUDE.md](../../CLAUDE.md) hard rules); two decision entries (Phase 7 laptop-gate deferral; human-checklist hand-off pattern) are flagged in the PR description for the user to append at merge time.

## Files affected

**New:**
- `README.md` — overwrite the existing 28-line workflow-flavored README with the 1-minute run-it-yourself guide (workflow content already lives in `CONTRIBUTING.md` + `ProjectDocs/branching_strategy.md`; nothing is lost).
- `ProjectDocs/runbooks/phase-7-rehearsal.md` — the human checklist. Establishes the new `ProjectDocs/runbooks/` subfolder.
- `tests/unit/test_doctor.py` — minimal coverage for each `doctor` check against fakes (no live HTTP, no real embedding load in CI).
- `ProjectDocs/plans/phase-7-task-3-rehearsal-and-readme-plan.md` — this plan file, per the established [phase-7-task-1 plan](phase-7-task-1-llm-hardening-plan.md) precedent.

**Edit:**
- `src/expertview/cli.py` — add the `doctor` subparser + handler.

**Not touched (architecture walls / hard rules):**
- No edits in `agents/`, `evidence/`, `orchestration/`, `rag/`, `prompts/`, `ui/`.
- No new dependency in `pyproject.toml`.
- No edits to `decisions.md` or `open_questions.md`.
- No new prompt files.

## `README.md` shape

Replace the existing file. Match the matter-of-fact tone of `project_introduction.md`. Sections: project description (one paragraph), Requirements, Environment variables table (`OPENROUTER_API_KEY` required, `LANGSMITH_API_KEY` recommended, `LANGSMITH_PROJECT` + `EXPERTVIEW_SYNTH_MODEL` optional), Run it (three commands), Offline replay, Pre-flight check, Demo rehearsal pointer, Documentation map.

## `ProjectDocs/runbooks/phase-7-rehearsal.md` shape

Eight sections: pre-flight (env + doctor run), warm-up runs (both incidents on free build synth), paid-synth swap (three runs — two CLI + one Streamlit), trace export (capture the Streamlit run, write under `data/traces/`), replay sanity check, watched observation (four-question colleague check), what to do when X happens (429 / outage / off-script question), rehearsal log table.

Every command is a fenced PowerShell block with bracketed placeholders. The paid frontier ID is illustrative (`anthropic/claude-opus-4.7`); the runbook directs the user to check the OpenRouter catalog at rehearsal time.

## `expertview doctor` subcommand

Eight checks (one row per check, rendered in a Rich `Table`):

1. `OPENROUTER_API_KEY` set (required).
2. `LANGSMITH_API_KEY` set (required).
3. `EXPERTVIEW_SYNTH_MODEL` introspection (informational, never fails).
4. Incident YAMLs parse — both `data/incidents/{cnc_out_of_tolerance,process_recipe_drift}.yaml` validate as `Incident`.
5. Streamlit imports — `streamlit` + `streamlit_mermaid` available.
6. Embedding round-trip — `create_embeddings().embed_query("ping")` returns a non-empty vector. **Skippable via `--skip-embedding`.**
7. LangSmith connectivity — `LangSmithClient().list_projects(limit=1)` succeeds. **Skippable via `--skip-langsmith`.**
8. Trace subcommands registered — parser introspection (no subprocess) confirms `trace-export` and `replay` are present.

Exit `0` if every non-skipped non-informational check passes; `1` otherwise. Failed checks listed in red after the table.

## Tests (offline, deterministic)

`tests/unit/test_doctor.py`:

1. `test_doctor_passes_with_full_environment` — happy path with fakes for embedding + LangSmith.
2. `test_doctor_fails_without_openrouter_key` — clear env; assert exit 1 + check #1 fail.
3. `test_doctor_fails_without_langsmith_key_but_keeps_other_rows_passing` — partial fail.
4. `test_doctor_reports_missing_incident_yaml` — monkeypatch `_DOCTOR_INCIDENT_PATHS` to a non-existent path; assert fail row mentions the path.
5. `test_doctor_skips_embedding_when_flag_set` — assert `create_embeddings` is not called.
6. `test_doctor_skips_langsmith_when_flag_set` — assert `LangSmithClient` is not constructed.
7. `test_doctor_detects_missing_trace_subcommands` — monkeypatch `_build_parser` to a stripped parser; assert fail row mentions both `trace-export` and `replay`.
8. `test_doctor_reports_embedding_failure_with_exception_class` — embedding raises; assert detail carries the exception class name.

All tests use `MonkeyPatch`; no live HTTP, no real model download.

## Quality gates

```powershell
uv run pytest tests/unit/test_doctor.py -v
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m expertview.cli doctor --help
uv run python -m expertview.cli demo --help
uv run python -m expertview.cli trace-export --help
uv run python -m expertview.cli replay --help
```

The pre-existing 4 integration failures from Task 2's PR (`test_demo_end_to_end`, `test_parallel_fanout`, `test_dynamic_spawning x2`) are unrelated to this task's surface; PR description acknowledges them.

## decisions.md entries (flagged for user-append at merge time)

1. **Phase 7 laptop-gate deferral** — referencing the 2026-05-27 direction. The "three consecutive clean runs on the actual demo laptop" portion of the quality gate is deferred to a post-merge human checklist; Tasks 1–3 closed the automatable scope; the human rehearsal is downstream of the `v0.8.0-demo` tag.
2. **Human-checklist hand-off pattern** — the runbook + README + doctor combination is the template for any future phase whose quality gate has a human-only step the executing agent cannot perform.

## Risks

- **Doctor depth creep.** Each check is one small tuple-returning function (≤10 LOC of logic). The runner sums to ~60 LOC.
- **Runbook drift from code.** Mitigation: every quoted command verified via `--help`; doctor's check #8 catches subcommand drift; the runbook leans on `data/traces/README.md` for the artifact schema rather than restating it.
- **Paid frontier model ID rot.** Mitigation: runbook calls the OpenRouter catalog link the source of truth; the model ID in the runbook is illustrative.
- **Test embedding-check pulling the real model.** Mitigation: tests monkeypatch `cli.create_embeddings`.

## Out of scope

- No edits to `agents/`, `evidence/`, `orchestration/`, `rag/`, `prompts/`, `ui/`.
- No new dependency.
- No edits to `decisions.md` or `open_questions.md`.
- No helper scripts under `scripts/`.
- No paid-synth call by the executing agent.
- No live rehearsal run, trace capture, or `v0.8.0-demo` tag by the executing agent.
