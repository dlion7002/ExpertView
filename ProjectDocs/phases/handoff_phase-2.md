# Handoff — ExpertView Phase 2 Planning Breakdown

**Date**: 2026-05-26
**Repo**: `c:\AAMisArchivos\AAprogramming\AI-Sysems\ExpertView`
**Branch at handoff**: `feature/orchestration-skeleton` (Phase 1 Task 5, not yet merged via PR)
**Outgoing model**: Opus 4.7
**Shell**: PowerShell on Windows 11 (Bash tool also available)

## What this session produced

Created `ProjectDocs/phases/phase-2/` — six new files breaking Phase 2 ("Vertical slice") into agent-executable task files. Same pattern the prior session used for Phase 1.

All six files are **untracked / uncommitted**. No git operations were performed this session.

| File | Role |
|---|---|
| [README.md](../../../../../AAMisArchivos/AAprogramming/AI-Sysems/ExpertView/ProjectDocs/phases/phase-2/README.md) | Index, dependency graph, parallelism rationale, pre-flight |
| [task-1-data-authoring.md](../../../../../AAMisArchivos/AAprogramming/AI-Sysems/ExpertView/ProjectDocs/phases/phase-2/task-1-data-authoring.md) | Mechanical corpus + CNC incident YAML. **Sequential, blocks 2 and 5.** |
| [task-2-mechanical-rag-loader.md](../../../../../AAMisArchivos/AAprogramming/AI-Sysems/ExpertView/ProjectDocs/phases/phase-2/task-2-mechanical-rag-loader.md) | `rag/domains/mechanical.py` loader + disk cache. **Parallelizable.** |
| [task-3-mechanical-investigator.md](../../../../../AAMisArchivos/AAprogramming/AI-Sysems/ExpertView/ProjectDocs/phases/phase-2/task-3-mechanical-investigator.md) | LangGraph node factory + prompt file. **Parallelizable.** |
| [task-4-synthesizer.md](../../../../../AAMisArchivos/AAprogramming/AI-Sysems/ExpertView/ProjectDocs/phases/phase-2/task-4-synthesizer.md) | Terminal node factory + prompt file. **Parallelizable.** |
| [task-5-runner-cli-wiring.md](../../../../../AAMisArchivos/AAprogramming/AI-Sysems/ExpertView/ProjectDocs/phases/phase-2/task-5-runner-cli-wiring.md) | Real `make_graph()` + `cli.py` + `/verify` as DoD. **Sequential.** |

Dependency shape: `Task 1 → {Task 2, Task 3, Task 4 in parallel} → Task 5 → phase quality gate → tag v0.3.0-demo`.

## Planning decisions made this session

User answered four clarifying questions via `AskUserQuestion`, picking the **recommended option in all four**:

1. **5 tasks** (consolidated) rather than 7 atomic or 4 heavy.
2. **Prompts bundled with their node tasks** (investigator prompt ships with Task 3; synthesizer prompt with Task 4).
3. **Data first, then parallel pipeline, then wiring** — mirrors Phase 1's fan-out shape.
4. **/verify rolled into Task 5's DoD** rather than a standalone task.

These are *planning* choices, not architectural choices, so they live only in the task files (no `decisions.md` entry needed, matching the precedent from the Phase 1 handoff).

## Pre-existing state I did not touch

The repo had these uncommitted changes at session start (left untouched):

- Modified: `.env.example`, `AGENTS.md`, `CLAUDE.md`, `ProjectDocs/architecture.md`, `ProjectDocs/build_plan.md`, `ProjectDocs/decisions.md`, `ProjectDocs/open_questions.md`, `ProjectDocs/phases/handoff_phase-1.md`, `ProjectDocs/phases/phase-1/task-1-project-bootstrap.md`, `ProjectDocs/phases/phase-1/task-3-rag-skeleton.md`, `ProjectDocs/phases/phase-1/task-4-agents-skeleton-and-llms.md`, `ProjectDocs/project_introduction.md`, `ProjectDocs/vision.md`, `ProjectDocs/workflow.md`, `pyproject.toml`, `src/expertview/agents/llms.py`, `tests/integration/test_provider_keys.py`, `tests/unit/test_runner_skeleton.py`, `uv.lock`
- Untracked: `ProjectDocs/Guides/`, `tests/conftest.py`

If any of these matter for the next agent's task, they should ask the user before touching them.

## Source-of-truth documents the next agent should read first

Read these directly — do not re-summarise them, they are the canonical inputs:

1. `CLAUDE.md` — operating guide; hard rules, workflow rules, architecture rules.
2. `ProjectDocs/build_plan.md` — Phase 2 verbatim in §"Phase 2 — Vertical slice".
3. `ProjectDocs/architecture.md` — module map (§2), key interfaces (§3), architecture rules (§5).
4. `ProjectDocs/decisions.md` — 2026-05-25 batch + 2026-05-26 OpenRouter pivot.
5. `ProjectDocs/phases/phase-2/README.md` — start here for the Phase 2 task table.
6. `ProjectDocs/phases/handoff_phase-1.md` — the prior session's handoff (Phase 1 planning context).
7. `ProjectDocs/phases/phase-1/README.md` — Phase 1 task table; helpful for the Phase 1 → 2 ordering.

## What the next agent should do

### If the next agent is **executing a Phase 2 task**

1. **Confirm Phase 1 Task 5 is merged first.** The current branch `feature/orchestration-skeleton` carries Phase 1's runner skeleton — its PR must hit `main` before Phase 2 Task 5 starts. Tasks 1–4 are unblocked once `main` has the `v0.2.0-demo` tag.
2. Open `ProjectDocs/phases/phase-2/README.md` and pick the next unblocked task from the table.
3. Read that task file end-to-end before doing anything.
4. Follow the planning loop in `workflow.md §1`: clarifying Q&A (3–8 questions via `AskUserQuestion`) → plan file → user approval (`ExitPlanMode`) → implement → summarize. The task file is the *scope*, not the plan; the executing agent still owns the plan.
5. **Task 1 (data authoring) is the only currently-unblocked task** once Phase 1 fully merges — Tasks 2–5 depend on Task 1.
6. Open a PR per the lightweight GitHub Flow when done.

### If the next agent is **breaking down Phase 3**

Use the same folder pattern: `ProjectDocs/phases/phase-3/` with `README.md` + N task files. Phase 3 is "Parallel fan-out" — the four remaining domain investigators + the dispatcher's `Send` API body. Likely natural breakdown: 1 task per domain (process, supply_chain, environmental, human_factors) + 1 task for the dispatcher rewrite + 1 wiring/verify task. Five tasks is probably right; six if the four-corpora authoring is split from the four investigator nodes.

### If the next agent is **doing anything else**

Read this whole handoff plus `CLAUDE.md` first. ExpertView has tight workflow rules (clarifying questions, plan-before-edit, decisions log discipline). The user enforces them.

## Suggested skills

Per the patterns in `CLAUDE.md` and what each Phase 2 task touches:

| Task being executed | Skills to invoke | Why |
|---|---|---|
| Task 1 (data authoring) | none mandatory; `/simplify` if the YAML helpers grow | Mostly content authoring; minimal code |
| Task 2 (RAG loader) | `/simplify` before PR | Protocol + cache combined → over-engineering risk |
| Task 3 (mechanical investigator) | `/security-review` | Per `CLAUDE.md`: triggers on prompt files |
| Task 4 (synthesizer) | `/security-review`; `claude-api` if you drop to native Anthropic SDK (not expected in Phase 2) | Same prompt-touching rule; `EXPERTVIEW_SYNTH_MODEL` swap path matters here |
| Task 5 (wiring + CLI + /verify) | **`/verify` is the DoD itself**; `/run` for rehearsal; `/review` before opening PR | Quality gate is "actually run it end-to-end" |
| Breaking down Phase 3 | `AskUserQuestion` early; `Plan` subagent if the dispatcher rewrite gets gnarly | Mirrors this session's pattern |
| End of next session | `handoff` skill again | Pattern continuity |

The `Explore` subagent is useful once `src/expertview/` grows (it has `agents/`, `evidence/`, `orchestration/`, `prompts/`, `rag/` now plus an active feature branch).

## Things that surprised me / worth knowing

- **The phase-breakdown pattern has now repeated twice** (Phase 1 prior session, Phase 2 this session). If Phase 3's breakdown follows the same shape, it crosses the `≥3` threshold from `CLAUDE.md` for a custom skill candidate (`phase-task-breakdown` or similar). Flag this to the user *before* writing the skill — `CLAUDE.md` says recommended additions require user approval.
- **The investigator vs. node-factory shape mismatch is intentional and called out in Task 3.** `agents/base.py`'s `Investigator.investigate(incident, prior_findings) -> list[Finding]` protocol is *not* the LangGraph node signature. Phase 2's investigator is a node factory that wraps the protocol's behavior in an async `(State) -> dict` shape. Don't "fix" this discrepancy — the task file explains it.
- **The Synthesizer protocol takes `(hypotheses, findings)` but Phase 2 state has no upstream hypotheses.** Task 4 calls this out explicitly — the synthesizer derives hypotheses internally as part of building the `CausalReport`. The protocol's two-arg shape becomes useful in Phase 5 (convergence) when investigator-emitted hypotheses might also appear on state.
- **Task 5 pre-wires a no-op `dispatcher` node** so Phase 3 only modifies the dispatcher body (with `Send(...)` calls), not the graph shape. This is intentional pre-wiring, not over-engineering — the task file says so.
- **The Bash tool on this Windows environment returns POSIX-style paths** (`/tmp` etc., via the Git-for-Windows Bash). The actual Windows temp resolves via `cygpath` from `mktemp -u`. The PowerShell tool returned exit-1 on bare `$env:TEMP` in this session — Bash with `cygpath` was the working escape hatch. The handoff doc is written to `C:\Users\jacob\AppData\Local\Temp\` via the Write tool directly.
- **User's auto-memory `project_expertview` says "phase 1 blocked on Q1 + Q2"** — that memory is stale (Q1/Q2 resolved 2026-05-25, Phase 1 has shipped Tasks 1–4 with Task 5 on a feature branch). Prior handoff already flagged this; worth updating when relevant.
- **Free-tier-first is a load-bearing user preference** (`feedback_free_tier_first_paid_for_demo`). Phase 2 must run on `openrouter/owl-alpha` (investigator) + `deepseek/deepseek-v4-flash:free` (build synthesizer). The paid frontier ID only enters at Phase 7 rehearsal and demo time. Burning the $5 OpenRouter credit during build violates this.

## State of the repo (snapshot)

- Phase 1 progress (per `git log`): Tasks 1, 2, 3, 4 merged to `main`. Task 5 (orchestration runner skeleton) sits on `feature/orchestration-skeleton` as commit `fb35a74`, not yet merged.
- `src/expertview/` package skeleton: `agents/` (with `investigators/` subdir, `base.py`, `llms.py`), `evidence/models.py`, `orchestration/state.py` + `runner.py` (placeholder), `prompts/investigator/` + `prompts/synthesizer/` (empty), `rag/base.py` + `rag/inmemory.py`.
- `data/domains/` and `data/incidents/` directories exist (empty) — Phase 2 Task 1 fills them.
- No `.env` write attempts this session. No secrets touched.

## Verification commands (for the next agent)

```powershell
uv run pytest                                    # unit + integration tests
uv run ruff check .                              # lint
uv run ruff format --check .                     # format check
uv run python -c "from expertview.orchestration.runner import make_graph; make_graph()"   # Phase 1 quality gate compile check
```

Phase 2's quality-gate command, once Task 5 is implemented:

```powershell
uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml
```

## Open / deferred items

- `ProjectDocs/open_questions.md` was not touched this session — should still be empty of active questions (the Phase 1 handoff confirmed that).
- Hook proposals from `workflow.md §8` (PostToolUse ruff format, PreToolUse Bash block on destructive ops, Stop reminder on architecture-layer edits) remain unapproved — mention them only if the user asks about workflow automation.
- The 6 new files in `ProjectDocs/phases/phase-2/` are untracked. The user has not authorised committing them — ask before `git add`.
