# ExpertView — Claude Code Operating Guide

## What this project is

**ExpertView** is a multi-agent Root Cause Analysis (RCA) system for industrial manufacturing incidents. Five domain investigators (mechanical, process, supply chain, environmental, human factors) run in parallel as LangGraph branches against domain-specific RAG stores, share evidence through the LangGraph shared state, spawn sub-investigations dynamically via conditional edges, and converge on an evidence-weighted causal report. Built on LangGraph + LangSmith, with Llama 3.3 70B (NIM) driving investigators, DeepSeek-R1 / Opus 4.7 driving the synthesizer (env-selected), and NV-Embed-v2 + NV-Rerank powering retrieval. **This is a pre-hackathon build** for the shapeX 1-day event — constructed in advance, brought to the event ready to demo, and also designed as a CV/portfolio asset.

## First things to read when starting a session

1. [ProjectDocs/vision.md](ProjectDocs/vision.md) — intent, users, success criteria, non-goals.
2. [ProjectDocs/architecture.md](ProjectDocs/architecture.md) — module map, protocols, data flow, tech stack.
3. [ProjectDocs/open_questions.md](ProjectDocs/open_questions.md) — what still needs the user's input.
4. If implementing this session, also read [ProjectDocs/build_plan.md](ProjectDocs/build_plan.md) for phase order + quality gates.
5. [ProjectDocs/decisions.md](ProjectDocs/decisions.md) — locked decisions and their reasons.

## Hard rules (never bypass)

- **Never edit `.env`.**
- **Never modify [ProjectDocs/project_introduction.md](ProjectDocs/project_introduction.md)** — it is the seed of truth.
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
- **LLM provider clients (`ChatAnthropic`, `ChatNVIDIA`) are instantiated only in `src/expertview/agents/llms.py`.** No LLM clients in `rag/`, `evidence/`, or `prompts/`. The factory honors `EXPERTVIEW_SYNTH_MODEL` to swap the synthesizer between `deepseek-r1` (build) and `opus-4-7` (demo).

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
| `/security-review` | Before commits touching prompts, LLM provider clients (`ChatAnthropic`, `ChatNVIDIA`), `agents/llms.py`, LangSmith key reads, or `.env` | Catches leaks + prompt-injection holes |
| `/run` | Demo rehearsals | Drives the app, confirms visible behavior |
| `/update-config` | For `settings.json` / hooks changes | Never edit `settings.json` by hand for risky changes |
| `claude-api` | Auto-triggers on Anthropic SDK code (relevant on the demo-time synthesizer path if it drops to raw SDK for caching) | Handles prompt caching, model selection |

Subagents: use `Explore` for "where is X" once `src/` grows past one file. Use `Plan` for designing non-trivial modules.

## Recommended additions (require user approval before applying)

- **Hooks** (specs in [ProjectDocs/workflow.md §8](ProjectDocs/workflow.md)): PostToolUse `ruff format` on touched `.py` files; PreToolUse Bash block on `rm -rf`, `git push --force` to main, `uv remove`, and any `.env` write touching `ANTHROPIC_API_KEY`, `NVIDIA_API_KEY`, or `LANGSMITH_API_KEY`; Stop reminder to update `decisions.md` if architecture-layer files changed.
- **Custom skills** (build only if pattern repeats ≥3 times): `rca-investigator-prompt`, `domain-rag-seed`, `agent-trace-replay`.

Propose, do not apply.

## Decision-making meta-rules

- **Stop and ask** when a question affects: cross-agent data shape, public protocols, the demo scenario, the architecture rules above, or any *Hard rule*.
- **Decide and log** for internal questions: helper structure, file naming inside a module, test layout, log message wording.
- **Propose, do not apply** for hook changes, `settings.json` edits, dependency additions, or anything affecting the user's environment outside this repo.

