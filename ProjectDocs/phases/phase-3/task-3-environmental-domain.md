# Task 3 — Environmental Domain Bundle

> **Branch suggestion**: `feature/environmental-domain`
> **Parallelism**: **Parallelizable with Tasks 1, 2, 4.** No shared editing surface with the other domain bundles.
> **Depends on**: Phase 2 complete (mechanical bundle merged, `v0.3.0-demo` tagged). Reuses `evidence/models`, `agents/base`, `agents/llms`, `rag/base`, and the patterns from [`rag/domains/mechanical.py`](../../../src/expertview/rag/domains/mechanical.py), [`prompts/investigator/mechanical.md`](../../../src/expertview/prompts/investigator/mechanical.md), and [`agents/investigators/mechanical.py`](../../../src/expertview/agents/investigators/mechanical.py).

## Purpose

Land the **environmental** domain: author a small corpus of shop-floor environmental records (HVAC logs, ambient temperature and humidity readings, vibration sensor data, compressed-air system status), wire a loader and a LangGraph investigator node against it, and ship the versioned prompt. After Phase 3 ships, this investigator runs concurrently with the other four against the shared `Incident` and contributes environmental `Finding`s to the synthesizer's convergence.

This domain plays a **calibration role** in the demo: the environmental corpus should mostly *exonerate* environmental causes (ambient conditions within normal range on shift 3) while planting one or two ambiguous signals that the LLM has to reason past. A multi-domain causal report is more credible when at least one investigator returns mostly "evidence does not support" findings — it shows the system is not just generating findings everywhere it looks.

This task does not modify `orchestration/runner.py` — the dispatcher rewrite and graph registration are Task 5's responsibility.

## Why it matters

- **Demo legibility**: a synthesizer report that pins blame across all five domains looks like the system is hallucinating findings. The environmental corpus is structured so this domain produces *fewer* and *lower-confidence* findings than mechanical / process / supply_chain. That asymmetry is what makes the final convergence look like reasoning rather than checklist-output.
- **Negative-evidence handling**: the citation requirement does not change — the environmental investigator must still cite documents, even for findings that conclude "evidence does not support an environmental cause." This is the first time the system has to deal with this case at the prompt level; the prompt framing matters.
- Phase 3's quality gate requires "5 investigator spans overlapping in time" on a LangSmith trace. This task ships investigator #4 of the four new ones.

## Concrete steps (what to produce)

1. **Create `data/domains/environmental/`** with 5–10 markdown files. Suggested mix that supports the locked CNC causal chain via *calibration* (mostly negative evidence):
   - 1–2 **HVAC daily logs** for the incident date and the surrounding week — readings within normal range, no alarms.
   - 1–2 **ambient temperature and humidity charts** from the shop floor over the incident shift, with one slightly out-of-band reading that is a *red herring* (e.g., a 2°C spike that does not exceed the process tolerance for the CNC operation).
   - 1–2 **vibration sensor reports** from line 2 (and a neighboring line for comparison) — line 2's vibration is elevated but explainable by an unrelated event (forklift traffic at the start of shift 3, the post-maintenance run-in vibration of the freshly serviced hydraulic cylinder).
   - 1 **compressed-air system status report** — pressure within spec, no leaks.
   - 1–2 **coolant / chiller logs** for the CNC machine — temperatures normal, no contamination flags.
   - 1 **environmental policy / specification document** stating the operating envelopes (ambient temp range, humidity range, vibration thresholds) — this is the document the investigator's "evidence does not support" findings will cite as the negative-evidence ground truth.

   Each file is a short, plausible facilities or sensor record. Keep each under ~200 lines. Use stable filename conventions (e.g., `hvac-log-shift-3.md`, `vibration-line-2-incident-day.md`, `coolant-chiller-cnc.md`, `environmental-spec-operating-envelopes.md`) so citations in the synthesizer report are readable.
2. **Create `src/expertview/rag/domains/environmental.py`** — loader mirroring `rag/domains/mechanical.py`:
   - Reads `data/domains/environmental/*.md`.
   - Embeds via the local `HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")` constructed in `agents/llms.py`.
   - Caches the vector index to disk under a **domain-specific cache key** (e.g., `.cache/rag/environmental/`).
   - Returns a `KnowledgeStore` instance per the `rag/base.py` protocol.
3. **Create `src/expertview/prompts/investigator/environmental.md`** — versioned prompt mirroring `prompts/investigator/mechanical.md` with one extra clause:
   - Role framing for an environmental RCA investigator (HVAC, ambient conditions, vibration, coolant, compressed air, facilities systems).
   - Citation requirement reproduced verbatim from the mechanical prompt — every `Finding.claim` cites at least one supplied document by `source` or `id`.
   - **Added clause for negative-evidence findings**: when the evidence does not support a causal role for the environmental domain, the investigator should still emit a low-confidence `Finding` whose `claim` states this and which cites the operating-envelope spec plus the relevant readings. Do not return an empty `findings` list when the corpus contains directly-relevant exonerating evidence.
   - Output contract: structured JSON parseable into `list[Finding]`, with `investigator_domain="environmental"`.
4. **Create `src/expertview/agents/investigators/environmental.py`** — node factory `make_environmental_investigator_node(store: KnowledgeStore, llm: ChatOpenAI) -> Callable[[ExpertViewState], Awaitable[dict]]:`. Mirror `agents/investigators/mechanical.py`; differences are the prompt path, the `investigator_domain` literal (`"environmental"`), and the function/factory names.
5. **Add a unit test** in `tests/unit/test_environmental_investigator.py` mirroring `tests/unit/test_mechanical_investigator.py`:
   - Builds the node with a fake `KnowledgeStore` and a fake LLM that returns hard-coded JSON.
   - Invokes the node against a stub `ExpertViewState` with the CNC `Incident`.
   - Asserts the returned patch is `{"findings": [...]}`, that each `Finding.investigator_domain == "environmental"`, and that each `Finding.citations` is non-empty.
   - Optionally: a second test case where the fake LLM returns a low-confidence "evidence does not support" finding, asserting the patch shape still holds and the citation is still present (verifies the negative-evidence path).
6. **Verify locally**: `uv run pytest tests/unit/test_environmental_investigator.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** plants environmental evidence weighted toward *exoneration*. The operating-envelope spec is the load-bearing file — it is what the negative-evidence findings will cite. The red-herring temperature spike and the explainable vibration signal force the synthesizer to handle ambiguous signals rather than only obvious ones.
- **Step 2** stands up the environmental retrieval store.
- **Step 3** locks the prompt as a versioned artifact and adds the negative-evidence clause that distinguishes this domain's prompt from the other three.
- **Step 4** exports the fourth investigator node factory.
- **Step 5** locks the contract: structured JSON in, validated `Finding` objects out, `investigator_domain="environmental"`, citations preserved on both positive and negative-evidence findings.
- **Step 6** is the local quality gate.

## Code locations

- `data/domains/environmental/*.md` (new — 5 to 10 files).
- `src/expertview/rag/domains/environmental.py` (new).
- `src/expertview/prompts/investigator/environmental.md` (new).
- `src/expertview/agents/investigators/environmental.py` (new).
- `tests/unit/test_environmental_investigator.py` (new).

## Connections

**Upstream**:

- `evidence/models.py` — `Incident`, `Finding` (Phase 1).
- `agents/base.py` — `Investigator` protocol (Phase 1).
- `agents/llms.py` — `create_investigator_llm()` (Phase 1).
- `rag/base.py` — `KnowledgeStore` protocol (Phase 1).
- `orchestration/state.py` — `ExpertViewState` (Phase 1).
- `rag/domains/mechanical.py`, `prompts/investigator/mechanical.md`, `agents/investigators/mechanical.py` — reference implementations (Phase 2).
- `data/incidents/cnc_out_of_tolerance.yaml` (Phase 2) — defines the scenario the corpus supports.

**Downstream**:

- [[task-5-dispatcher-wiring-verify]] imports `make_environmental_investigator_node`, constructs the store via this loader, and registers the resulting async function as a graph node.
- The synthesizer (Phase 2 Task 4) already reads `findings` from state; the environmental findings flow through without synthesizer changes. Phase 5's convergence logic will weight low-confidence findings differently from high-confidence ones — the environmental domain is the test case for that weighting.

## Parallelism rationale

- The bundle touches only `data/domains/environmental/`, `src/expertview/rag/domains/environmental.py`, `src/expertview/prompts/investigator/environmental.md`, `src/expertview/agents/investigators/environmental.py`, and `tests/unit/test_environmental_investigator.py`. None of these paths overlap with Tasks 1, 2, or 4.
- `orchestration/runner.py` is not edited here. Task 5 owns the dispatcher and graph registration.
- The loader's disk-cache key is domain-scoped.

## Risks / constraints / assumptions

- **Constraint**: prompts live as files under `src/expertview/prompts/`. Never inline ([CLAUDE.md hard rules](../../../CLAUDE.md)).
- **Constraint**: the only legal LLM construction site is `agents/llms.py`.
- **Constraint**: module boundaries are walls ([architecture.md §5](../../architecture.md)).
- **Risk**: the LLM treats the red-herring temperature spike or the elevated vibration as a primary cause and emits a high-confidence finding. Mitigation: the operating-envelope spec and the vibration explanation (forklift traffic, post-maintenance run-in) need to be retrievable for the same query that surfaces the anomalies. The user-curation pass should make sure the *explanation* of each red herring is in the corpus, not just the anomaly itself.
- **Risk**: negative-evidence findings get silently dropped because the JSON contract expects positive claims. Mitigation: the prompt's added clause explicitly permits and requires negative-evidence findings; the unit test covers this path; `Finding.confidence` low (e.g., < 0.3) but `claim` and `citations` populated.
- **Risk**: cache-key collision with sibling loaders. Mitigation: name the cache directory `.cache/rag/environmental/` explicitly.
- **Risk**: prompt drift from the mechanical prompt's citation discipline. Mitigation: copy the mechanical prompt verbatim, edit role framing + `investigator_domain` literal, then add the negative-evidence clause as a clearly-marked additional section so a future diff against `mechanical.md` is readable.
- **Assumption**: the user does a curation pass on the drafted corpus before Task 5's `/verify` rehearsal. The red herrings are the highest-leverage curator-attention items — they make the demo legible.
- **Assumption**: the synthesizer's existing prompt (Phase 2) already handles a mix of positive and negative-evidence findings without modification. If `/verify` shows the synthesizer ignoring negative-evidence inputs, that is a Phase 5 (convergence) concern, not a Phase 3 fix.

## Definition of done

- 5 to 10 markdown files exist under `data/domains/environmental/`, each on-topic, under ~200 lines, weighted toward exoneration with 1–2 explainable red herrings.
- The operating-envelope spec file exists and is retrievable for the negative-evidence findings to cite.
- `rag/domains/environmental.py` exposes a loader returning a `KnowledgeStore` and caches to a domain-scoped path.
- `prompts/investigator/environmental.md` exists with mechanical's citation discipline preserved verbatim, the role framing swapped, and the negative-evidence clause added.
- `agents/investigators/environmental.py` exports `make_environmental_investigator_node(store, llm)` returning an async `(ExpertViewState) -> dict` function.
- Unit test passes with fake store and fake LLM; asserts the `findings` patch shape, `investigator_domain="environmental"`, and non-empty citations. Negative-evidence test variant (if added) also passes.
- No `ChatOpenAI(...)` or `HuggingFaceEmbeddings(...)` constructed in `agents/investigators/environmental.py`.
- No prompt strings inlined in `.py` files.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/environmental-domain` per [branching_strategy.md §5](../../branching_strategy.md). PR description flags the red herrings as the highest-leverage curator-attention items.
