# ExpertView — Build Plan

> **Build mode**: pre-hackathon, self-paced. ExpertView is constructed over multiple sessions *before* the event and brought to the hackathon already polished. Each phase below ends in a working, demoable state with its own quality gate. Do not advance to the next phase until the current phase's gate is green.

## Pre-hackathon build phases

### Phase 0 — Foundations (this session, in progress)

- **Outputs**: this `ProjectDocs/` set + rewritten `CLAUDE.md`.
- **Quality gate**: user has reviewed [vision.md](vision.md) and [architecture.md](architecture.md) and confirmed they match intent. Open questions in [open_questions.md](open_questions.md) are answered or explicitly deferred with a documented reason. **Cleared 2026-05-25** — Q1 (Streamlit), Q2 (CNC out-of-tolerance scenario), Q3 (LangChain `InMemoryVectorStore`), and Q4 (hybrid mock corpora) are locked. **Updated 2026-05-26** — the multi-provider NIM + Anthropic plan was superseded by OpenRouter + local embeddings after the NIM free-tier endpoints failed against the user's key; see [decisions.md](decisions.md). The Q5 budget question is now answered by the $5 OpenRouter credit tracked in the OR dashboard. See [decisions.md](decisions.md) for resolutions.
- **Blocks**: none remaining. Phase 1 (Skeleton + contracts) is unblocked.

### Phase 1 — Skeleton + contracts

- **Goal**: project layout, pydantic schemas, `KnowledgeStore` stub wrapping LangChain `InMemoryVectorStore`, LangGraph `StateGraph` skeleton with `ExpertViewState` TypedDict, provider-key round-trip tests. No real investigator runs yet.
- **Outputs**:
  - `pyproject.toml` (uv-managed) with `langgraph`, `langchain-core`, `langchain-openai`, `langchain-huggingface`, `langchain-community`, `sentence-transformers`, `langsmith`, `pydantic`, `structlog`, `rich`, `pytest`, `pytest-asyncio`, `python-dotenv` (dev), `ruff`. `.gitignore`, `.python-version`.
  - `.env.example` listing `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `EXPERTVIEW_SYNTH_MODEL`.
  - `src/expertview/` package skeleton matching [architecture.md §2](architecture.md).
  - `evidence/models.py` with Finding, Hypothesis, CausalLink, CausalReport, Incident, Document.
  - `rag/base.py` and `rag/inmemory.py` (KnowledgeStore wrapping `InMemoryVectorStore`).
  - `orchestration/state.py` with `ExpertViewState` TypedDict + reducer annotations.
  - `orchestration/runner.py` with `make_graph()` returning a `CompiledGraph` (single placeholder node end-to-end).
  - `agents/base.py` with Investigator + Synthesizer protocols.
  - `agents/llms.py` with `ChatOpenAI` (pointed at OpenRouter) + `HuggingFaceEmbeddings` factory; honors `EXPERTVIEW_SYNTH_MODEL` (holds an OpenRouter model ID directly).
  - `tests/unit/test_schemas.py` — round-trip JSON serialization for every pydantic model.
  - `tests/integration/test_provider_keys.py` — local-embeddings round-trip against `BAAI/bge-small-en-v1.5` (no skip), plus OpenRouter round-trips against the investigator model (Owl Alpha, one-token completion) and the synthesizer model (whatever `EXPERTVIEW_SYNTH_MODEL` selects, one-token completion). Verifies key + connectivity.
- **Quality gate**: `uv run pytest` green on schema round-trips and provider round-trips. `uv run ruff check .` and `uv run ruff format --check .` clean. `python -c "from expertview.orchestration.runner import make_graph; make_graph()"` compiles a `StateGraph` without error.
- **Risk**: bikeshedding schema fields. Mitigation: fields can be added later; lock only the *minimum* set named in [architecture.md §3](architecture.md).

### Phase 2 — Vertical slice (this is the milestone that proves the architecture)

- **Goal**: ONE investigator (LangGraph node) + ONE domain corpus (5–10 mock docs, embedded via NV-Embed-v2, cached to disk) + a synthesizer node producing a single hypothesis from a single finding. End-to-end CLI call drives the compiled graph from `Incident` → `CausalReport`. LangSmith trace visible in the dashboard.
- **Outputs**:
  - `data/domains/mechanical/*.md` — 5–10 hybrid-authored mock docs (Claude drafts, hand-curated) covering FMEA snippets, maintenance log entries, hydraulic-cylinder service notes, and bearing-batch references that plant the demo's causal-chain clues.
  - `data/incidents/cnc_out_of_tolerance.yaml` — the rehearsed CNC out-of-tolerance incident (shift 3, line 2, post-hydraulic-cylinder maintenance, new-supplier bearing batch). Locked 2026-05-25 — see [decisions.md](decisions.md).
  - `rag/domains/mechanical.py` — loader: reads `data/domains/mechanical/*.md`, embeds via the local `HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")` constructed in `agents/llms.py`, caches the vector index to a local file so we re-embed only on corpus change.
  - `agents/investigators/mechanical.py` — async LangGraph node: queries the `KnowledgeStore`, calls the investigator LLM (`openrouter/owl-alpha` via `ChatOpenAI` pointed at OpenRouter), returns `{"findings": [...]}`.
  - `agents/synthesizer.py` — terminal LangGraph node: calls the LLM selected by `agents/llms.py` (`EXPERTVIEW_SYNTH_MODEL=deepseek/deepseek-v4-flash:free` during build), returns `{"causal_report": ...}`.
  - `prompts/investigator/mechanical.md` and `prompts/synthesizer/default.md`.
  - `orchestration/runner.py` — wires `dispatcher → mechanical → synthesizer` as a minimum graph; LangSmith tracing enabled via env.
  - `cli.py` — `python -m expertview.cli demo --incident <id>` prints a CausalReport + the LangSmith trace URL.
- **Quality gate**: the CLI command runs against the rehearsed incident, prints a coherent causal report with at least one citation back to the corpus, and a LangSmith trace appears in the project dashboard showing every node + LLM call. `/verify` confirms by actually running it.
- **Risk**: the prompt produces low-quality findings on DeepSeek V4 Flash's reasoning style. Mitigation: iterate on the prompt template against the build-phase synthesizer; demand citations; demand structured `Finding` output via pydantic-validated JSON; rehearse the same prompt against the paid frontier synthesizer at the end of phase 5 to catch transfer drift.

### Phase 3 — Parallel fan-out

- **Goal**: all 5 domain investigators run *concurrently* against 5 mock corpora, dispatched from a `dispatcher` LangGraph node via the `Send` API. Findings merge into shared state via the reducer on `ExpertViewState.findings`.
- **Outputs**:
  - All 5 corpora populated in `data/domains/`.
  - `rag/domains/{process,supply_chain,environmental,human_factors}.py` loaders (each embeds + caches independently).
  - `agents/investigators/{process,supply_chain,environmental,human_factors}.py` — async LangGraph node functions.
  - `orchestration/runner.py` — dispatcher node emits 5 `Send(...)` calls; investigator branches run concurrently; LangSmith captures the parallel spans.
  - structlog application-side logs showing per-investigator start/finish timestamps (complement, not replacement, of LangSmith traces).
- **Quality gate**: timing of `python -m expertview.cli demo` proves true parallelism — total wall time ≈ slowest investigator, not the sum of all five. LangSmith trace shows the 5 investigator spans overlapping in time. structlog log shows interleaved start times.
- **Risk**: OpenRouter free-tier rate limits during parallel dispatch (the free models route through whichever upstream provider OR has paired them with; per-provider rate limits apply). Mitigation: throttle via an `asyncio.Semaphore` inside the dispatcher (cap of 5 is fine; lower if OpenRouter 429s); on-429 retry with backoff inside `agents/llms.py`. Owl Alpha and the Nemotron fallback both have multi-provider routing so transient throttling on one provider rarely hits all five branches at once.

### Phase 4 — Dynamic sub-investigation

- **Goal**: at least one spawning trigger fires reliably on the rehearsed scenario (e.g., mechanical investigator finds a bearing anomaly → conditional edge routes to a supplier-history sub-investigator node under `supply_chain`).
- **Outputs**:
  - `agents/spawning.py` — pure predicates over `Finding` (one function per trigger, no side effects).
  - `orchestration/runner.py` extended with a `_should_spawn(state) -> str` conditional-edge function that calls the predicates and returns the next node name (a sub-investigator node, or `"synthesizer"` to fall through).
  - A sub-investigator node implementation (can live as a parameterized node in `agents/investigators/sub_investigator.py`).
  - LangSmith trace shows the spawned span as a child of the dispatcher, and the sub-investigator's `Finding` reaches the synthesizer via state merge.
- **Quality gate**: a single demo run produces a LangSmith trace containing both the 5 parallel investigator spans and the dynamically spawned sub-investigator span, with the sub-investigator's finding cited in the final CausalReport.
- **Risk**: spawning predicates become a tangle. Mitigation: one predicate per function, all predicates are pure functions over `Finding`; the conditional-edge function is a thin dispatcher over them.

> **Cut-line: phases 1–4 must ship before the event.** Phases 5–7 are progressively optional but each adds material demo value.

### Phase 5 — Evidence-weighted convergence

- **Goal**: the synthesizer applies confidence scoring + causal linking across findings; two distinct incidents produce two distinct causal reports with different top causes.
- **Outputs**:
  - `evidence/convergence.py` — pure functions: weight findings by source confidence, link causes across domains, score hypotheses.
  - A second rehearsed incident in `data/incidents/` that exercises a different domain.
  - `tests/integration/test_convergence.py` — two incidents in, two distinct reports out.
- **Quality gate**: both incidents produce reports where the top hypothesis differs and the confidence summary is non-trivial.
- **Risk**: the synthesizer over-fits to one scenario. Mitigation: the second incident is the safety check.

### Phase 6 — Demo surface

- **Goal**: a UI showing parallel execution live + the final causal report + the LangGraph topology diagram. A non-technical viewer can follow it.
- **Outputs**:
  - **Streamlit** single-screen app (locked 2026-05-25 — see [decisions.md](decisions.md)) under `src/expertview/ui/`. Three regions: incident input, live investigator-status panel + Mermaid topology diagram, final causal-report rendering. A `--cli` mode with `rich` live tables is kept wired as Plan B.
  - **Mermaid topology diagram rendered in the UI**: `compiled_graph.get_graph().draw_mermaid()` produces a Mermaid string showing nodes + edges; render via `st.mermaid` as a tab or sidebar. This is the demo-legibility recovery for the framework choice — judges see the LangGraph shape graphically rather than hidden in code.
  - Live investigator-status panel reading from LangGraph state (or LangSmith stream) via `st.empty()` + `st.fragment` for cheap incremental updates.
  - Final causal-report rendering with confidence bars + citations linking back to source documents.
- **Quality gate**: a third party can watch the demo and describe what is happening without prompting; the Mermaid topology diagram is visible and labels match the actual code.
- **Risk**: UI scope creep. Mitigation: hard-cap UI to one screen with three regions — incident input, live investigator status + topology diagram, final report.

### Phase 7 — Polish + rehearsal

- **Goal**: one fully scripted scenario, retries on transient OpenRouter failures, deterministic mock data for reproducible demos, the synthesizer swap to the paid frontier model exercised on the demo laptop, a LangSmith trace replay path as the final fallback.
- **Outputs**:
  - Retry/backoff wrapper inside `agents/llms.py` covering the OpenRouter `ChatOpenAI` client (429s, transient 5xxs).
  - Deterministic seed for any sampling; embedding cache invalidation rule documented.
  - **Synthesizer swap rehearsal**: a full demo run with `EXPERTVIEW_SYNTH_MODEL=anthropic/claude-opus-4.7` (or whichever paid frontier is on OR at demo time) on the demo laptop, verifying the same prompts produce a coherent CausalReport. This is where prompt-transfer drift between the free build synthesizer and the paid demo synthesizer is caught.
  - **LangSmith trace export**: a saved trace from a successful rehearsal run, with a documented `replay` command path so the demo can be reconstructed from the trace if all networks are down at the venue.
  - `README.md` with a 1-minute run-it-yourself guide (lists the two env vars: `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`).
- **Quality gate**: three consecutive clean runs of the demo scenario on the actual demo laptop — at least one of them with `EXPERTVIEW_SYNTH_MODEL` set to a paid frontier ID to confirm the demo-path. A successful LangSmith trace is exported.

---

## At-hackathon usage plan (1-day event itself)

> The system is already built. The event is for *adaptation*, not construction.

### Hour 1 — Read the brief, decide path

- Read the official hackathon brief carefully.
- Decide:
  - **Path A — Brief aligns with RCA** (e.g., "build an investigation system for X domain"). Proceed with most of ExpertView intact.
  - **Path B — Brief diverges materially** (e.g., "build a customer support triage system"). Lift the modular pieces into a new project.

### Path A — Adapt in place

- Swap the demo scenario in `data/incidents/` to match the brief's specifics.
- Replace or extend mock corpora in `data/domains/` if the brief implies different domains.
- Tune investigator prompts in `src/expertview/prompts/investigator/` — usually a 1-line change per file to match the brief's vocabulary.
- Rehearse the demo at least twice.

### Path B — Lift modules into a new project

The boundaries preserved during phase 1 are designed exactly for this. The lift-able units (in priority order):

1. `src/expertview/orchestration/` — the LangGraph `StateGraph` builder + `ExpertViewState` schema. Lift as a unit; rename `ExpertViewState` to fit the new domain and swap node implementations. Reusable for any parallel-agent + dynamic-spawn + convergence problem.
2. `src/expertview/agents/llms.py` — the `ChatOpenAI` (OpenRouter-routed) + `HuggingFaceEmbeddings` factory + env-driven model swap. Reusable verbatim — OpenRouter routes any frontier or open-weight LLM through one client.
3. `src/expertview/rag/` — the `KnowledgeStore` protocol + LangChain-backed implementation. Reusable for any domain.
4. `src/expertview/evidence/models.py` — the Finding/Hypothesis/CausalLink schemas. Reusable for any system that synthesizes evidence into a weighted conclusion.
5. `src/expertview/agents/base.py` — the Investigator/Synthesizer protocols. Generic enough that "Investigator" can be relabeled "Triage Agent" or "Diagnostic Agent" with no structural change.

The lift mechanic: create a new package, copy units 1–5 above, write new domain node functions on top of the protocols, swap the synthesizer prompt to fit the new use case, adjust the conditional-edge predicates for the new spawning logic. The LangGraph + state schema is now the unit of reuse; this is arguably stronger industry signal than lifting hand-rolled async modules.

### Hour 7–8 — Demo prep

- Rehearse the demo twice on the venue network.
- Prepare 1–2 fallback scenarios in case the primary scenario fails on the demo laptop.
- Have the architecture diagram from [architecture.md §4](architecture.md) ready as a screenshot for judge Q&A.
- Confirm the recorded JSONL backup trace plays correctly.

---

## Risk register

### Pre-hackathon (during the build)

| Risk | Mitigation |
|---|---|
| Scope creep across phases | Phase gates are mandatory; do not start phase N+1 until phase N's gate is green. |
| OpenRouter free-tier daily quota exhausted by iteration | LangSmith trace replay during prompt iteration; track OR usage in the OpenRouter dashboard. Only phase-7 rehearsals hit fresh paid-tier API calls. |
| Investigator prompts hallucinate findings | Prompts demand citations from the RAG corpus; integration tests assert citation presence. |
| Schema churn breaks tests | Keep `evidence/models.py` minimal; add fields only when a node actually needs them. |
| Paid-tier OpenRouter spend during prompt iteration | Iteration runs `EXPERTVIEW_SYNTH_MODEL=deepseek/deepseek-v4-flash:free`; paid frontier IDs only at phase-7 rehearsal and demo time. |
| Prompt-transfer drift between the free build synthesizer and the paid demo synthesizer | Phase-7 explicitly rehearses with the paid-frontier swap on the demo laptop. |
| LangChain prompt-cache lag on Anthropic | Demo-path synthesizer may drop to raw Anthropic SDK if cache matters; the `claude-api` skill governs that path. Soft spot, not a blocker. |

### At hackathon (event day)

| Risk | Mitigation |
|---|---|
| Brief diverges severely from RCA | Path B is the safety net; the LangGraph + state schema lifts as a unit, with `agents/llms.py` and `rag/` reusable verbatim. |
| Venue network outage | Personal cellular hotspot is the primary mitigation. LangSmith trace replay (a saved trace from phase 7) is the secondary mitigation if cellular also fails. |
| OpenRouter rate-limit during live demo | Investigator dispatcher already throttles via `Semaphore`; on-429 retry inside `agents/llms.py`. |
| Paid-tier spend overrun at the event | The synthesizer is the only paid-tier call. Mid-event iteration can run on the free build synthesizer to preserve the $5 credit; switch to the paid frontier synth ID only when demoing. |
| Judge asks an off-script question | LangGraph Mermaid topology diagram + the [architecture.md](architecture.md) diagram are the answer to most "how does it work" questions; have both open in tabs. |
| Last-minute prompt change breaks a working investigator | Versioned prompt files + `git diff` shows the regression; revert + rehearse. |

---

## Demo script outline

(Drafted in phase 6, rehearsed in phase 7.)

1. **Open** with the incident: a one-paragraph operational scenario the audience can picture.
2. **Show the fan-out**: 5 domain investigators light up in parallel in the UI; timestamps visible; LangGraph Mermaid diagram shows the topology.
3. **Show the spawn**: one investigator's finding fires a conditional edge and the sub-investigator node appears in the live trace.
4. **Show the convergence**: the synthesizer (a paid frontier model via OpenRouter, e.g. Opus 4.7) produces the CausalReport with weighted hypotheses and citations.
5. **Close** with the LangGraph + architecture diagrams, the OpenRouter-routed model story (free Owl Alpha for the 5-way parallel investigators, free DeepSeek V4 Flash for build-phase synthesis, paid frontier model swapped in at demo time via a single env var, local `BAAI/bge-small-en-v1.5` for retrieval, LangSmith for traceability), and the reusability claim (Path B lift-ability).
