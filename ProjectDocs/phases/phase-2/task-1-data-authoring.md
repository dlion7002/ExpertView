# Task 1 — Data Authoring (Mechanical Corpus + CNC Incident)

> **Branch suggestion**: `data/mechanical-corpus-and-incident`
> **Parallelism**: **Sequential.** Blocks Task 2 (the loader has nothing to read without these files) and Task 5 (the `/verify` run rehearses against the CNC incident).
> **Depends on**: Phase 1 complete (the package + schemas + state must exist so the YAML can be validated against `Incident`).

## Purpose

Land the data Phase 2 needs to be demonstrable: the 5–10 mock mechanical-domain documents that the mechanical investigator will retrieve from, and the rehearsed CNC out-of-tolerance incident YAML that the CLI demo replays. This is the corpus the entire vertical slice will point at; everything downstream is meaningless without it.

Authoring approach is hybrid per [decisions.md (2026-05-25 Q4 mock corpora)](../../decisions.md): the executing agent drafts initial content; the user reviews and hand-curates the clue trail so the demo's causal chain is satisfying.

## Why it matters

- [decisions.md (2026-05-25 Q2 demo incident)](../../decisions.md) locks the CNC out-of-tolerance scenario: shift 3, line 2, post-hydraulic-cylinder maintenance, new-supplier bearing batch. The corpus must plant retrievable evidence for that causal chain.
- [build_plan.md §Phase 2](../../build_plan.md) requires "at least one citation back to the corpus" in the quality gate. If the corpus is empty or generic, citations cannot be earned and the phase gate fails.
- [vision.md](../../vision.md) frames the demo as the proof of the architecture. The corpus is the substrate of that proof.

## Concrete steps (what to produce)

1. **Create `data/domains/mechanical/`** with 5–10 markdown files. Suggested mix that supports the locked CNC causal chain:
   - 2–3 **FMEA snippets** covering hydraulic-cylinder failure modes and bearing-wear failure modes.
   - 2–3 **maintenance log entries** that include the post-hydraulic-cylinder maintenance event on line 2 (with timestamps placing it on shift 3 of the incident date).
   - 2–3 **service notes** for hydraulic cylinders and bearings (vendor-manual-style passages, lubrication intervals, torque specs).
   - 1–2 **bearing-batch references** (a supplier-change memo, a QA receipt for the new-supplier batch). These plant the supply-chain clues Phase 4's spawning trigger will key on later; their presence inside the *mechanical* corpus is part of what will make the demo's spawn into `supply_chain` feel earned.

   Each file is a short, plausible operations document — not a research paper. Keep each under ~200 lines. Use a stable filename convention (e.g. `fmea-hydraulic-cylinder.md`, `maintenance-log-line-2.md`) so citations in the synthesizer report are readable.
2. **Create `data/incidents/cnc_out_of_tolerance.yaml`** matching the project's `Incident` pydantic model (`src/expertview/evidence/models.py`). Required content: incident `id`, `summary`, `observed_at` timestamp on shift 3, plus `symptoms` (out-of-tolerance dimensional readings on finished parts) and `affected_assets` (CNC on line 2). The YAML must round-trip through `Incident.model_validate(...)`.
3. **Add `tests/unit/test_incident_yaml.py`** that loads `data/incidents/cnc_out_of_tolerance.yaml`, validates it against `Incident`, and asserts a couple of identifying fields (incident `id`, the line/asset identifier). This is the boundary-validation contract — if a future schema change breaks the YAML, this test catches it.
4. **Verify locally**: `uv run pytest tests/unit/test_incident_yaml.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean (the YAML and `.md` files themselves don't need ruff, but the test does).

## What each step does

- **Step 1** plants the evidence the mechanical investigator will retrieve and the synthesizer will cite. The mix matters: FMEA + logs + service notes are what make a credible causal chain readable to a non-technical viewer.
- **Step 2** produces the demo scenario file. The YAML is the input to `python -m expertview.cli demo`.
- **Step 3** turns the YAML into a tested artifact — drift between the schema and the file is caught by CI, not by the demo failing mid-rehearsal.
- **Step 4** is the local quality gate.

## Code locations

- `data/domains/mechanical/*.md` (new — 5 to 10 files).
- `data/incidents/cnc_out_of_tolerance.yaml` (new).
- `tests/unit/test_incident_yaml.py` (new).

## Connections

**Upstream**:

- `evidence/models.py` `Incident` schema from Phase 1 Task 2.
- `data/domains/` and `data/incidents/` directories already exist (created by Phase 1 Task 1's bootstrap).

**Downstream**:

- [[task-2-mechanical-rag-loader]] reads every file in `data/domains/mechanical/`, embeds it, and caches the resulting vector index.
- [[task-5-runner-cli-wiring]] loads `data/incidents/cnc_out_of_tolerance.yaml`, builds the graph, and runs the end-to-end `/verify` against it.
- Phase 3 will mirror this structure for the four additional domains (`process`, `supply_chain`, `environmental`, `human_factors`).
- Phase 4's spawning trigger keys on findings derived from these documents (bearing batch / supplier hint).

## Parallelism rationale

- Sequential by necessity: Task 2 (loader) and Task 5 (wiring/verify) both consume files this task produces. Starting either earlier requires a fake corpus that would then have to be discarded.

## Risks / constraints / assumptions

- **Risk**: corpus too sparse to support a coherent causal chain. Mitigation: the file mix in step 1 is structured around the locked CNC scenario; the user-curation pass ensures the clues are actually present and traceable.
- **Risk**: corpus too dense or off-topic, making retrieval noisy. Mitigation: keep each file short, on-topic, and operationally plausible. Avoid fictional procedural noise that doesn't support a clue.
- **Risk**: the YAML drifts from the `Incident` schema between authoring and demo. Mitigation: the unit test in step 3.
- **Constraint**: per [CLAUDE.md hard rules](../../../CLAUDE.md), generated mock data >1MB must not be committed. The corpus here will be well under 1MB; if it grows, split it.
- **Assumption**: the user does the hand-curation pass after the agent drafts the corpus (per [decisions.md (2026-05-25 Q4)](../../decisions.md)). The agent should land the draft and call out in the PR description which files most need curator eyes.
- **Assumption**: PyYAML or equivalent is already pulled in transitively (via LangChain / LangGraph). If not, the executing agent must propose adding it via an entry in [decisions.md](../../decisions.md) per [CLAUDE.md hard rules](../../../CLAUDE.md) — *no silent dependency additions*.

## Definition of done

- 5 to 10 markdown files exist under `data/domains/mechanical/`, each is on-topic and under ~200 lines.
- `data/incidents/cnc_out_of_tolerance.yaml` exists and validates against `Incident`.
- `tests/unit/test_incident_yaml.py` passes.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `data/mechanical-corpus-and-incident` per [branching_strategy.md §5](../../branching_strategy.md), with the PR description flagging which corpus files most need user curation before downstream tasks build on them.
