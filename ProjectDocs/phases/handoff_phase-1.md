# Handoff — ExpertView Phase 1 Planning Breakdown

**Date**: 2026-05-25
**Repo**: `c:\AAMisArchivos\AAprogramming\AI-Sysems\ExpertView`
**Branch at handoff**: `main` (clean — only doc writes this session, no commits made)
**Outgoing model**: Opus 4.7

## What this session produced

Created a new planning folder breaking ExpertView's Phase 1 ("Skeleton + contracts") into agent-executable task files. The breakdown is the *scope* surface for downstream coding agents; it tells them *what* to build, not *how* — implementation choices stay with the executing agent per the user's instruction.

**New files in repo (all under `ProjectDocs/phases/phase-1/`)**:

- `README.md` — index, dependency graph, parallelism rationale, usage instructions
- `task-1-project-bootstrap.md` — pyproject.toml + `.env.example` + `src/expertview/` skeleton + `tests/` skeleton + `data/` placeholders. **Sequential, blocks all.** Branch `chore/project-bootstrap`.
- `task-2-evidence-models-and-state.md` — pydantic models in `evidence/models.py` + `ExpertViewState` TypedDict (with `operator.add` reducers) in `orchestration/state.py` + schema round-trip tests. **Sequential, blocks Tasks 3/4/5.** Branch `feature/evidence-state-schemas`.
- `task-3-rag-skeleton.md` — `KnowledgeStore` protocol + `InMemoryVectorStore` wrapper. **Parallelizable.** Branch `feature/rag-skeleton`.
- `task-4-agents-skeleton-and-llms.md` — `Investigator`/`Synthesizer` protocols + the sole-site LLM factory honoring `EXPERTVIEW_SYNTH_MODEL` + env-gated provider-key integration test. **Parallelizable.** Branch `feature/agents-llms`.
- `task-5-orchestration-runner-skeleton.md` — `make_graph()` compiling a `StateGraph` with one placeholder node + LangSmith tracing wired (no-op without keys). **Parallelizable.** Branch `feature/orchestration-skeleton`.

Dependency shape: `Task 1 → Task 2 → {Task 3, Task 4, Task 5 in parallel} → phase quality gate → tag v0.2.0-demo`.

## Decisions made this session (not yet logged in decisions.md — they are *planning* decisions, not architecture decisions)

User answered four clarifying questions via `AskUserQuestion`:

1. Planning folder location: `ProjectDocs/phases/phase-1/`.
2. Granularity: per logical module, ~5 tasks.
3. Branch mapping: each task suggests a branch, but not every task needs its own — agent may consolidate.
4. Index file: yes, README.md with dependency graph.

These are workflow choices, not architecture choices, so per `workflow.md §6` they did not require entries in `decisions.md`. If the next planning session for Phase 2 wants to deviate (e.g., different folder pattern), they are free to.

## Source-of-truth documents the next agent should read first

Do not duplicate; read these directly. They are the canonical inputs for both execution-of-Phase-1 and planning-of-Phase-2 work:

1. `CLAUDE.md` — operating guide; hard rules, workflow rules, architecture rules.
2. `ProjectDocs/build_plan.md` — the canonical phase definitions and quality gates. Phase 1 in §"Phase 1 — Skeleton + contracts"; Phase 2 in §"Phase 2 — Vertical slice".
3. `ProjectDocs/architecture.md` — module map (§2), key interfaces sketch (§3), data flow diagram (§4), architecture rules (§5), tech stack (§7).
4. `ProjectDocs/decisions.md` — every locked architectural choice with `Why` + `Reversibility`. The 2026-05-25 batch is what unblocked Phase 1.
5. `ProjectDocs/open_questions.md` — currently *empty* of active questions (all Phase 0 questions resolved or deferred). New questions during phase 1+ get appended here.
6. `ProjectDocs/workflow.md` — planning loop, quality gates, doc discipline.
7. `ProjectDocs/branching_strategy.md` — lightweight GitHub Flow; this is what the task files' branch suggestions reference.
8. `ProjectDocs/phases/phase-1/README.md` — start here for the Phase 1 task table + dependency graph.

## What the next agent should do

### If the next agent is **executing a Phase 1 task**

1. Open `ProjectDocs/phases/phase-1/README.md` and pick the next unblocked task from the table.
2. Read that task file end-to-end before doing anything.
3. Follow the planning loop in `workflow.md §1`: clarifying Q&A (3–8 questions via `AskUserQuestion`) → plan file → user approval (`ExitPlanMode`) → implement → summarize. The task file is the *scope*, not the plan; the executing agent still owns the plan.
4. **Task 1 is the only currently-unblocked task** — Tasks 2–5 depend on Task 1 being merged.
5. Open a PR per the lightweight GitHub Flow when done.

### If the next agent is **breaking down Phase 2**

1. Read Phase 2 in `ProjectDocs/build_plan.md` (the vertical slice — ONE investigator + ONE corpus + synthesizer → end-to-end CLI → CausalReport → LangSmith trace). It is structurally different from Phase 1: it is the *first* end-to-end execution, includes the CNC out-of-tolerance scenario (locked 2026-05-25), and includes mock-corpus authoring.
2. Reuse the same folder pattern: `ProjectDocs/phases/phase-2/` with `README.md` + N task files.
3. Likely natural breakdown for Phase 2 (sketch only — the executing agent should re-derive from `build_plan.md`):
   - Mock corpus authoring (`data/domains/mechanical/*.md` — Claude drafts + hand curation per `decisions.md` 2026-05-25 Q4)
   - Incident scenario YAML (`data/incidents/cnc_out_of_tolerance.yaml`)
   - Mechanical RAG loader (`rag/domains/mechanical.py` — uses Task 3's `InMemoryKnowledgeStore` + Task 4's `NVIDIAEmbeddings`)
   - Mechanical investigator node + prompt file
   - Synthesizer node + prompt file (DeepSeek-R1 path)
   - Real `make_graph()` wiring + CLI entry point
   - End-to-end verification with `/verify` skill
4. Ask the user clarifying questions before starting — folder location is already established (`ProjectDocs/phases/`), granularity and branch-mapping conventions may still be worth confirming for Phase 2's shape.
5. Phase 2 has more cross-file coupling than Phase 1 (the corpus, the loader, the investigator, the prompt, and the synthesizer all need to align to produce a coherent report). Sequential pinch points will be heavier than in Phase 1's clean fan-out.

## State of the repo

- `git status` at handoff start showed: modified `AGENTS.md`, `ProjectDocs/decisions.md`, `ProjectDocs/workflow.md`; untracked `.github/`, `.gitignore`, `CONTRIBUTING.md`, `ProjectDocs/branching_strategy.md`, `README.md`. **None of these were touched this session.** They are pre-existing state from prior sessions.
- This session added `ProjectDocs/phases/phase-1/` (untracked). No commits were made — the user has not authorized committing.
- The `src/expertview/` package does not yet exist. The repo is still in Phase 0 → Phase 1 transition; Task 1 will be the first task that creates Python source.

## Open / deferred items

- `ProjectDocs/open_questions.md` currently has **no active questions**.
- Q5 (Anthropic spend cap + NIM quota tracking) is *formally deferred* per `decisions.md` 2026-05-25; revisit at the end of phase 5 (or earlier if NIM quota strains).
- The recommended hooks in `workflow.md §8` (PostToolUse ruff format, PreToolUse Bash block on destructive ops, Stop reminder on architecture-layer edits) are still *proposals* — the user has not authorized application. Mention them if the user asks about workflow automation.

## Suggested skills for the next agent

- **If executing Task 1**: no special skills — just the planning loop in `workflow.md`.
- **If executing Task 2**: run `/review` before opening the PR (pydantic schemas + reducer wiring deserve a second look).
- **If executing Task 3**: run `/simplify` before opening the PR (protocol over-engineering risk is real).
- **If executing Task 4**: **`/security-review` is mandatory** per `CLAUDE.md` because the task touches `agents/llms.py`, env-var reads, and LLM provider clients. Also relevant: `claude-api` skill auto-triggers on Anthropic SDK code paths.
- **If executing Task 5**: run `/verify` after — the LangGraph compile is the Phase 1 quality gate; prove it by running it.
- **If breaking down Phase 2**: use `AskUserQuestion` early; consider `Plan` subagent for the mock-corpus + investigator + synthesizer triangle, which is more interconnected than any Phase 1 task.
- **General**: `handoff` skill (this one) again at the end of the next session.

## Things that surprised me / worth knowing

- The user's project framing changed *during* Phase 0 (2026-05-25): the build was reframed as a CV/portfolio asset for ReshapeX in addition to a hackathon entry. That reframe is what unlocked the LangGraph + LangSmith adoption and the multi-provider model split. Future planning should respect both axes — hiring signal *and* hackathon demo legibility.
- During-build cost discipline: free-tier NIM stack (Llama 3.3 70B + DeepSeek-R1 + NV-Embed-v2 + NV-Rerank) for everything; Anthropic Opus 4.7 reserved for the demo and the final Phase 7 rehearsal. The `EXPERTVIEW_SYNTH_MODEL` env var is the swap mechanism. Do **not** silently default to Anthropic during build — that breaks user feedback memory `feedback_free_tier_first_paid_for_demo`.
- The user's auto-memory notes the project is currently described as "phase 0 docs complete after 2026-05-25 CV-signal reframe; phase 1 blocked on Q1 (UI) + Q2 (demo incident)" — that memory is **stale**: Q1 and Q2 were resolved 2026-05-25 (Streamlit + CNC scenario locked), so Phase 1 is unblocked. The next agent should update memory accordingly when relevant.

## Verification commands (for the executing agent)

```powershell
uv run pytest                                    # unit + integration tests
uv run ruff check .                              # lint
uv run ruff format --check .                     # format check
uv run python -c "from expertview.orchestration.runner import make_graph; make_graph()"   # Phase 1 quality gate compile check (Task 5 must be merged first)
```

PowerShell on Windows is the user's primary shell. Bash is available via the Bash tool for POSIX scripts.