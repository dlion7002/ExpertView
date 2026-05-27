# Task 2 — Supply Chain Domain Bundle

> **Branch suggestion**: `feature/supply-chain-domain`
> **Parallelism**: **Parallelizable with Tasks 1, 3, 4.** No shared editing surface with the other domain bundles.
> **Depends on**: Phase 2 complete (mechanical bundle merged, `v0.3.0-demo` tagged). Reuses `evidence/models`, `agents/base`, `agents/llms`, `rag/base`, and the patterns from [`rag/domains/mechanical.py`](../../../src/expertview/rag/domains/mechanical.py), [`prompts/investigator/mechanical.md`](../../../src/expertview/prompts/investigator/mechanical.md), and [`agents/investigators/mechanical.py`](../../../src/expertview/agents/investigators/mechanical.py).

## Purpose

Land the **supply chain** domain: author a small corpus of supplier history, qualification records, receiving QA, and supplier-change correspondence, wire a loader and a LangGraph investigator node against it, and ship the versioned prompt. After Phase 3 ships, this investigator runs concurrently with mechanical and the other three domains against the shared `Incident` and contributes supply-side `Finding`s to the synthesizer's convergence.

This domain carries extra weight: Phase 4's dynamic-spawning trigger will key on a *mechanical* finding (bearing anomaly) and route to a sub-investigator under supply chain. The supply-chain corpus authored here is what that sub-investigator will retrieve from. Task 2 must plant the supplier-change clue trail richly enough that Phase 4's spawn lands somewhere with real evidence.

This task does not modify `orchestration/runner.py` — the dispatcher rewrite and graph registration are Task 5's responsibility.

## Why it matters

- The locked CNC out-of-tolerance scenario hinges on a **new-supplier bearing batch** ([decisions.md 2026-05-25 Q2](../../decisions.md)). Mechanical already carries a thin trail of that clue; the *substance* (when the supplier changed, who approved it, what the incoming-inspection cadence was, whether dimensional QA was on or off) lives in this corpus.
- Phase 4's spawn trigger ([build_plan.md §Phase 4](../../build_plan.md)) targets a supplier-history sub-investigator under supply chain. The corpus this task lands is the evidence base for that future spawn.
- Phase 3's quality gate requires "5 investigator spans overlapping in time" on a LangSmith trace. This task ships investigator #3 of the four new ones.

## Concrete steps (what to produce)

1. **Create `data/domains/supply_chain/`** with 5–10 markdown files. Suggested mix that supports the locked CNC causal chain and Phase 4's future spawn:
   - 1–2 **supplier-change memos** documenting the recent switch to a new bearing vendor (sourcing rationale, projected savings, signoff list).
   - 1–2 **incoming inspection / receiving QA records** for shipments from both the prior supplier and the new supplier — including the QA receipt for the batch that ended up on line 2.
   - 1–2 **supplier qualification documents** for the new bearing vendor (Cpk targets, sample-size requirements, first-article approval notes).
   - 1 **bill-of-materials excerpt** or **purchasing system query** showing which line received which lot.
   - 1–2 **prior corrective-action records** from previous supplier transitions on the same plant — establishes that supplier transitions historically caused tolerance variability without naming the answer.

   Each file is a short, plausible procurement / quality document. Keep each under ~200 lines. Use stable filename conventions (e.g., `supplier-change-memo-bearings.md`, `receiving-qa-batch-2026-05.md`, `qualification-new-bearing-vendor.md`) so citations in the synthesizer report are readable.
2. **Create `src/expertview/rag/domains/supply_chain.py`** — loader mirroring `rag/domains/mechanical.py`:
   - Reads `data/domains/supply_chain/*.md`.
   - Embeds via the local `HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")` constructed in `agents/llms.py`.
   - Caches the vector index to disk under a **domain-specific cache key** (e.g., `.cache/rag/supply_chain/`).
   - Returns a `KnowledgeStore` instance per the `rag/base.py` protocol.
3. **Create `src/expertview/prompts/investigator/supply_chain.md`** — versioned prompt mirroring `prompts/investigator/mechanical.md`:
   - Role framing for a supply-chain RCA investigator (supplier history, qualification, receiving QA, lot traceability).
   - Citation requirement reproduced verbatim from the mechanical prompt — every `Finding.claim` cites at least one supplied document by `source` or `id`.
   - Output contract identical: structured JSON parseable into `list[Finding]`, with `investigator_domain="supply_chain"`.
4. **Create `src/expertview/agents/investigators/supply_chain.py`** — node factory `make_supply_chain_investigator_node(store: KnowledgeStore, llm: ChatOpenAI) -> Callable[[ExpertViewState], Awaitable[dict]]:`. Mirror `agents/investigators/mechanical.py`; differences are limited to the prompt path, the `investigator_domain` literal (`"supply_chain"`), and the function/factory names.
5. **Add a unit test** in `tests/unit/test_supply_chain_investigator.py` mirroring `tests/unit/test_mechanical_investigator.py`:
   - Builds the node with a fake `KnowledgeStore` and a fake LLM that returns hard-coded JSON.
   - Invokes the node against a stub `ExpertViewState` with the CNC `Incident`.
   - Asserts the returned patch is `{"findings": [...]}`, that each `Finding.investigator_domain == "supply_chain"`, and that each `Finding.citations` is non-empty.
6. **Verify locally**: `uv run pytest tests/unit/test_supply_chain_investigator.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** plants the supplier-change clue trail. The receiving QA records and the supplier-change memo are the load-bearing files — they are what Phase 4's spawned sub-investigator will retrieve from, and what the synthesizer will cite when explaining the bearing-batch contribution to the causal chain.
- **Step 2** stands up the supply-chain retrieval store.
- **Step 3** locks the prompt as a versioned artifact and reproduces mechanical's citation discipline.
- **Step 4** exports the third investigator node factory.
- **Step 5** locks the contract: structured JSON in, validated `Finding` objects out, `investigator_domain="supply_chain"`, citations preserved.
- **Step 6** is the local quality gate.

## Code locations

- `data/domains/supply_chain/*.md` (new — 5 to 10 files).
- `src/expertview/rag/domains/supply_chain.py` (new).
- `src/expertview/prompts/investigator/supply_chain.md` (new).
- `src/expertview/agents/investigators/supply_chain.py` (new).
- `tests/unit/test_supply_chain_investigator.py` (new).

## Connections

**Upstream**:

- `evidence/models.py` — `Incident`, `Finding` (Phase 1).
- `agents/base.py` — `Investigator` protocol (Phase 1).
- `agents/llms.py` — `create_investigator_llm()` (Phase 1).
- `rag/base.py` — `KnowledgeStore` protocol (Phase 1).
- `orchestration/state.py` — `ExpertViewState` (Phase 1).
- `rag/domains/mechanical.py`, `prompts/investigator/mechanical.md`, `agents/investigators/mechanical.py` — reference implementations (Phase 2).
- `data/incidents/cnc_out_of_tolerance.yaml` (Phase 2) — defines the scenario the corpus supports.
- `data/domains/mechanical/` (Phase 2) — already contains thin bearing-batch references; this corpus is what *substantiates* those references.

**Downstream**:

- [[task-5-dispatcher-wiring-verify]] imports `make_supply_chain_investigator_node`, constructs the store via this loader, and registers the resulting async function as a graph node.
- **Phase 4's spawning trigger** ([build_plan.md §Phase 4](../../build_plan.md)) routes from a mechanical bearing-anomaly finding to a supplier-history sub-investigator. That sub-investigator will retrieve from this corpus. The clue trail authored here is the spawn's evidence base.

## Parallelism rationale

- The bundle touches only `data/domains/supply_chain/`, `src/expertview/rag/domains/supply_chain.py`, `src/expertview/prompts/investigator/supply_chain.md`, `src/expertview/agents/investigators/supply_chain.py`, and `tests/unit/test_supply_chain_investigator.py`. None of these paths overlap with Tasks 1, 3, or 4.
- `orchestration/runner.py` is not edited here. Task 5 owns the dispatcher and graph registration.
- The loader's disk-cache key is domain-scoped.

## Risks / constraints / assumptions

- **Constraint**: prompts live as files under `src/expertview/prompts/`. Never inline ([CLAUDE.md hard rules](../../../CLAUDE.md)).
- **Constraint**: the only legal LLM construction site is `agents/llms.py`.
- **Constraint**: module boundaries are walls ([architecture.md §5](../../architecture.md)). This module does not import from `agents/investigators/mechanical.py` or other sibling investigators.
- **Risk**: the corpus narrates the answer directly ("the new supplier's bearings caused the tolerance drift"). Mitigation: keep documents in operational voice — receipts, qualifications, memos — not analyses. Let retrieval + the LLM reconstruct the chain from the evidence. The user-curation pass enforces this.
- **Risk**: insufficient density for Phase 4's spawn target. Mitigation: the supplier-change memo + the two QA receipts (old supplier vs new supplier) + the qualification document are the minimum. If a draft skimps on these, the spawned sub-investigator will have nothing to retrieve when Phase 4 lands.
- **Risk**: cache-key collision with sibling loaders. Mitigation: name the cache directory `.cache/rag/supply_chain/` explicitly.
- **Risk**: prompt drift from the mechanical prompt's citation discipline. Mitigation: copy the mechanical prompt verbatim and edit only the role framing and `investigator_domain` literal.
- **Risk**: realistic supplier names or company identifiers leak into the corpus (an LLM-generated draft might invent specific company names that imply real-world entities). Mitigation: use generic placeholders (`Vendor A`, `Vendor B`, `Bearing Supplier — North`). The user-curation pass should scrub anything that reads as a real company.
- **Assumption**: the user does a curation pass on the drafted corpus before Task 5's `/verify` rehearsal (per the hybrid-authoring decision in [decisions.md (2026-05-25 Q4)](../../decisions.md)). The PR description should call out which files most need curator eyes — especially the receiving-QA records, where dates and lot numbers need to line up with the CNC incident date.

## Definition of done

- 5 to 10 markdown files exist under `data/domains/supply_chain/`, each on-topic, under ~200 lines, with the supplier-change clue trail rich enough to support Phase 4's spawn target.
- `rag/domains/supply_chain.py` exposes a loader returning a `KnowledgeStore` and caches to a domain-scoped path.
- `prompts/investigator/supply_chain.md` exists with mechanical's citation discipline preserved verbatim and the role framing swapped.
- `agents/investigators/supply_chain.py` exports `make_supply_chain_investigator_node(store, llm)` returning an async `(ExpertViewState) -> dict` function.
- Unit test passes with fake store and fake LLM; asserts the `findings` patch shape, `investigator_domain="supply_chain"`, and non-empty citations.
- No `ChatOpenAI(...)` or `HuggingFaceEmbeddings(...)` constructed in `agents/investigators/supply_chain.py`.
- No prompt strings inlined in `.py` files.
- No real-company-name leakage in the corpus.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/supply-chain-domain` per [branching_strategy.md §5](../../branching_strategy.md). PR description calls out which corpus files most need user curation (especially date / lot-number alignment with the CNC incident) and confirms real-LLM behavior is exercised by Task 5's `/verify`.
