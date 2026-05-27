# Task 1 — Spawning Predicates + Parameterized Sub-Investigator Bundle

> **Branch suggestion**: `feature/spawning-and-sub-investigator`
> **Parallelism**: **Sequential (blocks Task 2).** No sibling tasks in Phase 4 share editing surface; this bundle lands all the new building blocks the wiring task imports.
> **Depends on**: Phase 3 complete (`v0.4.0-demo` tagged). Reuses `evidence/models`, `agents/base`, `agents/llms`, `rag/base`, the `supply_chain` `KnowledgeStore` loader from Phase 3, and the investigator-node patterns from Phase 2 / Phase 3.

## Purpose

Land the v1 spawning infrastructure as a self-contained bundle:

- A pure predicate module (`agents/spawning.py`) holding one function — `is_bearing_anomaly(finding: Finding) -> bool` — that inspects a `Finding` and decides whether the bearing-anomaly trigger fires.
- A parameterized sub-investigator node (`agents/investigators/sub_investigator.py`) that takes a domain label, a `KnowledgeStore`, an LLM client, and the triggering parent `Finding`, queries the store for supplier-history evidence around the parent finding's specifics, and returns a `{"findings": [...]}` patch.
- The versioned prompt (`prompts/investigator/sub_investigator.md`) the sub-investigator node uses, with parent-finding context injected at runtime.
- 2–3 supplier-history documents added to `data/domains/supply_chain/` so the sub-investigator's `KnowledgeStore.search(...)` returns substantive evidence when the bearing-anomaly trigger fires (new-supplier qualification record, supplier audit log entry, prior bearing-batch incident report).
- Unit tests asserting the predicate is pure and the sub-investigator node returns the right patch shape against a fake `KnowledgeStore` and a fake LLM.

This task does not modify `orchestration/runner.py` — the conditional edge, the `_should_spawn` function, and the graph registration are Task 2's responsibility.

## Why it matters

- [build_plan.md §Phase 4](../../build_plan.md) requires the predicates module to live as pure functions over `Finding` so the conditional-edge function in `runner.py` can be a thin dispatcher over them. Establishing that purity here keeps Task 2's wiring trivial.
- The phase quality gate requires the sub-investigator's `Finding` to be cited in the final CausalReport. That depends on the sub-investigator returning a well-formed `Finding` with citations — which depends on (a) supplier-history evidence actually existing in the store, and (b) the prompt enforcing citation discipline. Both are this task's responsibility.
- The pattern repetition (mechanical → 4 Phase-3 investigators → sub-investigator) is now at six. Treat this task as the canonical parameterized variant — Task 2 should not need to read this file to understand the factory's contract, only its signature.

## Concrete steps (what to produce)

1. **Create `src/expertview/agents/spawning.py`** — pure predicate module. Exports a single function:

   ```python
   def is_bearing_anomaly(finding: Finding) -> bool: ...
   ```

   The implementation is a pure function over the `Finding` pydantic model. It returns `True` when the finding's `claim` (and optionally `investigator_domain == "mechanical"`) signals a bearing-related anomaly relevant to the rehearsed CNC scenario. No I/O, no LLM calls, no LangGraph imports, no global state. The exact matching strategy (substring, regex, keyword list) is the executing agent's call — keep it tight enough that mechanical findings about non-bearing topics do not fire it, loose enough that the rehearsed scenario's bearing finding does fire it. Document the matching strategy with a one-line comment if a future reader could not derive it from the code (per [CLAUDE.md "non-obvious WHY only" rule](../../../CLAUDE.md)).

   The module exports *only* this predicate at v1. The dispatcher function in `runner.py` (Task 2) is the place that iterates over `state["findings"]` calling the predicate — not this module.
2. **Add 2–3 supplier-history documents to `data/domains/supply_chain/`** so the sub-investigator has substantive evidence to retrieve. Suggested files (filenames are starting points; the executing agent may rename for readability):
   - `supplier-qualification-acme-bearings.md` — the qualification record for the new supplier whose bearing batch is implicated in the CNC scenario (initial PPAP / first-article inspection, qualification date, scope, any waived conditions).
   - `supplier-audit-log-2026-q1.md` — a short audit log entry from the most recent supplier audit cycle covering the new supplier, noting any observed control gaps without stating they caused the incident.
   - `prior-bearing-batch-incident-2025.md` — a brief prior-incident summary describing a similar bearing-batch issue with an older supplier, establishing a pattern the synthesizer can cite without giving the answer away.

   Each file is short (under ~200 lines), plausible, and on-topic. **Curation note for the PR description**: the user-curation pass after the Claude draft is what keeps these from solving the puzzle directly. The supplier-qualification record and the prior-incident summary are the two files that most need curator eyes.
3. **Create `src/expertview/prompts/investigator/sub_investigator.md`** — versioned prompt mirroring the citation discipline of `prompts/investigator/supply_chain.md` (and the original mechanical prompt). The prompt is parameterized over the parent `Finding`'s `claim` text — the rendering machinery is the executing agent's call (an `{parent_finding_claim}` placeholder filled at node entry is the simplest path). The prompt's role framing is "supplier-history sub-investigator spawned from a parent finding," and its instructions tell the LLM to:
   - Treat the parent finding's claim as a focused query into the supplier-history corpus.
   - Search for supplier identity, qualification status, audit history, and prior-batch evidence relevant to the parent claim.
   - Return at least one `Finding` (or zero if no relevant evidence is retrieved), each with `investigator_domain="supply_chain"` and `citations` referencing the supplier-history documents by `source` or `id`.
   - Preserve the JSON contract used by the five investigator prompts.

   The prompt file lives under `prompts/investigator/` (not a new `sub_investigator/` subfolder) so the prompt-loader helper in `prompts/schema.py` can locate it without configuration changes. This is a deliberate flat-layout choice; the sub-investigator is structurally an investigator, just one whose store and prompt are bound at a later wiring step.
4. **Create `src/expertview/agents/investigators/sub_investigator.py`** — node factory `make_sub_investigator_node(domain: str, store: KnowledgeStore, llm: ChatOpenAI) -> Callable[[ExpertViewState], Awaitable[dict]]`. The factory mirrors `make_supply_chain_investigator_node` (and its five siblings) with two differences:
   - The returned async function reads the **triggering parent `Finding`** from `state["findings"]` by re-running the predicate from `agents/spawning.py` (i.e., picking the first finding for which `is_bearing_anomaly(finding)` returns `True`). If multiple findings match, the first one wins; the predicate's purity guarantees this is deterministic over a given state.
   - The prompt rendering interpolates the parent finding's `claim` text into the prompt template before the LLM call (per step 3's `{parent_finding_claim}` contract).

   Returned `Finding`s have `investigator_domain="supply_chain"` (not `"sub_investigator"`) — the sub-investigator is structurally a supply-chain finding, and the synthesizer should not need to learn a new domain label. The patch shape is `{"findings": [...]}` — the same shape every other investigator returns — so the reducer on `ExpertViewState.findings` merges sub-investigator findings into the same list the five parallel investigators write to.
5. **Add unit tests**:
   - `tests/unit/test_spawning_predicates.py` — asserts `is_bearing_anomaly` returns `True` for representative bearing-anomaly `Finding` fixtures and `False` for non-bearing mechanical findings, process findings, and findings from other domains. Asserts purity: calling the predicate twice with the same input produces the same output and does not mutate the input.
   - `tests/unit/test_sub_investigator.py` — mirrors the existing investigator unit tests. Builds the node with a fake `KnowledgeStore` (returns hard-coded supplier-history-shaped `Document`s) and a fake LLM (returns hard-coded JSON containing one or two `Finding`s). Invokes the node against a stub `ExpertViewState` whose `findings` list contains a bearing-anomaly mechanical finding. Asserts the returned patch is `{"findings": [...]}`, that each `Finding.investigator_domain == "supply_chain"`, that each `Finding.citations` is non-empty, and that the prompt rendering actually received the parent finding's `claim` (assert via the fake LLM's recorded prompt argument).
6. **Verify locally**: `uv run pytest tests/unit/test_spawning_predicates.py tests/unit/test_sub_investigator.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** establishes the predicate as a pure function over `Finding`, isolated from orchestration. This is what lets Task 2's `_should_spawn` be a thin dispatcher rather than a tangle of inline conditionals — exactly the mitigation [build_plan.md §Phase 4 risk register](../../build_plan.md) names.
- **Step 2** plants the supplier-history evidence the sub-investigator's `KnowledgeStore.search(...)` will return. Without these docs, the sub-investigator runs but cites nothing, the synthesizer cannot include sub-investigator citations, and the phase quality gate fails on "sub-investigator's finding cited in the final CausalReport."
- **Step 3** locks the parameterized sub-investigation prompt as a versioned artifact, satisfies the [CLAUDE.md hard rule](../../../CLAUDE.md) against inline prompts, and gives the sub-investigator a focused brief that does not duplicate the supply_chain investigator's role.
- **Step 4** exports the sub-investigator node factory with the same signature shape as the five investigators (plus the `domain` parameter). The parent-finding injection is the load-bearing detail — without it, the sub-investigator queries the store with no useful context and returns generic supply-chain findings instead of supplier-history-specific ones.
- **Step 5** locks the contracts for both the predicate (purity + correct truth table) and the sub-investigator node (patch shape, domain label, citation presence, prompt interpolation). No live LLM call.
- **Step 6** is the local quality gate.

## Code locations

- `src/expertview/agents/spawning.py` (new).
- `src/expertview/agents/investigators/sub_investigator.py` (new).
- `src/expertview/prompts/investigator/sub_investigator.md` (new).
- `data/domains/supply_chain/supplier-qualification-acme-bearings.md` (new — filename indicative).
- `data/domains/supply_chain/supplier-audit-log-2026-q1.md` (new — filename indicative).
- `data/domains/supply_chain/prior-bearing-batch-incident-2025.md` (new — filename indicative).
- `tests/unit/test_spawning_predicates.py` (new).
- `tests/unit/test_sub_investigator.py` (new).

## Connections

**Upstream**:

- `evidence/models.py` — `Finding`, `Incident` (Phase 1).
- `agents/base.py` — `Investigator` protocol (Phase 1).
- `agents/llms.py` — `create_investigator_llm()` (Phase 1; Phase 3 added the semaphore that the shared investigator client passes through).
- `rag/base.py` — `KnowledgeStore` protocol (Phase 1).
- `orchestration/state.py` — `ExpertViewState`, `Annotated[list[Finding], operator.add]` reducer on `findings` (Phase 1).
- `rag/domains/supply_chain.py` — Phase 3 loader; the sub-investigator's store is constructed by Task 2 via this loader against the corpus that this task extends.
- `prompts/investigator/supply_chain.md` — Phase 3 prompt, used as the citation-discipline reference for the sub-investigator prompt.
- `agents/investigators/supply_chain.py` — Phase 3 node factory, the reference shape for the sub-investigator factory.

**Downstream**:

- [[task-2-conditional-edge-wiring-verify]] imports `is_bearing_anomaly` from `agents/spawning.py` and `make_sub_investigator_node` from `agents/investigators/sub_investigator.py`. It constructs the sub-investigator's store via Phase 3's `rag/domains/supply_chain.py` loader (the same store the supply_chain investigator uses) and registers the resulting async function as a graph node behind the conditional edge.
- Phase 5's evidence-weighted convergence may use the predicate's output (or a richer cousin) to weight sub-investigator findings differently from parallel-investigator findings.
- The `rca-investigator-prompt` skill candidacy flagged in the [Phase 4 README](README.md) would template the prompt + factory + unit test produced here.

## Parallelism rationale

- This task is **sequential** in Phase 4 because it has no sibling: Task 2 imports both its outputs (the predicate and the node factory). There is no horizontal slice that could parallelize without producing a PR with no consumer.
- The bundle touches only `src/expertview/agents/spawning.py`, `src/expertview/agents/investigators/sub_investigator.py`, `src/expertview/prompts/investigator/sub_investigator.md`, the three new files under `data/domains/supply_chain/`, and the two new unit-test files. None of these paths are touched by `orchestration/runner.py` (which Task 2 owns) or by any of the five existing investigator modules.
- The corpus addition into `data/domains/supply_chain/` is a cross-phase touch — the Phase 3 supply_chain bundle (`feature/supply-chain-domain`) authored the original corpus, and Phase 4 adds three sibling files. The store loader's cache key invalidates on corpus change, so the next `/verify` re-embeds the supply_chain corpus once and uses the updated index thereafter. No code edit to the loader is required.

## Risks / constraints / assumptions

- **Constraint**: prompts live as files under `src/expertview/prompts/`, never inline in `.py` files ([CLAUDE.md hard rules](../../../CLAUDE.md)).
- **Constraint**: the only legal LLM construction site is `agents/llms.py`. The sub-investigator node receives its LLM client via the factory's `llm` argument; do not call `ChatOpenAI(...)` inside `sub_investigator.py`.
- **Constraint**: module boundaries are walls ([architecture.md §5](../../architecture.md)). `agents/spawning.py` does not import from `orchestration/`, and `agents/investigators/sub_investigator.py` does not import from `orchestration/` or from any sibling investigator file (copy the pattern; do not re-export).
- **Constraint**: spawning predicates are pure functions over `Finding` ([build_plan.md §Phase 4 risk mitigation](../../build_plan.md)). The predicate in `agents/spawning.py` must not depend on global state, must not perform I/O, and must not call an LLM. Unit-test fixture should round-trip a `Finding` model and assert the predicate result.
- **Risk — parent-finding plumbing detail is missed**: if the sub-investigator node forgets to interpolate the parent `Finding.claim` into the prompt, the LLM queries the supply-chain store with no useful context and the resulting `Finding`s are generic supply_chain findings — indistinguishable from what the Phase-3 supply_chain investigator already produces. Mitigation: the unit test in step 5 asserts the fake LLM received a prompt containing the parent finding's claim text.
- **Risk — supplier-history corpus overlaps too heavily with the Phase-3 supply_chain corpus**: the new three files duplicate themes already present (e.g., another "new-supplier" reference). Mitigation: the supplier-qualification and prior-incident files plant *supplier-history-specific* evidence (qualification dates, audit findings, prior-batch outcomes) that the Phase-3 corpus did not need to cover for the parallel investigator. The user-curation pass enforces this distinction.
- **Risk — predicate too tight or too loose**: a tight predicate matching only one exact phrase fires reliably on the rehearsed scenario but breaks if a prompt iteration changes the mechanical investigator's wording. A loose predicate (e.g., matching "bearing" anywhere) fires on mechanical findings that are not anomalies. Mitigation: the unit test in step 5 covers both ends — representative bearing-anomaly findings fire, non-anomaly mechanical findings about bearings do not. The empirical truth table from the rehearsal is what calibrates the strictness.
- **Risk — sub-investigator `investigator_domain` label drift**: stamping the sub-investigator's findings with `"sub_investigator"` instead of `"supply_chain"` would force the synthesizer to learn a new domain label. Mitigation: the factory hard-codes `investigator_domain="supply_chain"` in the parser's fallback, and the unit test asserts it.
- **Assumption**: Phase 3's `supply_chain` `KnowledgeStore` loader caches per-corpus and re-embeds on corpus change. If the loader's cache key is content-hash-based, the three new documents trigger a clean re-embed on the next run; if the loader's cache key is path-list-based, confirm the new files are picked up (the executing agent should run a single load via the Phase 3 loader before declaring the bundle done).
- **Assumption**: the user curates the three new corpus documents between this PR opening and Task 2's `/verify` (per the hybrid-authoring decision in [decisions.md (2026-05-25 Q4)](../../decisions.md)). The PR description should list the supplier-qualification and prior-incident files as the two most needing curator attention.

## Definition of done

- `src/expertview/agents/spawning.py` exports `is_bearing_anomaly(finding: Finding) -> bool` as a pure function with no I/O, no LLM calls, and no LangGraph imports.
- `src/expertview/agents/investigators/sub_investigator.py` exports `make_sub_investigator_node(domain, store, llm)` returning an async `(ExpertViewState) -> dict` function whose patch shape is `{"findings": [...]}` and whose `Finding`s carry `investigator_domain="supply_chain"`.
- `src/expertview/prompts/investigator/sub_investigator.md` exists with citation discipline preserved and a `{parent_finding_claim}` (or equivalent) placeholder for runtime interpolation of the triggering parent finding's claim text.
- 2–3 new markdown files exist under `data/domains/supply_chain/` planting supplier-history evidence (qualification record, audit log, prior-batch incident), each on-topic and under ~200 lines.
- Unit tests pass with fake `KnowledgeStore` and fake LLM:
  - `test_spawning_predicates.py` asserts the predicate's truth table and purity.
  - `test_sub_investigator.py` asserts the patch shape, domain label, citation presence, and parent-finding prompt interpolation.
- No `ChatOpenAI(...)` or `HuggingFaceEmbeddings(...)` constructed in `agents/investigators/sub_investigator.py`.
- No prompt strings inlined in `.py` files.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/spawning-and-sub-investigator` per [branching_strategy.md §5](../../branching_strategy.md). PR description:
  - Names which two corpus files most need curator attention.
  - Confirms the sub-investigator's `investigator_domain` label is `"supply_chain"`, not `"sub_investigator"` (this is the decision a reviewer is most likely to flag).
  - Notes that this task does not wire the conditional edge — the sub-investigator node and predicate sit unimported on `main` until [[task-2-conditional-edge-wiring-verify]] lands.
