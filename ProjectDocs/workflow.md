# ExpertView — Workflow

> How we develop in this repo. Pairs with [CLAUDE.md](../CLAUDE.md) (the operating guide for Claude Code itself). This document is the *expanded* version with rationale; CLAUDE.md is the terse enforcement copy.

## 1. The planning loop (per non-trivial task)

```
clarifying Q&A   →   plan file   →   user approval   →   implement   →   summarize + risks
```

1. **Clarifying questions** (3–4) via `AskUserQuestion` before any non-trivial work. Skip only for typo fixes, single-line changes, or trivial renames.
2. **Plan file**: list affected files, list new files, sketch the change, identify risks. For multi-file work, enter plan mode and write to `~/.claude/plans/<name>.md`.
3. **Wait for user approval** (`ExitPlanMode`). Do not start editing files before approval.
4. **Implement** in small commits, one module at a time. Write the interface (protocol / pydantic model) first, then the test, then the implementation.
5. **Summarize** what changed at the end of the turn — affected files, key decisions, and any deferred work.
6. **Report remaining risks** in the same summary. If a follow-up is required, name it explicitly.

## 2. Dev cycle (per feature)

- **Smallest unit of work**: one module or one cross-module contract.
- **Interface-first**: the protocol or pydantic model goes in before the implementation. This is how we keep module boundaries (see [architecture.md §5](architecture.md)) from rotting.
- **Test alongside, not after**: every new public function gets at least one test in `tests/unit/` before it is wired into the rest of the system.
- **Vertical slice over horizontal sweep**: prefer making one investigator + one corpus + the synthesizer work end-to-end (phase 2) over building all five investigators in isolation. End-to-end working code is the only kind of code that matters at the demo.

## 3. Quality gates (definition of done)

A task is **not done** until all of the following hold:

- Typed: all new public functions have type hints. Pydantic for cross-agent data.
- `uv run ruff check .` is clean.
- `uv run ruff format --check .` is clean.
- `uv run pytest` passes (only the new test or the relevant subset is acceptable during phase 1–3; full suite required by phase 4 onwards).
- If it is a feature: the end-to-end CLI demo still runs (`uv run python -m expertview.cli demo`) AND a LangSmith trace is visible for the run in the project dashboard.
- No debug prints, no commented-out code, no `# TODO` without an entry in [open_questions.md](open_questions.md) or [decisions.md](decisions.md).
- No new dependency added without an entry in [decisions.md](decisions.md) explaining why.

## 4. Verification (how Claude proves a change works)

- **For code logic**: `uv run pytest -k <test_name>`.
- **For lint/style**: `uv run ruff check .` + `uv run ruff format --check .`.
- **For end-to-end behavior**: the built-in `/verify` skill — actually run the demo, observe output.
- **For demo polish**: the built-in `/run` skill — drive the app, take a screenshot/transcript, confirm visible parallelism.

> Type-checking and tests verify *code correctness*, not *feature correctness*. Always run the demo before declaring a feature done.

## 5. Self-review (before declaring done)

- Run `/simplify` on the changed code to catch over-engineering, unnecessary abstractions, and duplication.
- Run `/review` on the diff to catch logic errors, missing tests, and unclear naming.
- Run `/security-review` before any commit that touches LLM provider code (`ChatOpenAI` pointed at OpenRouter, `HuggingFaceEmbeddings`), prompts, `agents/llms.py`, LangSmith key reads, or anything reading from `.env`.

## 6. Documentation discipline

- **Every locked decision** goes into [decisions.md](decisions.md) the same turn it is locked. Format: date, decision, why, alternatives considered, reversibility.
- **Every unresolved question** lives in [open_questions.md](open_questions.md). When a question is answered → resolve it (move the answer to `decisions.md`, delete the open question).
- **`project_introduction.md` is a living doc** — keep it aligned with the current framing. (The "immutable seed" rule was dropped 2026-05-26; see [decisions.md](decisions.md).)
- **`architecture.md` updates only by amendment.** Add a "Changes" section at the bottom if the protocols evolve materially; do not rewrite silently.

## 7. Branching, PRs, and commit hygiene

ExpertView uses the lightweight GitHub Flow documented in [branching_strategy.md](branching_strategy.md). The short version:

- `main` is stable and demo-ready.
- Work happens in short-lived `feature/*`, `fix/*`, `docs/*`, or `chore/*` branches.
- Changes merge through pull requests, even for solo work, because PRs act as review and documentation checkpoints.
- CI must pass before merge.
- Demo-ready states on `main` are marked with annotated release tags such as `v0.1.0-demo`.
- Do not introduce `develop`, `release/*`, or `hotfix/*` branches unless the project later has multiple maintained release lines.

- One logical change per commit. Module + its test in the same commit is fine.
- Commit message format: `<area>: <one-line summary>` then a body explaining *why* (not *what* — the diff shows the what). Example: `evidence: introduce CausalLink schema for cross-domain hypotheses`.
- Never commit `.env`, API keys, the local `.venv/`, `__pycache__/`, generated mock data >1MB, or model checkpoints.
- Never use `--no-verify`. If a hook fails, fix the underlying issue.

## 8. Claude Code assets available

### Built-in skills (already installed, use freely)

| Skill | When to use |
|---|---|
| `/verify` | After implementing any feature, before marking it done. |
| `/simplify` | Before declaring complex work done — catches over-engineering. |
| `/review` | Before committing a substantial diff. |
| `/security-review` | Before committing anything touching prompts, the LLM provider client (`ChatOpenAI` pointed at OpenRouter), `agents/llms.py`, LangSmith key reads, or `.env`. |
| `/run` | To launch the demo and confirm visible behavior. |
| `/update-config` | For `settings.json` / hooks changes — never edit `settings.json` by hand for risky changes. |
| `claude-api` | Auto-triggers on raw Anthropic SDK code paths (only relevant if a demo-path synthesizer ever drops below OpenRouter to the native SDK for prompt caching). Trust it for caching, model selection, and migration help. |

### Subagents to use proactively

- `Explore` — for "where is X" questions once `src/` grows past one file.
- `Plan` — for designing non-trivial modules (e.g., convergence, spawning).
- `general-purpose` — for multi-step research tasks where the steps are unknown ahead of time.

### Hooks (recommended, **not yet applied** — pending user approval)

These would live in `.claude/settings.local.json` and be applied via `/update-config`. They are written here as specs:

- **PostToolUse on `Edit` / `Write` for `*.py`** — run `uv run ruff format <file>` on the touched file. Deterministic style, zero willpower required.
- **PreToolUse on `Bash`** — block commands matching: `rm -rf`, `git push --force` to `main`/`master`, `uv remove`, any write touching `.env` (including writes that introduce or modify `OPENROUTER_API_KEY` or `LANGSMITH_API_KEY`).
- **Stop** — if any file under `src/expertview/agents/`, `src/expertview/rag/base.py`, `src/expertview/orchestration/state.py`, `src/expertview/orchestration/runner.py`, or `src/expertview/evidence/models.py` changed in this turn, print a one-line reminder to update [decisions.md](decisions.md).

### Skills *flagged for research later* (not installed)

These came from skill-marketplace research and are unverified. The user should review each before installing.

- `subagent-driven-development` — useful once we have ≥3 independent modules under active development.
- `systematic-debugging` — structured RCA for *our own* debugging.
- `context-optimization` — relevant if the hackathon imposes a token budget.
- `skill-creator` — if we end up wanting custom skills like `rca-investigator-prompt`.

## 9. Patterns worth promoting to custom skills (future)

Only build these if the pattern repeats ≥3 times across sessions:

- `rca-investigator-prompt` — generates an investigator prompt with consistent structure (require citations, declare confidence in [0,1], emit `Finding` schema).
- `domain-rag-seed` — scaffolds a new knowledge domain (data folder, mock corpus generator, embedding setup, loader entry).
- `agent-trace-replay` — replays a recorded agent run from a JSONL trace for debugging.

When a pattern crosses the ≥3-times threshold, note it in [open_questions.md](open_questions.md) under "skill candidates".

## 10. Decision-making meta-rules (when to ask vs. when to decide)

- **Always ask** when the question affects: cross-agent data shape, the public protocols, the demo scenario, the architecture rules in [architecture.md §5](architecture.md), or anything in the *Hard rules* section of [CLAUDE.md](../CLAUDE.md).
- **Decide and log** when the question is internal: helper function structure, file naming inside a module, test layout, log message wording.
- **Propose, do not apply** for hook changes, `settings.json` edits, dependency additions, or anything that affects the user's environment outside this repo.
