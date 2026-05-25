# Task 2 — Evidence Models + Shared State

> **Branch suggestion**: `feature/evidence-state-schemas`
> **Parallelism**: **Sequential — blocks Tasks 3, 4, and 5.**
> **Depends on**: Task 1 (project bootstrap merged to `main`).

## Purpose

Lock the cross-agent data contract. Define the pydantic v2 models used by every investigator, the synthesizer, and the RAG layer (`Finding`, `Hypothesis`, `CausalLink`, `CausalReport`, `Incident`, `Document`), plus the `ExpertViewState` TypedDict that is the LangGraph shared state. Add round-trip JSON serialization tests so a future schema change cannot silently break agents that read or write the state.

This is the *pinch point* of Phase 1: every downstream module's public surface references one or more of these types. Landing them first prevents Tasks 3/4/5 from independently inventing slightly different shapes.

## Why it matters

- [architecture.md §5](../../architecture.md) makes pydantic models the only legal cross-agent payload — "Never raw dicts across module boundaries." This task is what makes that rule enforceable.
- The LangGraph `ExpertViewState` is the one allowed non-pydantic cross-node type ([CLAUDE.md coding standards](../../../CLAUDE.md)). It is the substrate that replaces the earlier `EvidenceBus` per [decisions.md (2026-05-25 LangGraph adoption)](../../decisions.md).
- Reducers on `ExpertViewState` fields are what make the 5-way investigator fan-out merge correctly in Phase 3. Getting the reducer annotations right here saves a Phase 3 refactor.

## Concrete steps (what to produce)

1. **Create `src/expertview/evidence/models.py`** with pydantic v2 models for the shapes sketched in [architecture.md §3](../../architecture.md): `Incident`, `Finding`, `Hypothesis`, `CausalLink`, `CausalReport`, `Document`. Keep the field set to the **minimum** named in the architecture doc — Phase 1's risk register flags bikeshedding here. Fields can be added later when a node actually needs them ([build_plan.md Phase 1 risk](../../build_plan.md)).
2. **Create `src/expertview/orchestration/state.py`** with the `ExpertViewState` TypedDict from [architecture.md §3](../../architecture.md). The list-typed fields (`findings`, `hypotheses`, `spawned_subinvestigations`) must use the `Annotated[..., operator.add]` reducer pattern so concurrent investigator branches merge cleanly. `causal_report` is single-writer (the synthesizer), so no reducer.
3. **Create `tests/unit/test_schemas.py`** asserting JSON round-trip for every model in `evidence/models.py`. The pattern is: build an instance with representative values → `model_dump_json()` → `model_validate_json(...)` → assert equality. This catches both required-field omissions and serialization drift. Cover every model — partial coverage here is what causes the cross-agent merge surprises the architecture rule is meant to prevent.
4. **Add a smoke test for `ExpertViewState`** in the same test file (or a sibling `test_state.py`): construct a minimal state dict, verify the TypedDict accepts it, and exercise the reducer by simulating two concurrent state patches and confirming list concatenation works as expected.
5. **Document field provenance**: for each non-obvious field, the *why* belongs in a one-line comment ([CLAUDE.md coding standards](../../../CLAUDE.md): "Only WHY-comments for non-obvious constraints, workarounds, or hidden invariants"). Do not restate the type. Most fields will have no comment; that is correct.
6. **Verify the quality gates** locally: `uv run pytest tests/unit/test_schemas.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- Step 1 establishes the cross-agent payload vocabulary. Every downstream task imports from this module.
- Step 2 establishes the LangGraph shared-state schema. Task 5's `make_graph()` consumes it; Tasks 3 and 4 import its referenced models indirectly.
- Step 3 is the architecture's anti-drift mechanism — if a future change silently breaks a field shape, the round-trip test fails immediately rather than at the next demo rehearsal.
- Step 4 verifies the reducer behavior is what we think it is *before* Phase 3 fans out 5 investigators against it. Cheap insurance.
- Step 5 keeps the module readable without comment-rot. Coding-standards-aligned.
- Step 6 is the local quality gate proving the contract is internally consistent before downstream tasks pick it up.

## Code locations

- `src/expertview/evidence/models.py` (new).
- `src/expertview/orchestration/state.py` (new).
- `tests/unit/test_schemas.py` (new); optional `tests/unit/test_state.py` if state tests grow.

## Connections

**Upstream**: Task 1 must have merged the package skeleton so `evidence/` and `orchestration/` packages exist as importable empty modules.

**Downstream**:

- Task 3 (`rag/base.py`) imports `Document` from `evidence/models.py` for the `KnowledgeStore.search` return type.
- Task 4 (`agents/base.py`) imports `Incident`, `Finding`, `Hypothesis`, `CausalReport` for the `Investigator` and `Synthesizer` protocol signatures.
- Task 5 (`orchestration/runner.py`) imports `ExpertViewState` from `orchestration/state.py`.
- Phase 2 investigators and synthesizer return `Finding[]` and `CausalReport` patches against `ExpertViewState`.
- Phase 3 relies on the `operator.add` reducer to merge findings from 5 concurrent branches.
- Phase 5 evidence-weighted convergence (`evidence/convergence.py`) operates on these models.

## Risks / constraints / assumptions

- **Risk**: bikeshedding fields. Mitigation already named in [build_plan.md Phase 1 risk](../../build_plan.md): lock only the *minimum* set named in [architecture.md §3](../../architecture.md). Fields can be added later when a node needs them.
- **Risk**: getting the reducer annotations wrong. If a list field on `ExpertViewState` lacks the `Annotated[..., operator.add]` reducer, Phase 3's concurrent dispatch will silently overwrite rather than merge — a hard-to-debug demo-day surprise. Test step 4 catches this.
- **Constraint**: pydantic v2 only (per [CLAUDE.md coding standards](../../../CLAUDE.md)). Do not use v1 idioms.
- **Constraint**: `ExpertViewState` is the *only* allowed non-pydantic cross-node type ([CLAUDE.md coding standards](../../../CLAUDE.md)). Do not add additional TypedDicts for sub-shapes — those should be pydantic models in `evidence/models.py`.
- **Constraint**: validate only at system boundaries ([CLAUDE.md coding standards](../../../CLAUDE.md)). The pydantic models *are* the boundary against LLM outputs — that is where validation lives. Do not add defensive runtime type checks inside internal functions.
- **Architecture rule**: `evidence/` does not import from `agents/` or `orchestration/` ([architecture.md §5](../../architecture.md)). It is the lowest layer. `orchestration/state.py` may import from `evidence/models.py` but not the reverse.
- **Assumption**: representative-value test data for the round-trip tests can be invented from the field semantics in [architecture.md §3](../../architecture.md); no real corpus or incident data exists yet.

## Definition of done

- All pydantic models from [architecture.md §3](../../architecture.md) live in `evidence/models.py` with type hints and minimal fields.
- `ExpertViewState` lives in `orchestration/state.py` with correct reducer annotations on list fields.
- Every model has a passing JSON round-trip test.
- `ExpertViewState` reducer behavior is exercised by at least one test.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- Any non-obvious field choice is logged in [decisions.md](../../decisions.md) the same turn — per [CLAUDE.md workflow rules](../../../CLAUDE.md).
- PR opened on `feature/evidence-state-schemas` per [branching_strategy.md §5](../../branching_strategy.md).
