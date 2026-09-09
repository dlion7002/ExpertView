# ExpertView — Agent Operating Guide

## What this project is

**ExpertView** is a multi-agent Root Cause Analysis (RCA) system for industrial manufacturing incidents, built as a **CV/portfolio asset** that demonstrates production-shaped multi-agent engineering (parallel branches, dynamic spawning, evidence-weighted convergence) on industry-standard tooling. Five domain investigators (mechanical, process, supply chain, environmental, human factors) run in parallel as LangGraph branches against domain-specific RAG stores, share evidence through the LangGraph shared state, spawn sub-investigations dynamically via conditional edges, and converge on an evidence-weighted causal report. Built on LangGraph + LangSmith, with LLMs routed through **OpenRouter** via an OpenAI-compatible client — `openrouter/owl-alpha` (free) for the parallel investigators, `deepseek/deepseek-v4-flash:free` for the build-phase synthesizer, and a paid frontier model (e.g. `anthropic/claude-opus-4.7`) for the demo synthesizer — and embeddings running locally via `BAAI/bge-small-en-v1.5`. The shapeX 1-day hackathon is a milestone the build also targets, but the primary success measure is interview/hiring legibility for AI-platform roles.

## First things to read when starting a session

1. [ProjectDocs/vision.md](ProjectDocs/vision.md) — intent, users, success criteria, non-goals.
2. [ProjectDocs/architecture.md](ProjectDocs/architecture.md) — module map, protocols, data flow, tech stack.
3. [ProjectDocs/open_questions.md](ProjectDocs/open_questions.md) — what still needs the user's input.
4. If implementing this session, also read [ProjectDocs/build_plan.md](ProjectDocs/build_plan.md) for phase order + quality gates.
5. [ProjectDocs/decisions.md](ProjectDocs/decisions.md) — locked decisions and their reasons.

## Hard rules (never bypass)

- **Never edit `.env`.**
- **Never change dependencies in `pyproject.toml`** without an entry in [ProjectDocs/decisions.md](ProjectDocs/decisions.md) explaining why.
- **Never bypass tests, hooks, or lint** with `--no-verify`, `--no-gpg-sign`, or similar flags.
- **Never commit** secrets, API keys, the local `.venv/`, `__pycache__/`, generated mock data >1MB, or model checkpoints.
- **Never inline an investigator or synthesizer prompt** in agent code — prompts live as versioned files under `src/expertview/prompts/`.

## Workflow rules

1. **Ask 3–8 clarifying questions** before any non-trivial work, via `AskUserQuestion`. Skip only for typo fixes / single-line changes / trivial renames.
2. **For non-trivial tasks, write a plan file before editing.** List affected files, list new files, sketch the change, identify risks.
3. **Wait for user approval** (`ExitPlanMode`) before editing.
4. **After implementing**: summarize what changed, name affected files, report remaining risks, and note any pattern that has now repeated ≥3 times (skill candidate).
5. **Log every locked decision** in [ProjectDocs/decisions.md](ProjectDocs/decisions.md) the same turn it is locked.
6. **Drain [ProjectDocs/open_questions.md](ProjectDocs/open_questions.md)** as questions are resolved — move the answer into `decisions.md`, delete the open question.

## Coding standards (Python)

- Type hints on every public function.
- Pydantic v2 models for all cross-agent data (Finding, Hypothesis, CausalLink, CausalReport, Incident, Document). Never raw dicts across module boundaries. The LangGraph `ExpertViewState` (TypedDict) is the one allowed non-pydantic cross-node type and lives in `orchestration/state.py`.
- `uv run ruff format` and `uv run ruff check .` must be clean before declaring done.
- **No fallbacks or defensive code for cases that can't happen.** Trust internal contracts. Validate only at system boundaries (CLI input, LLM responses parsed against pydantic).
- **No comments that restate the code.** Only WHY-comments for non-obvious constraints, workarounds, or hidden invariants.
- No debug prints, no commented-out code, no `# TODO` without an entry in `open_questions.md` or `decisions.md`.

## Architecture rules

- **Agents communicate only via the LangGraph shared state.** No direct calls between investigators. The synthesizer is the sole reader of the final state snapshot. State schema lives in `src/expertview/orchestration/state.py` as `ExpertViewState`.
- **LangGraph nodes are pure async functions `(State) -> dict`** returning state patches. No side effects outside the returned patch and explicit LangSmith spans.
- **RAG stores expose only the `KnowledgeStore` protocol.** Extend the protocol if a caller needs more; never reach into implementation internals.
- **Synthesizer is side-effect-free.** The synthesizer node calls an LLM and returns `{"causal_report": CausalReport(...)}` — nothing else. No state writes outside the patch, no disk writes, no spawning.
- **Module boundaries are walls.** A file in `rag/` does not import from `agents/`. A file in `evidence/` does not import from `orchestration/`. Test files are the only exception.
- **LLM provider clients (`ChatOpenAI` pointed at OpenRouter, `HuggingFaceEmbeddings`) are instantiated only in `src/expertview/agents/llms.py`.** No LLM clients in `rag/`, `evidence/`, or `prompts/`. The factory honors `EXPERTVIEW_SYNTH_MODEL` to swap the synthesizer between OpenRouter model IDs (e.g. `deepseek/deepseek-v4-flash:free` for build, `anthropic/claude-opus-4.7` for demo).

## Verification commands

```powershell
uv run pytest                                    # unit + integration tests
uv run ruff check .                              # lint
uv run ruff format --check .                     # format check
uv run python -m expertview.cli demo             # end-to-end demo scenario (once implemented)
```

PowerShell on Windows is the user's shell — prefer `$null` not `/dev/null`, `$env:VAR` not `$VAR`. Bash is also available via the Bash tool for POSIX scripts.

## Built-in skills to lean on

| Skill | When | Why |
|---|---|---|
| `/verify` | After every feature, before declaring done | Forces actually running the code |
| `/simplify` | Before declaring complex work done | Catches over-engineering |
| `/review` | Before committing a substantial diff | Catches logic + naming issues |
| `/security-review` | Before commits touching prompts, the LLM provider client (`ChatOpenAI` pointed at OpenRouter), `agents/llms.py`, LangSmith key reads, or `.env` | Catches leaks + prompt-injection holes |
| `/run` | Demo rehearsals | Drives the app, confirms visible behavior |
| `/update-config` | For `settings.json` / hooks changes | Never edit `settings.json` by hand for risky changes |
| `claude-api` | Auto-triggers on raw Anthropic SDK code (only relevant if a demo-path synthesizer ever drops below OpenRouter to the native SDK for prompt caching) | Handles prompt caching, model selection |

Subagents: use `Explore` for "where is X" once `src/` grows past one file. Use `Plan` for designing non-trivial modules.

## Recommended additions (require user approval before applying)

- **Hooks** (specs in [ProjectDocs/workflow.md §8](ProjectDocs/workflow.md)): PostToolUse `ruff format` on touched `.py` files; PreToolUse Bash block on `rm -rf`, `git push --force` to main, `uv remove`, and any `.env` write touching `OPENROUTER_API_KEY` or `LANGSMITH_API_KEY`; Stop reminder to update `decisions.md` if architecture-layer files changed.
- **Custom skills** (build only if pattern repeats ≥3 times): `rca-investigator-prompt`, `domain-rag-seed`, `agent-trace-replay`.

Propose, do not apply.

## Decision-making meta-rules

- **Stop and ask** when a question affects: cross-agent data shape, public protocols, the demo scenario, the architecture rules above, or any *Hard rule*.
- **Decide and log** for internal questions: helper structure, file naming inside a module, test layout, log message wording.
- **Propose, do not apply** for hook changes, `settings.json` edits, dependency additions, or anything affecting the user's environment outside this repo.


