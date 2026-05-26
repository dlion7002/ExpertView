# Task 3 — Mechanical Investigator Node + Prompt

> **Branch suggestion**: `feature/mechanical-investigator`
> **Parallelism**: **Parallelizable with Tasks 2 and 4.**
> **Depends on**: Phase 1 (uses `evidence/models`, `agents/base`, `agents/llms`, `rag/base`). Does **not** import Task 2's loader directly — the `KnowledgeStore` is injected at graph-build time by Task 5.

## Purpose

Build the first real LangGraph node in the project: the mechanical investigator. It takes the current `ExpertViewState`, queries a `KnowledgeStore` for evidence relevant to the incident, calls the investigator LLM (`openrouter/owl-alpha` via `create_investigator_llm()`), and returns `{"findings": [Finding, ...]}` as its state patch. Ship the versioned prompt file alongside the node — per [CLAUDE.md hard rules](../../../CLAUDE.md), prompts must live as files, never inline in agent code.

## Why it matters

- This is the **first node that does real work**. Phase 1 compiled a placeholder; Phase 2 here proves the pattern that all five investigators in Phase 3 will follow.
- [architecture.md §5](../../architecture.md) requires nodes be pure async `(State) -> dict` functions returning patches. Establishing the right shape here means Phase 3's four siblings copy a clean pattern.
- The Phase 2 quality gate demands "at least one citation back to the corpus" in the final report — that citation has to be produced *here*, on the `Finding`, and propagated through the synthesizer. The prompt must make the model cite or the gate fails.

## Concrete steps (what to produce)

1. **Create `src/expertview/prompts/investigator/mechanical.md`** — the versioned prompt file. Required behavior elicited:
   - Role framing for a mechanical-domain RCA investigator.
   - Instruction to use only the supplied retrieved documents as evidence (no parametric knowledge).
   - **Mandatory citation**: every `Finding.claim` must include at least one citation referencing a supplied document by its `source` (or `id`). The synthesizer's report will surface these.
   - Output contract: structured JSON parseable into a list of `Finding` (fields per `evidence/models.py`: `investigator_domain="mechanical"`, `claim`, `confidence` ∈ [0,1], `citations`).
2. **Create `src/expertview/agents/investigators/__init__.py`** (empty marker if absent) and **`src/expertview/agents/investigators/mechanical.py`** exporting a node factory. Suggested shape:
   - `def make_mechanical_investigator_node(store: KnowledgeStore, llm: ChatOpenAI) -> Callable[[ExpertViewState], Awaitable[dict]]:`
   - The returned async node:
     - Reads `incident: Incident` from state.
     - Calls `store.search(query, k=...)` where `query` is derived from the incident summary + symptoms.
     - Loads the prompt template from `prompts/investigator/mechanical.md` and renders it with the retrieved docs + incident.
     - Awaits the LLM call.
     - Parses the response into a `list[Finding]` via pydantic (`Finding.model_validate(...)` per item) — *no* manual dict construction; validate at the LLM boundary per [CLAUDE.md coding standards](../../../CLAUDE.md).
     - Returns `{"findings": findings}` so the `operator.add` reducer on `ExpertViewState.findings` concatenates cleanly when Phase 3 adds parallel siblings.
   - Use the factory pattern so the wiring layer (Task 5) injects the store and LLM at graph-build time; the node itself stays pure and easy to unit-test.
3. **Add a unit test** in `tests/unit/test_mechanical_investigator.py` that:
   - Builds the node with a fake `KnowledgeStore` (returns a hard-coded `list[Document]`) and a fake LLM (returns a hard-coded JSON string that parses into one or two `Finding`s).
   - Invokes the node against a stub `ExpertViewState`.
   - Asserts the returned patch is `{"findings": [...]}` and that each `Finding.citations` is non-empty (the contract that citations are propagated, not silently lost).
4. **Verify locally**: `uv run pytest tests/unit/test_mechanical_investigator.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** locks the prompt as a versioned artifact, satisfies the hard rule against inline prompts, and makes the citation requirement structural rather than aspirational.
- **Step 2** establishes the node shape (factory returning a pure async function) that Phase 3's four siblings will copy. The factory pattern is what keeps the node testable without a real store and what lets Task 5 wire the real store in at one place.
- **Step 3** locks the contract: structured JSON in, validated `Finding` objects out, citations preserved. No live LLM call needed at unit-test time.
- **Step 4** is the local quality gate.

## Code locations

- `src/expertview/prompts/investigator/mechanical.md` (new).
- `src/expertview/agents/investigators/__init__.py` (new if absent).
- `src/expertview/agents/investigators/mechanical.py` (new).
- `tests/unit/test_mechanical_investigator.py` (new).

## Connections

**Upstream**:

- `evidence/models.py` — `Incident`, `Finding`.
- `agents/base.py` — the `Investigator` protocol shape (the node's behavior is compatible with the protocol's `(incident, prior_findings) -> list[Finding]` semantics, wrapped in a LangGraph node signature).
- `agents/llms.py` — `create_investigator_llm()`.
- `rag/base.py` — the `KnowledgeStore` protocol the node accepts as a dependency.
- `orchestration/state.py` — the `ExpertViewState` type the node consumes.

**Downstream**:

- [[task-5-runner-cli-wiring]] constructs the store via Task 2's loader, constructs the LLM via `create_investigator_llm()`, calls the factory here to bind both, and registers the resulting async function as a graph node.
- Phase 3's `process`, `supply_chain`, `environmental`, and `human_factors` investigator nodes will mirror this file's structure — same factory shape, same `{"findings": [...]}` patch.
- Phase 4's spawning logic reads the `Finding`s this node emits and conditionally routes to a sub-investigator.

## Parallelism rationale

- The node takes its `KnowledgeStore` as a constructor argument. A fake store satisfies the protocol for testing, so Task 3 develops to completion without Task 2 merging first.
- The synthesizer (Task 4) consumes `findings` from state; it doesn't depend on this node's implementation, only on the `Finding` schema (Phase 1).
- Three branches with no shared editing surface among `agents/investigators/mechanical.py`, `rag/domains/mechanical.py`, and `agents/synthesizer.py`. Architecture rule from [architecture.md §5](../../architecture.md) keeps the fan-out safe.

## Risks / constraints / assumptions

- **Constraint**: prompts live as files under `src/expertview/prompts/`. Never inline ([CLAUDE.md hard rules](../../../CLAUDE.md)).
- **Constraint**: the only legal LLM construction site is `agents/llms.py`. The node receives the LLM via the factory's argument; do not call `ChatOpenAI(...)` inside the investigator.
- **Risk**: `openrouter/owl-alpha` returns prose instead of parseable JSON. Mitigation: the prompt demands a JSON schema; the parser raises a clear error on validation failure; consider a single retry with a "parse-correction" follow-up in a later phase rather than here (Phase 7's retry/backoff wrapper covers transient errors; structural drift is a prompt iteration problem).
- **Risk**: query derivation from the incident is too generic and retrieval misses the planted clues. Mitigation: derive the query from `incident.summary + " " + " ".join(incident.symptoms + incident.affected_assets)` (or similar concatenation) so the corpus's surface forms get hit. Tune in the prompt-iteration pass before declaring done.
- **Risk**: findings lack citations because the LLM ignores the instruction. Mitigation: the unit test asserts `Finding.citations` is non-empty; the integration run in Task 5 surfaces real-model behavior.
- **Assumption**: the node returns a patch with `findings` only. Hypotheses are the synthesizer's responsibility. If the investigator ever needs to emit hypotheses directly, that's a Phase 5 (convergence) decision, not a Phase 2 one.

## Definition of done

- Prompt file exists at `src/expertview/prompts/investigator/mechanical.md` and contains the citation requirement explicitly.
- `agents/investigators/mechanical.py` exports a node factory; the returned node is an async `(ExpertViewState) -> dict` function compatible with `StateGraph.add_node(...)`.
- Unit test passes with fake store and fake LLM; asserts the `findings` patch shape and non-empty citations.
- No `ChatOpenAI(...)` or `HuggingFaceEmbeddings(...)` constructed in this module — both come in via dependencies.
- No prompt strings inlined in `.py` files.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/mechanical-investigator` per [branching_strategy.md §5](../../branching_strategy.md). PR description should call out that real-LLM behavior (citation discipline, JSON parseability) is exercised by Task 5's `/verify`, not by this PR's unit tests.
