# Task 1 — Process Domain Bundle

> **Branch suggestion**: `feature/process-domain`
> **Parallelism**: **Parallelizable with Tasks 2, 3, 4.** No shared editing surface with the other domain bundles.
> **Depends on**: Phase 2 complete (mechanical bundle merged, `v0.3.0-demo` tagged). Reuses `evidence/models`, `agents/base`, `agents/llms`, `rag/base`, and the patterns from [`rag/domains/mechanical.py`](../../../src/expertview/rag/domains/mechanical.py), [`prompts/investigator/mechanical.md`](../../../src/expertview/prompts/investigator/mechanical.md), and [`agents/investigators/mechanical.py`](../../../src/expertview/agents/investigators/mechanical.py).

## Purpose

Land the second domain in the system: **process**. Author a small corpus of CNC machining process documents (SOPs, control plans, tolerance specifications, in-process inspection records), wire a loader and a LangGraph investigator node against it, and ship the versioned prompt. After Phase 3 ships, this domain runs concurrently with the mechanical investigator (and three others) against the shared `Incident` and contributes process-side `Finding`s to the convergence in the synthesizer.

This task does not modify `orchestration/runner.py` — the dispatcher rewrite and graph registration are Task 5's responsibility.

## Why it matters

- The process domain is what makes the CNC out-of-tolerance scenario *interesting*. Mechanical evidence alone (a hydraulic-cylinder service event + a new bearing batch) does not explain why the line drifted out of tolerance on shift 3 specifically. Process evidence — the SOP that *should* have caught the drift, the in-process inspection cadence, the control-plan reaction rule — is what allows the synthesizer to write a multi-domain causal chain rather than a single-cause report.
- Phase 3's quality gate requires "5 investigator spans overlapping in time" on a LangSmith trace. This task ships investigator #2 of the four new ones.
- The bundle establishes that the per-domain shape locked by the mechanical bundle scales. If anything breaks during the copy (cache key collisions, prompt loader path assumptions, factory signature drift), this is the task where it surfaces — fix it here before Tasks 2/3/4 copy the same mistake.

## Concrete steps (what to produce)

1. **Create `data/domains/process/`** with 5–10 markdown files. Suggested mix that supports the locked CNC causal chain:
   - 1–2 **CNC machining SOPs** for the part family being run on line 2 (the operation sequence, feeds and speeds, tooling, the in-process gauging requirement).
   - 1–2 **control-plan excerpts** with tolerance specifications and the reaction rule when a measurement drifts (who is notified, what stops, what is recorded).
   - 1–2 **in-process inspection log entries** from the days surrounding the incident, including the shift-3 entry that should have caught the drift earlier.
   - 1–2 **tolerance-stack-up references** or **process-capability (Cpk) reports** for the affected dimension.
   - 1 **deviation report** or **CAPA log** for a recent prior incident on the same line — establishes a pattern the synthesizer can lean on without giving the answer away.

   Each file is a short, plausible manufacturing-process document. Keep each under ~200 lines. Use stable filename conventions (e.g., `sop-cnc-line-2.md`, `control-plan-tolerance-reaction-rule.md`, `inspection-log-shift-3.md`) so citations in the synthesizer report are readable.
2. **Create `src/expertview/rag/domains/process.py`** — loader mirroring `rag/domains/mechanical.py`:
   - Reads `data/domains/process/*.md`.
   - Embeds via the local `HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")` constructed in `agents/llms.py`.
   - Caches the vector index to disk under a **domain-specific cache key** (e.g., `.cache/rag/process/`) — re-embed only on corpus change. The cache path *must* differ from mechanical's; cache collisions across domains would silently serve the wrong store.
   - Returns a `KnowledgeStore` instance per the `rag/base.py` protocol.
3. **Create `src/expertview/prompts/investigator/process.md`** — versioned prompt mirroring `prompts/investigator/mechanical.md`:
   - Role framing for a manufacturing-process RCA investigator (control plans, SOPs, process capability, in-process inspection).
   - Citation requirement reproduced verbatim from the mechanical prompt — every `Finding.claim` cites at least one supplied document by `source` or `id`.
   - Output contract identical: structured JSON parseable into `list[Finding]`, with `investigator_domain="process"`.
4. **Create `src/expertview/agents/investigators/process.py`** — node factory `make_process_investigator_node(store: KnowledgeStore, llm: ChatOpenAI) -> Callable[[ExpertViewState], Awaitable[dict]]:`. Mirror `agents/investigators/mechanical.py` exactly; the only differences are:
   - The prompt file path (`prompts/investigator/process.md`).
   - The `investigator_domain` value baked into the parser's fallback (`"process"`).
   - The function and factory names.
5. **Add a unit test** in `tests/unit/test_process_investigator.py` that mirrors `tests/unit/test_mechanical_investigator.py`:
   - Builds the node with a fake `KnowledgeStore` and a fake LLM that returns hard-coded JSON.
   - Invokes the node against a stub `ExpertViewState` with the CNC `Incident`.
   - Asserts the returned patch is `{"findings": [...]}`, that each `Finding.investigator_domain == "process"`, and that each `Finding.citations` is non-empty.
6. **Verify locally**: `uv run pytest tests/unit/test_process_investigator.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** plants process-side evidence the synthesizer will cite. The deviation report and the shift-3 inspection-log entry are the load-bearing files — they connect the process domain into the multi-domain causal chain without solving the puzzle.
- **Step 2** stands up the second domain's retrieval store. Separate cache key is what keeps it independent of mechanical's.
- **Step 3** locks the prompt as a versioned artifact, satisfies the hard rule against inline prompts, and reproduces mechanical's citation discipline.
- **Step 4** exports the second investigator node factory. The shape it copies will be copied again by Tasks 2/3/4 — get it right here.
- **Step 5** locks the contract: structured JSON in, validated `Finding` objects out, `investigator_domain` correctly stamped, citations preserved. No live LLM call.
- **Step 6** is the local quality gate.

## Code locations

- `data/domains/process/*.md` (new — 5 to 10 files).
- `src/expertview/rag/domains/process.py` (new).
- `src/expertview/prompts/investigator/process.md` (new).
- `src/expertview/agents/investigators/process.py` (new).
- `tests/unit/test_process_investigator.py` (new).

## Connections

**Upstream**:

- `evidence/models.py` — `Incident`, `Finding` (Phase 1).
- `agents/base.py` — `Investigator` protocol (Phase 1).
- `agents/llms.py` — `create_investigator_llm()` (Phase 1).
- `rag/base.py` — `KnowledgeStore` protocol (Phase 1).
- `orchestration/state.py` — `ExpertViewState` (Phase 1).
- `rag/domains/mechanical.py` — the reference implementation for the loader (Phase 2).
- `prompts/investigator/mechanical.md` — the reference prompt (Phase 2).
- `agents/investigators/mechanical.py` — the reference node factory (Phase 2).
- `data/incidents/cnc_out_of_tolerance.yaml` — the rehearsed incident the corpus must support (Phase 2).

**Downstream**:

- [[task-5-dispatcher-wiring-verify]] imports `make_process_investigator_node` from this module, constructs the store via this loader, and registers the resulting async function as a graph node alongside the other four investigators.
- Phase 4's spawning logic may key on process-domain `Finding`s as triggers (e.g., a control-plan-violation finding might spawn a sub-investigator into supplier compliance).

## Parallelism rationale

- The bundle touches only `data/domains/process/`, `src/expertview/rag/domains/process.py`, `src/expertview/prompts/investigator/process.md`, `src/expertview/agents/investigators/process.py`, and `tests/unit/test_process_investigator.py`. None of these paths overlap with Tasks 2, 3, or 4.
- `orchestration/runner.py` is not edited here. Task 5 owns the dispatcher and graph registration.
- The loader's disk-cache key is domain-scoped, so concurrent first-run embedding across multiple domains does not collide.

## Risks / constraints / assumptions

- **Constraint**: prompts live as files under `src/expertview/prompts/`. Never inline ([CLAUDE.md hard rules](../../../CLAUDE.md)).
- **Constraint**: the only legal LLM construction site is `agents/llms.py`. The node receives the LLM via the factory's argument; do not call `ChatOpenAI(...)` inside the investigator.
- **Constraint**: module boundaries are walls ([architecture.md §5](../../architecture.md)). This module does not import from `agents/investigators/mechanical.py` — copy the pattern, do not re-export from a sibling.
- **Risk**: process corpus overlaps too heavily with mechanical (both ending up about machining tolerances). Mitigation: keep this corpus focused on *process governance* (SOPs, control plans, inspection cadence, reaction rules) rather than mechanical failure modes. The user-curation pass after the draft is where this gets enforced.
- **Risk**: the corpus solves the puzzle by stating the answer directly. Mitigation: the deviation report should describe a *pattern*, not the answer. The synthesizer earns the conclusion by combining process + mechanical + supply-chain evidence.
- **Risk**: cache-key collision with mechanical's loader (both writing to `.cache/rag/`). Mitigation: name the cache directory or file explicitly per domain (`.cache/rag/process/` vs `.cache/rag/mechanical/`). The first run on a clean checkout should produce two independent cache artifacts.
- **Risk**: prompt drift from the mechanical prompt's citation discipline. Mitigation: copy mechanical's prompt verbatim and edit only the role framing and the `investigator_domain` literal; do not relax the JSON contract or the citation requirement.
- **Assumption**: the user does a curation pass on the drafted corpus before Task 5's `/verify` rehearsal (per the hybrid-authoring decision in [decisions.md (2026-05-25 Q4)](../../decisions.md)). The PR description should list which files most need curator eyes.

## Definition of done

- 5 to 10 markdown files exist under `data/domains/process/`, each on-topic, under ~200 lines, and supporting the CNC causal chain without solving it directly.
- `rag/domains/process.py` exposes a loader returning a `KnowledgeStore` and caches to a domain-scoped path.
- `prompts/investigator/process.md` exists with mechanical's citation discipline preserved verbatim and the role framing swapped.
- `agents/investigators/process.py` exports `make_process_investigator_node(store, llm)` returning an async `(ExpertViewState) -> dict` function.
- Unit test passes with fake store and fake LLM; asserts the `findings` patch shape, `investigator_domain="process"`, and non-empty citations.
- No `ChatOpenAI(...)` or `HuggingFaceEmbeddings(...)` constructed in `agents/investigators/process.py` — both come in via dependencies / `agents/llms.py`.
- No prompt strings inlined in `.py` files.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/process-domain` per [branching_strategy.md §5](../../branching_strategy.md). PR description calls out which corpus files most need user curation and confirms real-LLM behavior is exercised by Task 5's `/verify`, not by this PR's unit tests.
