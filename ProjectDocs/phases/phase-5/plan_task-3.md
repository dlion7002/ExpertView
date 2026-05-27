# Plan — Phase 5 Task 3 (Wire convergence into synthesizer + integration test + /verify)

> Working plan for the execution session. Scope source: [task-3-wiring-and-verify.md](task-3-wiring-and-verify.md).
> Branch: `feature/phase-5-convergence-wiring`. PR scope: **Task 3 code only** (no unrelated untracked files).

## Affected files

- **Edit** `src/expertview/agents/synthesizer.py` — import convergence functions; insert post-LLM re-scoring between `_parse_causal_report` and `_validate_report`; return the re-scored report. Node stays a pure `(State) -> {"causal_report": ...}`.
- **New** `tests/integration/test_convergence.py` — two-incident distinctness regression test on `make_graph()` with deterministic fakes (mirrors `tests/integration/test_dynamic_spawning.py`).
- **Edit** `ProjectDocs/decisions.md` — log the post-LLM re-scoring design + reranker-deferral (decision is already locked by the Phase 5 README Q&A).
- **Conditional** `src/expertview/prompts/synthesizer/default.md` — **only if** live `/verify` shows the prompt and re-scoring producing incoherent output. Default: unchanged. Citation-preservation section stays intact regardless.

## Change sketch — `synthesizer.py`

Imports: `from expertview.evidence.convergence import link_causes, score_hypothesis`
(plus `Hypothesis` from `evidence.models`).

In `synthesizer_node`, replace the parse→validate→return tail with:

```
draft = _parse_causal_report(_response_text(response))
report = _rescore_report(draft, incident)
_validate_report(report, incident)
return {"causal_report": report}
```

New private helpers (synthesizer-local; presentation/derivation, not evidence math):

- `_rescore_report(draft, incident) -> CausalReport`
  - `scored = [score_hypothesis(h) for h in draft.top_hypotheses]`
  - `ranked = sorted(scored, key=_hypothesis_rank_key)` — same key `link_causes` uses, so `top_hypotheses[0]` == the chain's first cause.
  - `causal_chain = link_causes(ranked, incident)` (`score_hypothesis` is idempotent, so re-scoring inside `link_causes` is consistent).
  - `summary = _summarize_confidence(ranked)`
  - return `draft.model_copy(update={"top_hypotheses": ranked, "causal_chain": causal_chain, "confidence_summary": summary})` — new frozen model, no mutation; `incident_id`/`generated_at` and every `supporting_findings` citation carried over verbatim.
- `_hypothesis_rank_key(h)` → `(-h.confidence, h.domain_origin, h.id, h.claim)`.
- `_summarize_confidence(ranked)` → reflects computed scores (dominant domain, top confidence, margin over runner-up, hypothesis/domain spread). Guards the empty list (returns a no-hypothesis sentence) so the empty-hypotheses case still falls through to `_validate_report`'s existing "at least one hypothesis" ValueError.

`_validate_report` runs on the **final** re-scored report (unchanged).

## Integration test — `tests/integration/test_convergence.py`

Mirror the `test_dynamic_spawning.py` harness (fake stores, fake investigator LLM, fake synthesizer LLM, monkeypatched runner factories + loaders). Two legs:

- **CNC leg**: fake synthesizer drafts a strong mechanical+supply_chain hypothesis (raw LLM confidence deliberately ≠ computed) and a weak process hypothesis; run against `data/incidents/cnc_out_of_tolerance.yaml`'s `Incident`.
- **Process leg**: strong process+environmental hypothesis vs. weak mechanical; run against `data/incidents/process_recipe_drift.yaml`'s `Incident` (id `imm-fill-drift-2026-05-26-changeover`).

Assertions:
- The two reports' top hypotheses differ (by `claim` and `domain_origin`).
- CNC top `domain_origin` ∈ {mechanical, supply_chain}; process top `domain_origin` == process.
- Each `confidence_summary` is non-empty and varies with the data (not a constant).
- **Re-scoring actually ran**: top hypothesis's final `confidence` == `score_hypothesis(draft_hypothesis).confidence`, ≠ the raw value the fake LLM emitted.
- Every input citation still present in the re-scored report's `supporting_findings`.

No OpenRouter call — fakes return hard-coded JSON; runs in CI.

## Verification

1. `uv run pytest` (green) — existing synthesizer/spawning/end-to-end tests stay compatible (verified by reasoning: single-hypothesis re-score keeps contract; empty-hypotheses still raises; dynamic-spawning asserts only type+id).
2. `uv run ruff check .` and `uv run ruff format --check .` clean.
3. Live `/verify` (per user: run now, free-tier synth):
   - `uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml`
   - `uv run python -m expertview.cli demo --incident data/incidents/process_recipe_drift.yaml`
   - Confirm top hypotheses differ (CNC → mechanical/supply-chain; process → process), confidence summaries non-trivial, citations present, LangSmith trace pointer if key set.
   - If the prompt and re-scoring visibly conflict, apply the conditional prompt narrowing and re-run.

## Decisions.md entry

`## 2026-05-27 — Phase 5 post-LLM re-scoring wiring + reranker deferral` — records that the synthesizer applies deterministic re-scoring after the LLM draft, the confidence_summary is assembled from computed scores, and the reranker stays deferred unless retrieval (not convergence) proves the bottleneck.

## Branch / PR

- `git switch -c feature/phase-5-convergence-wiring`
- Stage **only**: `src/expertview/agents/synthesizer.py`, `tests/integration/test_convergence.py`, `ProjectDocs/decisions.md` (+ prompt if edited). Leave `.claude/skills/`, `phase-4/`, `phase-5/`, deleted handoff untouched.
- Commit, push, open PR with the DoD body (re-scoring summary, prompt-iteration note, side-by-side top hypotheses, citation-contract confirmation), return URL.

## Risks

- Citations dropped during re-scoring — mitigated: `score_hypothesis`/`model_copy` carry `supporting_findings` verbatim; test asserts.
- No-op re-scoring (dead convergence) — mitigated: test asserts final confidence == `score_hypothesis` output ≠ raw LLM value.
- Two reports collapse to same top cause — mitigated: domain-distinct fakes in test; live verify is the real gate.
- OpenRouter 429s on two live runs — sequential runs; Phase 3 semaphore caps per-run concurrency.
- Empty-hypotheses edge — `_summarize_confidence` guards it; `_validate_report` still raises the expected ValueError.
