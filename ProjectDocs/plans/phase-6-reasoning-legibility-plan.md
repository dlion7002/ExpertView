# Phase 6 — Decision & Reasoning Legibility Plan

## Problem

The flow does not feel *justified* on two surfaces:

1. **Dispatcher reads as a no-op.** `_dispatcher_node` returns `{}` and
   `_dispatcher_fanout` unconditionally sends to all five investigators
   ([runner.py:89-106](../../src/expertview/orchestration/runner.py#L89-L106)).
   The "Parallel Dispatcher" label implies a decision that is never made or
   shown.

2. **The final report discards its own reasoning.** The live run gathers
   conclusions from all five investigators (incl. environmental *ruling out*
   vibration, process/human-factors contributing-factor gaps), but the report:
   - collapses to a single originating hypothesis — the other domains' verdicts
     never appear;
   - has no narrative for *why* that cause is the conclusion;
   - shows no "considered but discarded" content;
   - uses a templated `confidence_summary` and templated causal-chain
     rationales (`_rescore_report` rebuilds the chain mechanically, dropping the
     LLM's drafted links).

The deductive material already lives in `state["findings"]`; it is dropped
before the report. Model output quality is *not* the issue — the missing layer
is the explanation.

## Locked decisions (from clarifying Q&A, 2026-05-27)

- **Reasoning source: hybrid (math + LLM narrative).** Convergence stays the
  sole source of the numbers; an LLM writes the qualitative narrative *grounded
  in those final numbers*.
- **Alternatives: one comparative paragraph** (not per-item rejection lines).
- **Dispatcher: left as-is.** Since it always activates all five investigators
  and takes no decision, the flow is honestly a deterministic pipeline at that
  stage. The user decided not to surface dispatcher reasoning. Section A below is
  **dropped from this pass**.

## Approach

### A. Dispatcher legibility — DROPPED (user decision, 2026-05-27)

The dispatcher stays a deterministic fan-out; no reasoning is shown there. No
change to `streaming.py`, `state.py`, the graph, or routing.

### B. Report reasoning (two-stage synthesizer; numbers stay deterministic)

- **`CausalReport` gains two narrative fields** (both default `""` so existing
  constructors stay valid):
  - `verdict_reasoning: str` — deductive narrative: from symptoms + cross-domain
    evidence to the chosen originating cause.
  - `alternatives_summary: str` — one paragraph: what else was considered (the
    non-adopted findings, the ruled-out environmental signal, the
    contributing-factor gaps) and why they are not the originating cause.
- **Deterministic basis helpers** in `evidence/convergence.py` (no new
  cross-boundary type): `corroborating_domains(hypothesis)` and
  `mean_evidence_weight(hypothesis)`, both reusing `weight_finding`. Used by
  both the stage-2 prompt builder and the renderer (single source of truth).
- **Stage-2 reasoning call** in `agents/synthesizer.py`: after `_rescore_report`
  assigns final numbers, render a new prompt (`prompts/synthesizer/reasoning.md`)
  with the incident, the re-scored ranked hypotheses + their deterministic
  basis, the causal chain, and the **full** findings list; call the same
  synthesizer LLM a second time; parse the JSON at the boundary into a small
  pydantic model; `model_copy` the two fields onto the report. Side-effect-free
  preserved (two `ainvoke` calls, no disk/state writes). No fallback on failure
  (propagates, consistent with stage-1).

### C. Rendering

- **Streamlit** (`ui/render.py`):
  - `_dispatcher_detail` → show the `DispatchDecision` rationale + per-domain
    lenses.
  - `render_causal_report` → add "Why this is the root cause" (verdict_reasoning)
    and "What else was considered" (alternatives_summary, one paragraph) blocks;
    add a deterministic "backed by N findings across M domains" basis line.
- **CLI** (`cli.py`):
  - dispatcher row detail → `DispatchDecision` rationale.
  - `_render_report` → a "Reasoning" panel (verdict_reasoning) and the
    alternatives paragraph.

## Affected files

- `src/expertview/evidence/models.py` — two new `CausalReport` fields (defaulted).
- `src/expertview/evidence/convergence.py` — two pure basis helpers.
- `src/expertview/agents/synthesizer.py` — stage-2 reasoning call + boundary model.
- `src/expertview/ui/render.py` — dispatcher detail + report reasoning blocks.
- `src/expertview/cli.py` — dispatcher detail + reasoning panel.
- `ProjectDocs/decisions.md` — log the locked decisions.

## New files

- `src/expertview/prompts/synthesizer/reasoning.md` — stage-2 reasoning prompt.

## Tests

- `tests/unit/test_synthesizer.py` — switch `FakeLlm` to a two-response sequence
  (stage-1 JSON, then reasoning JSON); assert both new fields populated and that
  the stage-2 prompt received the final confidences + findings.
- `tests/unit/test_convergence.py` — cover the two basis helpers.
- `tests/unit/test_cli.py` — reasoning panel render.

## Risks

- **Two LLM calls per synthesis** on the demo path (latency/cost). Acceptable —
  demo path only; reasoning is the point. No new dependency.
- **Test fakes** assume one `ainvoke`; must update to a sequenced fake.
- Narrative could drift from numbers — mitigated by feeding the LLM the final
  re-scored confidences + deterministic basis and instructing it to ground in
  them.

## Out of scope (deliberately)

- No change to investigation behavior — investigators still run from the
  incident; the dispatch briefing is legibility, not a gate.
- No rewrite of the convergence causal-chain rebuild (symptom links stay; the
  user confirmed those are fine). The new narrative *references* the full
  picture instead of restructuring the chain.
- Selective/skipping triage in the dispatcher (rejected: would break the
  always-parallel cross-domain-convergence story).
