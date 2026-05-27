# Task 2 — Second Rehearsed Incident (Process-Led) + Corpus Clues

> **Branch suggestion**: `feature/second-incident`
> **Parallelism**: **Parallelizable with Task 1.** Pure data authoring — touches only `data/incidents/` and `data/domains/`; no Python, no shared surface with Task 1's `evidence/` module.
> **Depends on**: Phase 4 complete (`v0.5.0-demo` tagged). Reuses the incident YAML shape from `data/incidents/cnc_out_of_tolerance.yaml` (Phase 2) and the five domain corpora under `data/domains/` (Phases 2–4).

## Purpose

Author the second rehearsed incident the phase quality gate requires — a **process-led** scenario whose root cause lives in the `process` domain, in deliberate contrast to the mechanical / supply-chain-led CNC scenario. The deliverable is a new `data/incidents/<slug>.yaml` matching the locked incident schema plus the planted corpus clues that let the existing investigators retrieve evidence pointing at a *process* root cause, so that when Task 3 runs both incidents the two reports name different top causes.

This task is **data only**. It does not touch any file under `src/` and does not run the graph end-to-end — that is [[task-3-wiring-and-verify]]'s job. It does not author convergence math — that is [[task-1-convergence-functions]]. Its job is to make sure a second, genuinely different causal chain is *retrievable* from the corpora before Task 3 wires and verifies.

## Why it matters

- [build_plan.md §Phase 5](../../build_plan.md) names "a second rehearsed incident in `data/incidents/` that exercises a different domain" as a phase output, and the quality gate requires the two incidents' top hypotheses to differ. Without a second incident with a different retrievable root cause, the gate cannot be met.
- The [build_plan.md §Phase 5 risk](../../build_plan.md) is that the synthesizer over-fits to one scenario; "the second incident is the safety check." That safety check only works if the second incident's evidence genuinely leads elsewhere — a re-skin of the CNC chain would let an over-fit pipeline pass anyway.
- The hybrid mock-corpus decision ([decisions.md 2026-05-25 Q4](../../decisions.md)) governs this work: Claude drafts the volume, the user hand-curates so the planted clues land in the documents the process investigator actually retrieves. The same discipline that made the CNC scenario work applies here.
- [decisions.md (2026-05-25 CNC scenario)](../../decisions.md) noted that in the CNC scenario the process domain was "the synthesizer's job to connect the threads" — it never led. Leading the second incident with process is the cleanest available contrast and gives the process corpus its first turn as the source of a root cause.

## Concrete steps (what to produce)

1. **Choose and pin the process-led scenario.** A concrete, demo-legible manufacturing incident whose root cause is a *process* fault — for example a recipe / setpoint-drift defect where a product changeover applied a stale or unvalidated process parameter (barrel-temperature profile, hold-pressure, feed rate, tolerance band), and the symptoms point at a parameter problem rather than a worn part or a bad supplier batch. The exact scenario is the executing agent's call in collaboration with the user-curator, subject to one constraint: the root cause must sit in the `process` domain, and mechanical / supply-chain / environmental / human-factors evidence must be present but *non-causal* (so the contrast with the CNC scenario is real). State the chosen scenario in one paragraph at the top of the PR description.
2. **Write `data/incidents/<slug>.yaml`** matching the locked schema in `data/incidents/cnc_out_of_tolerance.yaml`: `id`, `summary`, `observed_at` (ISO-8601 with offset), `symptoms` (list of concrete observable strings), `affected_assets` (list of asset ids). The `id` must be unique and distinct from the CNC incident's id (the synthesizer's `_validate_report` asserts the report's `incident_id` matches the input incident id, so a clean unique id matters). Symptoms should read as process-parameter symptoms (e.g., dimensional or fill drift correlated with a changeover or a recipe edit), not as the CNC mechanical chatter/bore-drift symptoms.
3. **Plant the process root-cause clues in `data/domains/process/`.** Add 2–4 short markdown documents (each under ~200 lines, plausible, on-topic) carrying the retrievable evidence the process investigator needs: e.g., a recipe / parameter change log showing the stale-revision setpoint applied at the changeover, a process-validation or first-article record showing the parameter was never re-validated for the new product, and a control-plan or SPC excerpt tying the drifting symptom to that parameter. These are the documents whose retrieval makes the process hypothesis win. Per the [hybrid-corpus decision](../../decisions.md), Claude drafts them and the user curates so they plant the clue without stating the conclusion outright.
4. **Add light non-causal cross-domain evidence where it sharpens the contrast** (optional, scenario-dependent). To make the second incident feel like a real multi-domain investigation rather than a single-domain lookup, add brief entries to one or two *other* domain corpora that the relevant investigators will retrieve but that do **not** point at the root cause (e.g., a mechanical maintenance log showing the machine was recently serviced and is within spec, or a supply-chain note confirming the material batch was qualified and clean). Keep these minimal — their job is to give the convergence layer non-winning findings to down-weight, demonstrating evidence-weighting rather than single-source retrieval. Do not add so much cross-domain noise that the process clue stops winning.
5. **Sanity-check retrievability without running the graph.** Confirm the planted process clues are phrased so a query derived from the incident's symptoms would surface them — i.e., the symptom vocabulary in the YAML and the clue vocabulary in the process docs share retrievable terms. This is a read-through check, not a code run; the live retrieval proof happens in Task 3's `/verify`. (If the executing agent wants a stronger check, a single ad-hoc load of the process store via the Phase 3 loader against one symptom query is acceptable, but it is not required by this task.)
6. **Verify locally**: `uv run pytest` green (no test should regress from adding data files) and `uv run ruff check .` / `uv run ruff format --check .` clean. There is no new test in this task — the integration test lives in Task 3.

## What each step does

- **Step 1** pins the scenario and its root-cause domain, so the planted clues and the contrast with the CNC scenario are deliberate rather than emergent.
- **Step 2** produces the incident artifact in the locked schema with a unique id, so the synthesizer's id-match validation passes and the two incidents are unambiguously distinct.
- **Step 3** plants the retrievable process evidence — the load-bearing step. If these clues are absent or unretrievable, the process investigator returns generic findings and the second report's top hypothesis collapses back toward the CNC chain, failing the gate.
- **Step 4** gives the convergence layer non-causal cross-domain findings to down-weight, so the second `/verify` demonstrates *weighting* and not just single-domain retrieval — without drowning the process clue.
- **Step 5** is a cheap read-through guard against the most common failure: clue documents whose vocabulary does not overlap the incident symptoms, so retrieval never surfaces them.
- **Step 6** confirms no existing test regresses and the repo stays lint-clean.

## Code locations

- `data/incidents/<slug>.yaml` (new — slug indicative, e.g. `process_recipe_drift.yaml`).
- `data/domains/process/<clue>.md` × 2–4 (new — filenames indicative; the planted process root-cause clues).
- `data/domains/<other>/<note>.md` (optional new — minimal non-causal cross-domain evidence, only if it sharpens the contrast).

## Connections

**Upstream**:

- `data/incidents/cnc_out_of_tolerance.yaml` (Phase 2) — the incident-schema reference this new YAML mirrors.
- `data/domains/process/` (Phase 3) — the existing process corpus this task extends with root-cause clues.
- The five Phase 3 domain loaders under `rag/domains/` consume these files at retrieval time; they cache per-corpus and re-embed on corpus change, so the new documents are picked up on the next graph run with no loader edit.

**Downstream**:

- [[task-3-wiring-and-verify]] runs `python -m expertview.cli demo --incident data/incidents/<slug>.yaml` as the second leg of its `/verify`, and the integration test in Task 3 references this incident id to assert its top hypothesis differs from the CNC report's.
- Phase 6's demo may offer both incidents as selectable inputs; this YAML is the second option.
- Phase 7's rehearsal script may use this incident as a fallback scenario per [build_plan.md §Hour 7–8](../../build_plan.md).

## Parallelism rationale

- This task is **parallelizable with Task 1**: it touches only `data/incidents/` and `data/domains/`, while Task 1 touches only `src/expertview/evidence/` and `tests/unit/`. No file overlap, no import relationship.
- It shares no editing surface with Task 3 either; Task 3 *reads* this incident at `/verify` time and *references* its id in the integration test, but does not edit any file this task creates.
- The corpus additions into `data/domains/process/` are a cross-phase touch — Phase 3 authored the original process corpus; this task adds sibling clue files. The loader's cache invalidates on corpus change, so Task 3's first `/verify` re-embeds the process corpus once. No loader code edit is required.

## Risks / constraints / assumptions

- **Constraint**: the incident YAML matches the locked schema fields in `data/incidents/cnc_out_of_tolerance.yaml` exactly (`id`, `summary`, `observed_at`, `symptoms`, `affected_assets`). A missing or renamed field breaks `Incident` model construction at CLI load time.
- **Constraint**: the incident `id` is unique and distinct from the CNC incident's id — the synthesizer's `_validate_report` raises if the report's `incident_id` does not match the input incident id, and a duplicate id would conflate the two scenarios.
- **Constraint**: corpus documents are hand-curated after the Claude draft ([decisions.md 2026-05-25 Q4](../../decisions.md)) — the curation pass is what keeps the process clues from stating the conclusion outright while still planting it retrievably.
- **Risk — the second incident is a re-skin of the CNC chain**: if the symptoms or planted clues drift back toward bearing/hydraulic/supplier themes, an over-fit pipeline produces near-identical top hypotheses and the gate's "top hypothesis differs" requirement fails. Mitigation: the root cause is pinned to the `process` domain in step 1, the process clues in step 3 carry recipe/parameter vocabulary distinct from the CNC mechanical/supply vocabulary, and the PR description states the intended root cause explicitly so a reviewer can confirm the contrast.
- **Risk — process clue not retrievable**: if the clue documents' vocabulary does not overlap the incident symptoms, the process investigator never surfaces them and the process hypothesis cannot win. Mitigation: step 5's read-through (or optional ad-hoc load) check.
- **Risk — cross-domain noise overwhelms the process clue**: too much non-causal cross-domain evidence (step 4) can let a competing domain's findings out-weight the process finding, inverting the intended top cause. Mitigation: keep step-4 additions minimal and explicitly non-causal; the convergence layer is meant to down-weight them, not be defeated by volume.
- **Risk — embedding cache staleness**: if the process loader's cache key does not invalidate on the new files, Task 3's `/verify` retrieves the old index and the clues never appear. Mitigation: confirm the loader re-embeds on corpus change (the Phase 4 sub-investigator task relied on the same behavior); if the cache key is path-list-based, confirm the new filenames are picked up.
- **Assumption**: the existing five domain prompts are scenario-neutral enough to investigate a process-led incident without per-incident prompt edits. If the process investigator prompt is too CNC-specific to produce a useful process finding on the new incident, that surfaces in Task 3's `/verify` as a prompt-iteration item ([decisions.md / build_plan §Path A prompt-tuning](../../build_plan.md)), not a corpus problem — note it for Task 3 rather than editing prompts here (prompt edits are out of this data-only task's scope).

## Definition of done

- `data/incidents/<slug>.yaml` exists, matches the locked incident schema, has a unique `id` distinct from the CNC incident, and describes a scenario whose root cause is in the `process` domain.
- 2–4 process clue documents exist under `data/domains/process/`, each under ~200 lines, plausible, on-topic, and carrying retrievable evidence for the process root cause without stating the conclusion outright.
- Any optional cross-domain non-causal evidence added is minimal and does not out-weight the process clue.
- The incident-symptom vocabulary and the process-clue vocabulary share retrievable terms (step-5 read-through confirmed).
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green (no regression from the added data files).
- PR opened on `feature/second-incident` per [branching_strategy.md §5](../../branching_strategy.md). PR description:
  - States the chosen scenario and names the intended `process`-domain root cause in one paragraph, so the reviewer can confirm it contrasts with the CNC chain.
  - Names which corpus files most need curator attention (the process change-log and validation-record files are the likely candidates — they are the ones that, mis-curated, either give the answer away or fail to plant it).
  - Confirms the incident `id` is unique and distinct from `cnc-out-of-tolerance-2026-05-24-shift-3`.
  - Notes that this incident is not yet wired into any test or `/verify` — [[task-3-wiring-and-verify]] consumes it once merged.
