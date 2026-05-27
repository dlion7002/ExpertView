# Task 3 — Wire Convergence into the Synthesizer + Two-Incident Integration Test + Parallel `/verify`

> **Branch suggestion**: `feature/phase-5-convergence-wiring`
> **Parallelism**: **Sequential.** Final merge point of Phase 5. Edits `agents/synthesizer.py` (and possibly `prompts/synthesizer/default.md`) and adds the integration test; must run after Tasks 1 and 2 are merged to `main`.
> **Depends on**: Task 1 merged (`evidence/convergence.py` exports the re-scoring functions) and Task 2 merged (the process-led incident YAML and its corpus clues are on `main` under `data/incidents/` and `data/domains/process/`).

## Purpose

Make the convergence layer load-bearing. Today `agents/synthesizer.py` parses the LLM's `CausalReport` and returns it verbatim. After this task the synthesizer applies the locked **post-LLM re-scoring** design: the LLM still drafts hypotheses and causal links, then `evidence/convergence.py` deterministically re-weights finding confidence by source, re-scores each hypothesis, orders the causal chain, and produces a confidence summary that reflects the computed scores. The returned `CausalReport`'s numbers become reproducible Python, not LLM whim — which is what makes "evidence-weighted convergence" a real, testable property rather than a prompt instruction.

Also lands in this task:

- A possible small iteration of `prompts/synthesizer/default.md` so the LLM's role narrows to *proposing* hypotheses and links while convergence owns the final `confidence` / `strength` numbers — only if `/verify` shows the prompt and the re-scoring fight each other.
- `tests/integration/test_convergence.py` — runs both rehearsed incidents through `make_graph()` with deterministic fake stores and fake LLMs and asserts the two reports name different top hypotheses with non-trivial confidence summaries. No OpenRouter call; runs in CI.
- End-to-end `/verify` against both incidents. The phase quality gate is satisfied here: both incidents produce reports where the top hypothesis differs and the confidence summary is non-trivial.

## Why it matters

- Until Task 3 ships, `evidence/convergence.py` sits unimported on `main` (Task 1) and the process-led incident has no test or `/verify` consuming it (Task 2). This is the task where the convergence math and the second incident stop being separate artifacts and become the demonstrated phase behavior.
- [build_plan.md §Phase 5](../../build_plan.md) requires "the synthesizer applies confidence scoring + causal linking across findings." The synthesizer edit here is what makes that literally true — the synthesizer *calls* the scoring and linking functions.
- The phase quality gate has a **silent-pass mode**: if the synthesizer returns the LLM's draft confidences unchanged, two incidents can still produce two reports, but the "evidence-weighted" claim is hollow and the convergence module is dead code. The integration test in step 3 and the `/verify` assertions in step 4 are designed so a green run actually exercises the re-scoring path, not just the LLM's own output.
- The locked post-LLM design keeps the synthesizer side-effect-free ([architecture.md §5](../../architecture.md)): re-scoring is a pure transform of the parsed report into a re-scored report; the node still returns only `{"causal_report": ...}`, writes no disk, spawns nothing.

## Concrete steps (what to produce)

1. **Import the convergence functions into `agents/synthesizer.py`** from `evidence/convergence.py` (`weight_finding`, `score_hypothesis`, `link_causes`, and any summary helper Task 1 exposed). This is an `agents/ → evidence/` import — the existing, allowed direction ([architecture.md §5](../../architecture.md)); the synthesizer already imports `evidence/models.py`.
2. **Insert the re-scoring step between parse and return.** In the node body, after `_parse_causal_report(...)` produces the LLM's draft `CausalReport` and before the node returns its patch:
   - Re-score each hypothesis in `top_hypotheses` via `score_hypothesis` (which recomputes `confidence` from its supporting findings' weights).
   - Re-order `top_hypotheses` by the re-scored confidence so the top hypothesis is the highest-weighted one (the "top cause").
   - Re-build or re-score the `causal_chain` via `link_causes` so link `strength` reflects the scored hypotheses.
   - Assemble a `confidence_summary` that reflects the computed scores (dominant domain, top-hypothesis margin, or spread) — non-trivial per the quality gate.
   - Construct a **new** `CausalReport` from the re-scored parts (the model is `frozen=True`; use `model_copy(update=...)` or a fresh constructor — do not mutate). Keep `incident_id` and the citation contract intact: every citation present in the input findings must still appear in the re-scored report's `supporting_findings` (the [synthesizer prompt's citation-preservation rule](../../../src/expertview/prompts/synthesizer/default.md) is the credibility surface; re-scoring must not drop citations).
   - Keep `_validate_report` running on the final re-scored report so the id-match and non-empty-hypotheses invariants still hold.
   The node remains a pure `(State) -> dict` returning `{"causal_report": CausalReport(...)}` — no new side effects.
3. **Iterate `prompts/synthesizer/default.md` only if needed.** Re-scoring overrides the LLM's `confidence` and `strength` numbers, so the prompt's current instruction to have the LLM produce calibrated confidences is now partly moot. If `/verify` shows the LLM and the re-scoring producing contradictory or incoherent reports, narrow the prompt so the LLM *proposes* hypotheses, supporting findings (with citations preserved verbatim), and causal-link rationales, while stating that final numeric confidence/strength are assigned downstream. This edit is **conditional** — make it only if `/verify` demands it, and record the prompt diff in the PR. The citation-preservation section of the prompt stays unchanged regardless.
4. **Add `tests/integration/test_convergence.py`** running both incidents through `make_graph()` with deterministic fakes (mirror the fake-store / fake-LLM pattern in `tests/integration/test_dynamic_spawning.py`):
   - **CNC leg**: fakes return mechanical/supply-chain-weighted findings; invoke the graph against `data/incidents/cnc_out_of_tolerance.yaml`'s `Incident`; capture the report.
   - **Process leg**: fakes return process-weighted findings; invoke the graph against the Task 2 incident's `Incident`; capture the report.
   - Assert: the two reports' top hypotheses differ (by `claim` and/or `domain_origin`); each report's `confidence_summary` is non-trivial (non-empty and reflects the scoring, not a constant string); each report's top hypothesis's `domain_origin` matches the incident's intended lead domain (mechanical/supply-chain for CNC, process for the second incident). Assert the re-scoring actually ran — e.g., a hypothesis's final `confidence` equals what `score_hypothesis` computes for its findings, not the raw value the fake LLM emitted.
   The test does not hit OpenRouter — fake LLMs return hard-coded JSON. It is the CI **regression guard** that catches a future refactor bypassing the re-scoring or collapsing the two scenarios to one top cause.
5. **Run the end-to-end `/verify` against both incidents**:
   - `uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml`
   - `uv run python -m expertview.cli demo --incident data/incidents/<second-slug>.yaml`
   - Confirm: each run prints a coherent `CausalReport` with citations.
   - Confirm: the **top hypotheses differ** between the two reports — the CNC report's top cause is mechanical/supply-chain (bearing/hydraulic/supplier), the second report's top cause is the process root cause from Task 2.
   - Confirm: each `confidence_summary` is non-trivial — it reflects the computed weighting (names a dominant domain or describes the spread), not a boilerplate sentence.
   - Confirm: the LangSmith trace for each run shows the investigator fan-out and the synthesizer span as before; re-scoring is in-process Python and needs no new span, but the synthesizer span's output is the re-scored report.
6. **Verify locally**: `uv run pytest` green; `uv run ruff check .` and `uv run ruff format --check .` clean; the manual two-incident `/verify` from step 5 satisfies the differ-top-hypothesis and non-trivial-summary assertions.

## What each step does

- **Step 1** brings the convergence functions into the only module allowed to call them in the orchestration path — the synthesizer — via the existing `agents/ → evidence/` import direction.
- **Step 2** is the core of the phase: it inserts deterministic re-scoring between the LLM draft and the returned report, making the confidence numbers reproducible Python while preserving the synthesizer's purity and the citation contract.
- **Step 3** resolves the tension between the prompt (which asks the LLM for confidences) and the re-scoring (which overrides them), but only if `/verify` shows they conflict — avoiding speculative prompt churn.
- **Step 4** locks both scenarios as a deterministic CI regression test, proving the re-scoring path runs and the two top causes diverge without spending OpenRouter budget.
- **Step 5** is the quality gate itself: the live two-incident `/verify` is the DoD; without two runs showing different top hypotheses and non-trivial summaries, the phase is not done.
- **Step 6** is the local check before opening the PR.

## Code locations

- `src/expertview/agents/synthesizer.py` (edit — import convergence functions; insert the re-scoring step between parse and return; keep `_validate_report` on the final report).
- `src/expertview/prompts/synthesizer/default.md` (conditional edit — narrow the LLM's role to proposing, only if `/verify` requires it; citation-preservation section unchanged).
- `tests/integration/test_convergence.py` (new — two-incident distinctness regression test with deterministic fakes).

## Connections

**Upstream**:

- [[task-1-convergence-functions]] — provides `weight_finding`, `score_hypothesis`, `link_causes` (and any summary helper), imported by `agents/synthesizer.py`.
- [[task-2-second-incident]] — provides the process-led incident YAML (consumed by `/verify` and referenced by the integration test) and the planted process clues (retrieved at `/verify` time).
- Phase 2 — `agents/synthesizer.py` (the node this task edits; the parse/validate scaffolding is reused, the return value changes), `prompts/synthesizer/default.md` (the prompt possibly iterated).
- Phase 1 — `evidence/models.py` (`CausalReport`, `Hypothesis`, `CausalLink`, `Finding`, `Symptom`), `orchestration/state.py` (`ExpertViewState`; the synthesizer reads merged `findings` from it).
- Phase 4 — `tests/integration/test_dynamic_spawning.py` is the fake-store / fake-LLM pattern reference for the new integration test; `orchestration/runner.py`'s `make_graph()` is invoked unchanged (no topology edit in this phase).

**Downstream**:

- Phase 6's UI renders the re-scored `top_hypotheses` as confidence bars and the `confidence_summary` as report text; the numbers it shows are the ones `score_hypothesis` computes here.
- Phase 7's rehearsal exercises the synthesizer swap to the paid frontier model; the re-scoring runs identically regardless of which synthesizer model drafts the hypotheses, so the swap does not change the convergence math.
- The locked post-LLM re-scoring design is logged in [decisions.md](../../decisions.md) when this task lands (per [CLAUDE.md workflow rule 5](../../../CLAUDE.md) — log the decision the turn it locks).

## Parallelism rationale

- This task is **sequential by necessity**: it imports Task 1's functions and consumes Task 2's incident, and it edits `agents/synthesizer.py` (shared) plus possibly `prompts/synthesizer/default.md`. Either edit would conflict if attempted before Tasks 1 and 2 land.
- It is the final-merge pinch point: Tasks 1 and 2 prove the convergence math and the second incident in isolation; Task 3 proves they work together when the synthesizer applies the math to a real second scenario.
- It touches no investigator node, no loader, and no graph topology — the convergence is entirely inside the synthesizer node body, so [architecture.md §5](../../architecture.md)'s walls are respected (`agents/synthesizer.py` imports from `evidence/`, the existing direction).

## Risks / constraints / assumptions

- **Constraint**: the synthesizer is side-effect-free ([architecture.md §5](../../architecture.md)) — it returns only `{"causal_report": ...}`, writes no disk, spawns nothing. Re-scoring is a pure transform inside the node; it adds no side effect.
- **Constraint**: LLM clients live only in `agents/llms.py` ([CLAUDE.md architecture rules](../../../CLAUDE.md)). This task constructs no LLM; it consumes the synthesizer client `make_graph()` already passes in.
- **Constraint**: prompts live as files under `src/expertview/prompts/` ([CLAUDE.md hard rules](../../../CLAUDE.md)). Any prompt iteration in step 3 edits `prompts/synthesizer/default.md` — never an inline f-string in `synthesizer.py`.
- **Constraint**: `evidence/models.py` models are `frozen=True`. The re-scored report is a *new* `CausalReport` (and new `Hypothesis` / `CausalLink` objects); no in-place mutation.
- **Risk — citations dropped during re-scoring**: rebuilding hypotheses can accidentally lose the verbatim `supporting_findings` / `citations` that the prompt's citation-preservation rule guarantees. Mitigation: `score_hypothesis` copies all non-confidence fields verbatim (Task 1 contract); the integration test in step 4 asserts every input citation still appears in the re-scored report.
- **Risk — silent dead-code convergence**: if the re-scoring is wired but its output equals the LLM's draft (e.g., the weighting is a no-op), the convergence module is effectively dead and the "evidence-weighted" claim is hollow even though `/verify` passes. Mitigation: the step-4 test asserts a hypothesis's final confidence equals `score_hypothesis`'s computed value, not the fake LLM's raw value — a no-op re-scoring fails this assertion.
- **Risk — two reports collapse to the same top cause**: if Task 2's process clues are weak or the weighting over-favors one domain, both incidents may surface the same top hypothesis and the gate fails. Mitigation: the step-4 test exercises both legs with domain-distinct fake findings; if live `/verify` collapses them, the cause is either Task 2's corpus (weak/unretrievable clue — a Task 2 follow-up) or Task 1's weighting (scenario-biased — a Task 1 follow-up), and the `/verify` notes which.
- **Risk — prompt vs. re-scoring incoherence**: the LLM, told to produce confidences, may also re-order or editorialize in ways the re-scoring then contradicts (e.g., a `confidence_summary` the LLM wrote that no longer matches the re-scored numbers). Mitigation: step 3's conditional prompt iteration narrows the LLM's role; the synthesizer assembles the final `confidence_summary` from the computed scores rather than trusting the LLM's.
- **Risk — `/verify` LangSmith trace appears empty or partial**: tracing depends on the Phase 1 env-var setup. Mitigation: confirm `LANGSMITH_API_KEY` is set before declaring `/verify` complete (re-run a Phase 4 `/verify` first if the trace surface looks empty). Re-scoring itself needs no trace — it is in-process Python.
- **Risk — OpenRouter free-tier limits during two live `/verify` runs**: two end-to-end runs mean up to twelve investigator-class LLM calls plus two synthesizer calls. Phase 3's `asyncio.Semaphore(5)` caps concurrency within each run. Mitigation: run the two incidents sequentially (not concurrently); if 429s appear, the same mitigation as Phase 3 applies (lower the cap), and Phase 7's retry/backoff is the real fix.
- **Assumption**: the process investigator prompt is scenario-neutral enough to produce a useful process finding on Task 2's incident. If `/verify` shows the process investigator returning generic findings on the second incident, that is a prompt-iteration item (edit `prompts/investigator/process.md`) surfaced by Task 2's note — handle it inside this task if it blocks the gate, and record the prompt diff in the PR.
- **Assumption**: the reranker remains deferred ([Phase 5 README pre-flight](README.md)). If `/verify` shows the *retrieval* (not the convergence) is why the process hypothesis loses, that is the trigger to reconsider the local CrossEncoder per [architecture.md §7](../../architecture.md) — as a separate follow-up with its own [decisions.md](../../decisions.md) entry, not an edit inside this task.

## Definition of done

- `agents/synthesizer.py` imports the convergence functions from `evidence/convergence.py` and applies post-LLM re-scoring: hypotheses re-scored via `score_hypothesis`, `top_hypotheses` ordered by re-scored confidence, `causal_chain` re-scored/linked via `link_causes`, and a `confidence_summary` assembled from the computed scores.
- The synthesizer node still returns only `{"causal_report": CausalReport(...)}`, constructs new frozen models (no mutation), preserves every input citation, and keeps `_validate_report` running on the final report.
- `prompts/synthesizer/default.md` is either unchanged or iterated to narrow the LLM's role (confidences assigned downstream), with the citation-preservation section intact; any diff is recorded in the PR.
- `tests/integration/test_convergence.py` exists and passes: both incidents run through `make_graph()` with deterministic fakes; the two top hypotheses differ; each `confidence_summary` is non-trivial; the re-scoring is asserted to have actually run (final confidence equals `score_hypothesis`'s output, not the fake LLM's raw value).
- Manual `/verify` against both incidents succeeds:
  - `data/incidents/cnc_out_of_tolerance.yaml` → top cause is mechanical/supply-chain.
  - `data/incidents/<second-slug>.yaml` → top cause is the process root cause from Task 2.
  - The two reports' top hypotheses differ and both `confidence_summary` strings are non-trivial.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/phase-5-convergence-wiring` per [branching_strategy.md §5](../../branching_strategy.md). PR description:
  - States that the synthesizer now applies post-LLM re-scoring and summarizes the re-scoring flow in two or three sentences.
  - Notes whether `prompts/synthesizer/default.md` was iterated and links the diff if so.
  - Records the two incidents' top hypotheses side by side, demonstrating they differ (the quality-gate evidence).
  - Confirms the citation contract survived re-scoring (every input citation present in the final report).
  - Flags whether any process-investigator prompt iteration was required to surface the process root cause, and links that diff if so.
- Once merged, log the post-LLM re-scoring design and the reranker-deferral in [decisions.md](../../decisions.md), then tag `v0.6.0-demo` per [branching_strategy.md §8](../../branching_strategy.md). Phase 6 (demo surface) is unblocked.
