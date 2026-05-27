# Task 4 — Human Factors Domain Bundle

> **Branch suggestion**: `feature/human-factors-domain`
> **Parallelism**: **Parallelizable with Tasks 1, 2, 3.** No shared editing surface with the other domain bundles.
> **Depends on**: Phase 2 complete (mechanical bundle merged, `v0.3.0-demo` tagged). Reuses `evidence/models`, `agents/base`, `agents/llms`, `rag/base`, and the patterns from [`rag/domains/mechanical.py`](../../../src/expertview/rag/domains/mechanical.py), [`prompts/investigator/mechanical.md`](../../../src/expertview/prompts/investigator/mechanical.md), and [`agents/investigators/mechanical.py`](../../../src/expertview/agents/investigators/mechanical.py).

## Purpose

Land the **human factors** domain: author a small corpus of shift staffing records, operator training and certification records, handover notes between shifts, and behavioral observation records, wire a loader and a LangGraph investigator node against it, and ship the versioned prompt. After Phase 3 ships, this investigator runs concurrently with the other four against the shared `Incident` and contributes human-factors `Finding`s to the synthesizer's convergence.

The CNC out-of-tolerance scenario is centered on **shift 3 specifically**. The human-factors corpus is where the *shift-specific* element of the causal chain lives: who was on shift, how recently were they trained on the post-maintenance verification procedure, what was in the shift-3 handover note from shift 2.

This task does not modify `orchestration/runner.py` — the dispatcher rewrite and graph registration are Task 5's responsibility.

## Why it matters

- The locked CNC scenario specifies *shift 3* as the timing axis ([decisions.md 2026-05-25 Q2](../../decisions.md)). Without human-factors evidence, the "why this shift?" question goes unanswered in the synthesizer report. With it, the convergence becomes a multi-domain story: a new-supplier bearing batch (supply_chain) + a recent hydraulic-cylinder service (mechanical) + a control-plan reaction rule that depends on operator verification (process) + a shift-3 staffing context where that verification was less likely to catch the drift (human_factors).
- Phase 3's quality gate requires "5 investigator spans overlapping in time" on a LangSmith trace. This task ships the **fifth and final** of the new investigators.
- The human-factors corpus is the highest-risk for **inappropriate content** — fictional people doing things wrong. Naming individuals or implying performance issues with named operators is unacceptable in a portfolio demo. Mitigation is built into the constraints below.

## Concrete steps (what to produce)

1. **Create `data/domains/human_factors/`** with 5–10 markdown files. Suggested mix that supports the locked CNC causal chain via *shift-context* evidence:
   - 1–2 **shift staffing records** for the incident date (shifts 1, 2, and 3) — headcount, role assignments. Use **generic role labels** (Operator A, Operator B, Setup Tech, Shift Lead) — **no real names, no fictional named individuals**. The relevant detail is that shift 3 was running a leaner crew than shifts 1 and 2.
   - 1–2 **training and certification matrices** showing which roles are certified on which procedures (especially "post-maintenance verification" and "first-piece-after-service inspection"). The corpus should imply that shift 3's available certifications had a thinner overlap with the post-maintenance procedure than shifts 1–2 — without naming who.
   - 1–2 **shift handover notes** between consecutive shifts on the incident date. The shift-2-to-3 handover should mention the hydraulic-cylinder service event but in passing, not as a flagged risk requiring extra inspection.
   - 1 **procedure document** describing the standard post-maintenance verification protocol on a CNC line (who runs it, when, what the gauging schedule is for the first hour back from service). This is the document negative or positive findings will cite as ground truth.
   - 1–2 **prior near-miss or learning-team reports** from the same plant about post-maintenance procedure adherence — establishes a pattern (post-maintenance verification is occasionally compressed under shift-end time pressure) without solving the puzzle.

   Each file is a short, plausible operations or HR document. Keep each under ~200 lines. Use stable filename conventions (e.g., `staffing-shift-3-incident-day.md`, `training-matrix-post-maintenance.md`, `handover-shift-2-to-3.md`, `procedure-post-maintenance-verification.md`) so citations in the synthesizer report are readable.

2. **Create `src/expertview/rag/domains/human_factors.py`** — loader mirroring `rag/domains/mechanical.py`:
   - Reads `data/domains/human_factors/*.md`.
   - Embeds via the local `HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")` constructed in `agents/llms.py`.
   - Caches the vector index to disk under a **domain-specific cache key** (e.g., `.cache/rag/human_factors/`).
   - Returns a `KnowledgeStore` instance per the `rag/base.py` protocol.
3. **Create `src/expertview/prompts/investigator/human_factors.md`** — versioned prompt mirroring `prompts/investigator/mechanical.md` with one extra constraint clause:
   - Role framing for a human-factors RCA investigator (staffing patterns, training and certification coverage, handover quality, procedure adherence, work-design factors).
   - Citation requirement reproduced verbatim from the mechanical prompt — every `Finding.claim` cites at least one supplied document by `source` or `id`.
   - **Added clause for the human-factors domain**: findings frame human-factors causes as *system-level* (staffing pattern, training-matrix coverage, procedure design, work-pressure context), never as individual blame. Findings must not name persons, even ones present in the corpus. If a corpus document names a role (e.g., "Operator A"), the finding refers to the role, not the individual. This is a hard constraint on the prompt, not a stylistic preference.
   - Output contract: structured JSON parseable into `list[Finding]`, with `investigator_domain="human_factors"`.
4. **Create `src/expertview/agents/investigators/human_factors.py`** — node factory `make_human_factors_investigator_node(store: KnowledgeStore, llm: ChatOpenAI) -> Callable[[ExpertViewState], Awaitable[dict]]:`. Mirror `agents/investigators/mechanical.py`; differences are the prompt path, the `investigator_domain` literal (`"human_factors"`), and the function/factory names.
5. **Add a unit test** in `tests/unit/test_human_factors_investigator.py` mirroring `tests/unit/test_mechanical_investigator.py`:
   - Builds the node with a fake `KnowledgeStore` and a fake LLM that returns hard-coded JSON.
   - Invokes the node against a stub `ExpertViewState` with the CNC `Incident`.
   - Asserts the returned patch is `{"findings": [...]}`, that each `Finding.investigator_domain == "human_factors"`, and that each `Finding.citations` is non-empty.
6. **Verify locally**: `uv run pytest tests/unit/test_human_factors_investigator.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** plants the shift-context evidence. The staffing record + the training matrix + the handover note are the load-bearing files — they answer "why shift 3" without naming anyone. The procedure document is what negative-evidence and procedure-adherence findings cite.
- **Step 2** stands up the human-factors retrieval store.
- **Step 3** locks the prompt as a versioned artifact, reproduces mechanical's citation discipline, and adds the no-individual-blame constraint that distinguishes this domain's prompt from the other four.
- **Step 4** exports the fifth investigator node factory.
- **Step 5** locks the contract: structured JSON in, validated `Finding` objects out, `investigator_domain="human_factors"`, citations preserved.
- **Step 6** is the local quality gate.

## Code locations

- `data/domains/human_factors/*.md` (new — 5 to 10 files).
- `src/expertview/rag/domains/human_factors.py` (new).
- `src/expertview/prompts/investigator/human_factors.md` (new).
- `src/expertview/agents/investigators/human_factors.py` (new).
- `tests/unit/test_human_factors_investigator.py` (new).

## Connections

**Upstream**:

- `evidence/models.py` — `Incident`, `Finding` (Phase 1).
- `agents/base.py` — `Investigator` protocol (Phase 1).
- `agents/llms.py` — `create_investigator_llm()` (Phase 1).
- `rag/base.py` — `KnowledgeStore` protocol (Phase 1).
- `orchestration/state.py` — `ExpertViewState` (Phase 1).
- `rag/domains/mechanical.py`, `prompts/investigator/mechanical.md`, `agents/investigators/mechanical.py` — reference implementations (Phase 2).
- `data/incidents/cnc_out_of_tolerance.yaml` (Phase 2) — defines the scenario the corpus supports (especially the shift-3 axis).

**Downstream**:

- [[task-5-dispatcher-wiring-verify]] imports `make_human_factors_investigator_node`, constructs the store via this loader, and registers the resulting async function as a graph node.
- The synthesizer (Phase 2 Task 4) consumes the findings from state without modification.

## Parallelism rationale

- The bundle touches only `data/domains/human_factors/`, `src/expertview/rag/domains/human_factors.py`, `src/expertview/prompts/investigator/human_factors.md`, `src/expertview/agents/investigators/human_factors.py`, and `tests/unit/test_human_factors_investigator.py`. None of these paths overlap with Tasks 1, 2, or 3.
- `orchestration/runner.py` is not edited here. Task 5 owns the dispatcher and graph registration.
- The loader's disk-cache key is domain-scoped.

## Risks / constraints / assumptions

- **Constraint**: prompts live as files under `src/expertview/prompts/`. Never inline ([CLAUDE.md hard rules](../../../CLAUDE.md)).
- **Constraint**: the only legal LLM construction site is `agents/llms.py`.
- **Constraint**: module boundaries are walls ([architecture.md §5](../../architecture.md)).
- **Hard constraint — no individual blame**: this is the most sensitive corpus in the system. No real or fictional named individuals. No findings that frame a person as the cause. The prompt enforces this at the LLM boundary; the corpus enforces it at the content level by using role labels only. If a draft file slips and uses a name, the user-curation pass must catch it before merge. Treat this as non-negotiable — a portfolio demo that names a fictional operator as the cause of an incident is worse than no human-factors domain at all.
- **Risk**: the LLM concludes "operator error" as a primary finding despite the prompt's framing. Mitigation: the prompt rewrites the framing to *system-level* causes (staffing pattern, training coverage, procedure design); the user-curation pass and a manual review of the first `/verify` run in Task 5 confirm the framing held.
- **Risk**: corpus too vague and the human-factors investigator produces only generic "shift 3 had fewer people" findings without citing the procedure or the training matrix. Mitigation: the procedure document + the training matrix should be retrievable for the same queries that surface the staffing record. The user-curation pass enforces this by keeping the file count small and the cross-references explicit (e.g., the handover note mentions "per the post-maintenance verification procedure (see procedure-post-maintenance-verification.md)").
- **Risk**: cache-key collision with sibling loaders. Mitigation: name the cache directory `.cache/rag/human_factors/` explicitly.
- **Risk**: prompt drift from the mechanical prompt's citation discipline. Mitigation: copy the mechanical prompt verbatim, edit role framing + `investigator_domain` literal, then add the no-individual-blame clause as a clearly-marked additional section.
- **Assumption**: the user does a curation pass on the drafted corpus before Task 5's `/verify` rehearsal — with **special attention** to scrubbing any names that slipped into the draft. The PR description must explicitly call this out.

## Definition of done

- 5 to 10 markdown files exist under `data/domains/human_factors/`, each on-topic, under ~200 lines, using **role labels only — no individual names**.
- The procedure document + the training matrix + the handover note are present and cross-reference each other.
- `rag/domains/human_factors.py` exposes a loader returning a `KnowledgeStore` and caches to a domain-scoped path.
- `prompts/investigator/human_factors.md` exists with mechanical's citation discipline preserved verbatim, the role framing swapped, and the no-individual-blame clause added.
- `agents/investigators/human_factors.py` exports `make_human_factors_investigator_node(store, llm)` returning an async `(ExpertViewState) -> dict` function.
- Unit test passes with fake store and fake LLM; asserts the `findings` patch shape, `investigator_domain="human_factors"`, and non-empty citations.
- No `ChatOpenAI(...)` or `HuggingFaceEmbeddings(...)` constructed in `agents/investigators/human_factors.py`.
- No prompt strings inlined in `.py` files.
- No individual names — real or fictional — anywhere in the corpus.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/human-factors-domain` per [branching_strategy.md §5](../../branching_strategy.md). PR description explicitly states "reviewed for individual-blame framing; uses role labels only" and flags any borderline phrases for user attention.
