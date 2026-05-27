# Task 1 — Convergence Functions + Unit Tests

> **Branch suggestion**: `feature/convergence-functions`
> **Parallelism**: **Parallelizable with Task 2.** No shared editing surface — this task touches only `evidence/convergence.py` and its unit test; Task 2 touches only `data/`.
> **Depends on**: Phase 4 complete (`v0.5.0-demo` tagged). Reuses `evidence/models.py` (`Finding`, `Hypothesis`, `CausalLink`, `Symptom`) from Phase 1.

## Purpose

Land the evidence-math layer as a self-contained module of pure functions over the `evidence/models.py` types. `evidence/convergence.py` exports the three functions [build_plan.md §Phase 5](../../build_plan.md) names — weight a finding by source confidence, link causes across domains, and score hypotheses — plus whatever small private helpers they need. Every function is a pure transform: deterministic, no I/O, no LLM calls, no logging, no global state, and no imports from `agents/` or `orchestration/`.

This task does **not** wire the functions into the synthesizer and does **not** touch `agents/synthesizer.py` — that is [[task-3-wiring-and-verify]]'s responsibility. It also does not author the second incident — that is [[task-2-second-incident]]. The deliverable here is the module plus its unit tests, sitting on `main` ready to be imported by Task 3.

## Why it matters

- [build_plan.md §Phase 5](../../build_plan.md) lists `evidence/convergence.py` with these exact three responsibilities as a phase output. Shipping it as pure functions isolated from the graph is what lets Task 3's synthesizer edit be a thin call into this module rather than a tangle of inline scoring logic.
- The locked **post-LLM re-scoring** design (see [Phase 5 README pre-flight](README.md)) means the report's confidence numbers are computed in Python, not asserted by the LLM. That only works if the scoring functions are deterministic and unit-tested in isolation — which is exactly this task's deliverable.
- [architecture.md §5](../../architecture.md) requires cross-agent data to flow through `evidence/models.py` pydantic models and forbids `evidence/` from importing `orchestration/`. Keeping the convergence math LLM-provider-pure and orchestration-unaware preserves the Path B lift story in [build_plan.md §Path B](../../build_plan.md) — `evidence/` lifts as a unit.
- The phase quality gate requires a "non-trivial confidence summary." A non-trivial summary is one that reflects the *computed* weighting (relative hypothesis strengths, dominant domain, spread) — which presupposes a scoring function exists to compute it. This task provides the inputs that summary will draw on.

## Concrete steps (what to produce)

1. **Create `src/expertview/evidence/convergence.py`** — pure-function module exporting the three named operations. Suggested public surface (exact signatures are the executing agent's call, but they must operate on `evidence/models.py` types and return new immutable models, never mutate inputs — the models are `frozen=True`):

   ```python
   def weight_finding(finding: Finding) -> float: ...
   def score_hypothesis(hypothesis: Hypothesis) -> Hypothesis: ...
   def link_causes(hypotheses: list[Hypothesis], incident: Incident) -> list[CausalLink]: ...
   ```

   - **`weight_finding`** maps a `Finding` to a source-confidence weight. The weighting policy (e.g., a multiplier keyed on `investigator_domain`, on citation count, on the finding's own `confidence`, or a blend) is the executing agent's call — document the chosen policy in a one-line comment per the [CLAUDE.md "non-obvious WHY only" rule](../../../CLAUDE.md). The policy must be a total function (defined for every `Finding`) with no special-casing of the two rehearsed incidents — over-fitting to one scenario is the [build_plan.md §Phase 5 risk](../../build_plan.md).
   - **`score_hypothesis`** returns a new `Hypothesis` whose `confidence` is recomputed from the weights of its `supporting_findings` (e.g., a normalized aggregate). It copies the input's other fields verbatim. It must return a *new* frozen model, not mutate the input.
   - **`link_causes`** builds or re-orders `CausalLink` objects across the scored hypotheses, expressing cross-domain causation (a cause hypothesis from one domain producing an effect hypothesis or a `Symptom` from the incident). Whether this function *generates* links from scored hypotheses or *re-scores `strength` on links the LLM already drafted is the executing agent's call and is coordinated with Task 3's wiring — but the function itself stays pure.
2. **Decide and document the aggregation rule** for `score_hypothesis`. Pick a defensible aggregate (weighted mean, max, or sum-capped-at-1.0) over the supporting findings' weights, and write one comment line stating why. The rule must keep `confidence ∈ [0.0, 1.0]` (the `Finding`/`Hypothesis` pydantic constraint) — a sum that can exceed 1.0 must be clamped or normalized, and the test in step 4 asserts the bound holds.
3. **Provide a confidence-summary input helper if useful** — optionally a small pure function (e.g., `summarize_confidence(hypotheses: list[Hypothesis]) -> str` or a structured intermediate the synthesizer formats) that turns the scored hypotheses into the material the synthesizer's `confidence_summary` will reflect. If the executing agent judges this belongs in the synthesizer rather than here, omit it and note the decision for Task 3 — the constraint is only that the summary ends up *non-trivial* (reflects computed scores), wherever it is assembled.
4. **Add `tests/unit/test_convergence.py`** asserting:
   - `weight_finding` is pure (same input → same output, input unmutated) and total (returns a finite weight for findings from every `investigator_domain`, including `"supply_chain"` sub-investigator findings).
   - `score_hypothesis` returns a new `Hypothesis` with `confidence ∈ [0.0, 1.0]`, recomputed from supporting-finding weights, with all other fields preserved; a hypothesis backed by higher-weighted findings scores above one backed by lower-weighted findings.
   - `link_causes` produces well-formed `CausalLink` objects (each `strength ∈ [0.0, 1.0]`, each `cause`/`effect` referencing supplied hypotheses or incident symptoms) and is deterministic over a fixed input.
   - A **distinctness** sanity check: two different finding sets (one mechanical/supply-chain-weighted, one process-weighted) produce different top-scored hypotheses. This is the unit-level rehearsal of the phase quality gate; the live two-incident proof lives in Task 3.
5. **Verify locally**: `uv run pytest tests/unit/test_convergence.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** establishes the three convergence operations as pure functions isolated from orchestration, so Task 3's synthesizer edit is a call into this module rather than inline scoring logic.
- **Step 2** locks the aggregation rule and its `[0.0, 1.0]` invariant — the bound is a pydantic constraint on `Finding`/`Hypothesis`, so an unclamped aggregate would raise at model construction; deciding the rule here prevents that surfacing as a runtime failure in Task 3.
- **Step 3** routes the "non-trivial confidence summary" quality-gate requirement to a concrete input, while leaving the executing agent free to assemble the summary string in the synthesizer if that reads cleaner.
- **Step 4** locks the contracts: purity, totality, the confidence bound, well-formed links, and the distinctness sanity check that previews the phase gate. No live LLM call.
- **Step 5** is the local quality gate.

## Code locations

- `src/expertview/evidence/convergence.py` (new).
- `tests/unit/test_convergence.py` (new).

## Connections

**Upstream**:

- `evidence/models.py` — `Finding`, `Hypothesis`, `CausalLink`, `Symptom`, `Incident` (Phase 1). The only import this module needs beyond the standard library.

**Downstream**:

- [[task-3-wiring-and-verify]] imports `weight_finding`, `score_hypothesis`, and `link_causes` (and any summary helper) into `agents/synthesizer.py` and applies them to the LLM's draft report.
- Phase 6's UI renders the scored hypotheses as confidence bars; the per-hypothesis `confidence` that `score_hypothesis` computes is what the bars display.
- Phase 4's sub-investigator findings (stamped `investigator_domain="supply_chain"`) flow through `weight_finding` like any other finding — the weighting policy must define a weight for them without special-casing (covered by the step-4 totality assertion).

## Parallelism rationale

- This task is **parallelizable with Task 2**: it touches only `src/expertview/evidence/convergence.py` and `tests/unit/test_convergence.py`, while Task 2 touches only `data/`. No file overlap.
- It does **not** share editing surface with Task 3 either, but Task 3 depends on it (Task 3 imports its functions). The dependency is one-directional: this task produces, Task 3 consumes.
- [architecture.md §5](../../architecture.md)'s *"module boundaries are walls"* is what makes the parallelism safe — `evidence/` imports neither `agents/` nor `orchestration/`, so this module cannot accidentally couple to Task 3's wiring or to any investigator node.

## Risks / constraints / assumptions

- **Constraint**: module boundaries are walls ([architecture.md §5](../../architecture.md)). `evidence/convergence.py` imports only from `evidence/models.py` and the standard library — never from `agents/`, `orchestration/`, `rag/`, or any LLM-provider package. It is LLM-provider-pure.
- **Constraint**: cross-agent data goes through `evidence/models.py` pydantic models ([architecture.md §5](../../architecture.md)). Functions take and return `Finding` / `Hypothesis` / `CausalLink` — never raw dicts or tuples across the public surface.
- **Constraint**: the `evidence/models.py` models are `frozen=True` (immutable). `score_hypothesis` and `link_causes` must construct *new* models (e.g., via `model_copy(update=...)`), never attempt in-place mutation — a frozen-model mutation raises at runtime.
- **Constraint**: no `# TODO` without an entry in `open_questions.md` or `decisions.md` ([CLAUDE.md coding standards](../../../CLAUDE.md)); type hints on every public function.
- **Risk — over-fitting the weighting to the CNC scenario**: a `weight_finding` policy hand-tuned so the bearing/supply-chain finding always wins would pass the CNC `/verify` but fail the phase gate's distinctness requirement on the process-led incident. Mitigation: the weighting policy keys on structural properties (domain, citation count, finding confidence) common to all incidents, never on scenario-specific claim text; the step-4 distinctness test exercises a process-weighted finding set. This is the [build_plan.md §Phase 5 risk](../../build_plan.md) ("synthesizer over-fits to one scenario") addressed at the math layer.
- **Risk — confidence bound violation**: an unclamped aggregate that exceeds 1.0 raises when the resulting `Hypothesis` is constructed. Mitigation: step 2's aggregation rule clamps or normalizes; the step-4 test asserts `0.0 ≤ confidence ≤ 1.0` for representative inputs including a hypothesis with many high-weight findings.
- **Assumption**: the synthesizer LLM emits at least one `Hypothesis` with non-empty `supporting_findings` (already enforced by `agents/synthesizer.py`'s `_validate_report`). If a hypothesis arrives with zero supporting findings, `score_hypothesis` must still return a valid model (e.g., a defined floor confidence) rather than divide by zero — cover this edge in the test.
- **Assumption**: Task 3 decides whether `link_causes` generates links from scratch or re-scores LLM-drafted links. This task exposes a function that can do either by accepting the scored hypotheses (and incident) and returning links; the precise contract is finalized when Task 3 wires it. If Task 3 needs a different signature, that is a small follow-up, not a rework.

## Definition of done

- `src/expertview/evidence/convergence.py` exports `weight_finding`, `score_hypothesis`, and `link_causes` (plus any documented summary helper) as pure functions over `evidence/models.py` types, with type hints on every public function and one-line WHY comments on the non-obvious weighting/aggregation policy.
- The module imports nothing from `agents/`, `orchestration/`, `rag/`, or any LLM-provider package — confirmed by inspection of its import block.
- `score_hypothesis` and `link_causes` return new frozen models; no in-place mutation of inputs.
- `tests/unit/test_convergence.py` asserts purity, totality, the `[0.0, 1.0]` confidence bound, well-formed links, the zero-supporting-findings edge, and the two-finding-set distinctness sanity check.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/convergence-functions` per [branching_strategy.md §5](../../branching_strategy.md). PR description:
  - States the chosen `weight_finding` policy and `score_hypothesis` aggregation rule in one or two sentences, so the reviewer can judge whether they are scenario-neutral (the over-fitting guard).
  - Notes that this module sits unimported on `main` until [[task-3-wiring-and-verify]] wires it into the synthesizer.
  - Flags whether the confidence-summary helper lives here or is deferred to the synthesizer (Task 3 needs to know).
