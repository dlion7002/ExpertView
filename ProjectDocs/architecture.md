# ExpertView — Architecture

> **Status**: v0. Module boundaries and key interfaces are sketched here before implementation begins. Interfaces are expected to evolve once the vertical slice (build phase 2 in [build_plan.md](build_plan.md)) lands. Every change to this document should be reflected in [decisions.md](decisions.md) the same session.

## 1. Structural pattern

ExpertView implements the pattern called out in [project_introduction.md](project_introduction.md):

```
Parallel Hypotheses  +  Recursive Sub-Investigation  +  Evidence-Weighted Convergence
```

This is *not* a pipeline with an orchestrator label. The multi-agent shape is structural:

- **Different knowledge bases must live in different RAG stores.** A single context window cannot hold mechanical, process, supply, environmental, and human-factors corpora effectively. Each domain owns its own store.
- **Hypotheses must run in parallel.** Sequential investigation is structurally wrong — we do not know ex-ante which domain contains the root cause.
- **Sub-investigations spawn dynamically.** A mechanical investigator finding a part anomaly may need to spawn a supplier-history sub-investigator. The depth of the tree is unknown at the start.
- **Convergence is evidence-weighted, not aggregated.** The synthesizer reads partial findings from all investigators, recognizes causal links across domains, and produces a confidence-weighted causal explanation.

## 2. Module map

```
src/expertview/
  agents/              # Investigator + synthesizer abstractions and concrete impls
    base.py            #   Investigator + Synthesizer protocols
    llms.py            #   ChatAnthropic + ChatNVIDIA factory (the ONLY place LLM clients
                       #     are instantiated). Reads env vars; honors EXPERTVIEW_SYNTH_MODEL
                       #     to swap synthesizer between deepseek-r1 (build) and opus-4-7 (demo).
    investigators/     #   One file per domain: mechanical.py, process.py, supply.py,
                       #     environmental.py, human_factors.py.
                       #     Each exports an async LangGraph node function.
    synthesizer.py     #   Terminal LangGraph node — convergence + causal report assembly
    spawning.py        #   Pure predicates over Finding used by conditional-edge functions
                       #     in orchestration/runner.py to decide sub-investigation spawns
  rag/                 # Knowledge stores (domain-specific)
    base.py            #   KnowledgeStore protocol
    inmemory.py        #   KnowledgeStore wrapping LangChain InMemoryVectorStore (v1)
    domains/           #   Per-domain loaders that read data/domains/*/ and return a KnowledgeStore
  evidence/            # Cross-agent data shapes + convergence math
    models.py          #   Pydantic: Finding, Hypothesis, CausalLink, CausalReport, Incident, Document
    convergence.py     #   Pure functions: weight findings, link causes, score hypotheses
  orchestration/       # LangGraph topology + shared state
    state.py           #   ExpertViewState (TypedDict) — the LangGraph shared state schema
                       #     that replaces the earlier "EvidenceBus" abstraction
    runner.py          #   Builds the StateGraph, wires nodes + conditional edges,
                       #     runs graph.ainvoke(); fan-out via Send API; LangSmith tracing on
  prompts/             # Versioned prompt templates per role (provider-agnostic)
    investigator/      #   One template per domain investigator
    synthesizer/       #   Synthesizer templates (per scenario archetype if needed)
    schema.py          #   Helpers that inject Finding/Hypothesis schemas into prompts
  ui/                  # Demo surface (deferred — see open_questions.md item #1)
  cli.py               # Entry point: `python -m expertview.cli demo --incident <id>`
data/
  domains/             # Mock corpora, one folder per domain
    mechanical/
    process/
    supply_chain/
    environmental/
    human_factors/
  incidents/           # Sample incident scenarios as JSON or YAML
tests/
  unit/
  integration/
  fixtures/
```

**Why this layout.** Each top-level package under `src/expertview/` has a single responsibility and a clean public surface (the `base.py` protocols, the `state.py` shared-state schema, the `llms.py` provider factory). This is what makes Path B at the hackathon viable — `rag/`, `orchestration/` (graph + state schema lifted as a unit), `evidence/`, and `agents/base.py` + `agents/llms.py` can be lifted whole into a different application without dragging the rest of the codebase along.

## 3. Key interfaces (v0 sketches)

These are deliberately small. Implementation files will inevitably add helper types, but the *public* surface stays at this level of complexity.

```python
# src/expertview/rag/base.py
class KnowledgeStore(Protocol):
    domain: str
    def search(self, query: str, k: int = 5) -> list[Document]: ...

# src/expertview/agents/base.py
class Investigator(Protocol):
    domain: str
    async def investigate(
        self,
        incident: Incident,
        prior_findings: list[Finding],
    ) -> list[Finding]: ...

class Synthesizer(Protocol):
    async def converge(
        self,
        hypotheses: list[Hypothesis],
        findings: list[Finding],
    ) -> CausalReport: ...

# src/expertview/orchestration/state.py
class ExpertViewState(TypedDict):
    incident: Incident
    findings: Annotated[list[Finding], operator.add]   # reducer = list concatenation
    hypotheses: Annotated[list[Hypothesis], operator.add]
    spawned_subinvestigations: Annotated[list[str], operator.add]
    causal_report: CausalReport | None

# src/expertview/orchestration/runner.py
def make_graph() -> CompiledGraph:
    """Builds the LangGraph StateGraph:
       dispatcher  --Send-->  [mechanical, process, supply, environmental, human_factors]
                              │
                              ▼  (conditional edge over Finding via agents/spawning.py predicates)
                              ▼  sub_investigator  (may loop back to dispatcher if needed)
                              ▼
                              synthesizer  -->  END
    """
```

Concrete data shapes live in `evidence/models.py` as pydantic models. The shape sketch:

- **Incident**: `id`, `summary`, `observed_at`, `symptoms[]`, `affected_assets[]`.
- **Finding**: `investigator_domain`, `claim`, `confidence` ∈ [0, 1], `citations[]` (document IDs from the RAG corpus), `raised_at`.
- **Hypothesis**: `claim`, `supporting_findings[]`, `confidence`, `domain_origin`.
- **CausalLink**: `cause: Hypothesis`, `effect: Hypothesis | Symptom`, `strength`, `rationale`.
- **CausalReport**: `incident_id`, `top_hypotheses[]`, `causal_chain: list[CausalLink]`, `confidence_summary`, `generated_at`.

## 4. Data flow (ASCII)

```
       ┌──────────────┐
       │   Incident   │   (read from data/incidents/<id>.yaml)
       └──────┬───────┘
              │
              ▼
   ┌──────────────────────────────────────┐
   │     LangGraph StateGraph             │
   │     (ExpertViewState shared state)   │
   └──────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────┐
   │     dispatcher       │   emits 5 Send(...) calls,
   │       (node)         │   one per domain investigator
   └─────┬─────┬─────┬────┘
         │     │     │  ... 5 LangGraph branches in parallel via Send API
         ▼     ▼     ▼
   ┌──────┐┌──────┐┌──────┐
   │ Mech ││ Proc ││Supply│ ...  each: queries its KnowledgeStore (NV-Embed + NV-Rerank),
   └──┬───┘└──┬───┘└──┬───┘      calls Llama 3.3 70B via ChatNVIDIA,
      │       │       │           returns {"findings": [...]} → state-merged via reducer
      └───────┴───────┘
                              ┌────────────────────────────┐
                              │ conditional edge predicate │ ── reads merged state.findings
                              │   (agents/spawning.py)     │
                              └──────────┬─────────────────┘
                                         │ if spawn-needed:
                                         ▼
                                  ┌────────────────┐
                                  │ sub-investigator │  (another LangGraph node;
                                  │      (node)      │   merges its findings back)
                                  └────────┬─────────┘
                                           │ else: fall through
                                           ▼
                          ┌──────────────────────────┐
                          │       synthesizer        │
                          │         (node)           │
                          │  DeepSeek-R1 (build) or  │
                          │  Opus 4.7 (demo)         │
                          │  emits CausalReport      │
                          └──────────┬───────────────┘
                                     ▼
                          ┌──────────────────────┐
                          │     CausalReport     │ →  UI / CLI render
                          └──────────────────────┘

  ── All node spans captured by LangSmith for trace replay / debugging. ──
```

## 5. Architecture rules (enforced in code review)

- **Agents communicate only via the LangGraph shared state.** No direct calls between investigators. The synthesizer is the sole reader of the final state snapshot. The state schema lives in `orchestration/state.py` as `ExpertViewState`.
- **LangGraph nodes are pure async functions `(State) -> dict`** returning state patches. No side effects outside the returned patch and explicit LangSmith spans. This keeps the topology reasoning-about-able.
- **LLM provider clients are instantiated only in `agents/llms.py`.** `ChatAnthropic` and `ChatNVIDIA` are imported by node implementations from this single factory module — never instantiated inline. The factory honors `EXPERTVIEW_SYNTH_MODEL` to switch the synthesizer between DeepSeek-R1 (build/iteration) and Opus 4.7 (demo / final rehearsal).
- **RAG stores expose only the `KnowledgeStore` protocol.** Callers cannot reach into vector store internals; if a caller needs more, extend the protocol.
- **Investigator + synthesizer prompts live in `src/expertview/prompts/`.** They are versioned files, never inline f-strings buried in agent code. Prompts are provider-agnostic (no model-specific tokens baked in).
- **Synthesizer is side-effect-free.** The synthesizer node calls an LLM and returns `{"causal_report": CausalReport(...)}` as its state patch — nothing else. No bus writes, no disk writes, no spawning. "Pure" here means no side effects in the orchestration sense.
- **Cross-agent data goes through pydantic models in `evidence/models.py`.** Never raw dicts. This guards against silent schema drift between nodes that read/write the shared state.
- **Module boundaries are walls, not suggestions.** A file in `rag/` does not import from `agents/`. A file in `evidence/` does not import from `orchestration/`. `agents/` may import from `langchain_anthropic` and `langchain_nvidia_ai_endpoints`; `rag/` may import from `langchain_core` and `langchain_community` retrievers; `evidence/` and `prompts/` import neither (LLM-provider-pure). Test imports are the only exception.

## 6. Concurrency model

- Investigators run as LangGraph branches dispatched from a `dispatcher` node via the `Send` API. Under the hood this executes them as concurrent asyncio tasks — the parallelism story is preserved, the framework just owns the fan-out plumbing.
- LLM calls go through LangChain's async interface: `ChatNVIDIA.ainvoke(...)` for investigators (Llama 3.3 70B) and for the build-phase synthesizer (DeepSeek-R1); `ChatAnthropic.ainvoke(...)` for the demo-phase synthesizer (Opus 4.7). Both clients are constructed once in `agents/llms.py`.
- Cross-branch state merge happens through `Annotated[list[...], operator.add]` reducers on the relevant `ExpertViewState` fields — multiple branches publishing findings simultaneously is the merge case that drove the schema design.
- Dynamic sub-investigation: a conditional edge after the investigator fan-out evaluates predicates from `agents/spawning.py` over the merged `state["findings"]`. If a predicate fires, the edge routes to a `sub_investigator` node; otherwise it falls through to the `synthesizer` node. This is a single-process, single-machine demo — no Redis, no Kafka.

## 7. Tech stack

### Confirmed

- **Python 3.11+** managed by **uv** (lockfile + virtualenv).
- **Agent orchestration**: **LangGraph** — `StateGraph` with the `Send` API for parallel branch fan-out and conditional edges for dynamic sub-investigation spawning. The graph is wired in `orchestration/runner.py`; the shared state schema is `ExpertViewState` in `orchestration/state.py`.
- **Tracing / observability**: **LangSmith** — every node + LLM call captured as a span; trace replay is the demo-day fallback if a live run fails (replacing what would have been a hand-rolled JSONL recorder).
- **LangChain provider integrations**: `langchain-core`, `langchain-anthropic` (for `ChatAnthropic`), `langchain-nvidia-ai-endpoints` (for `ChatNVIDIA` + `NVIDIAEmbeddings` + `NVIDIARerank`), `langchain-community` (for retrievers / vector stores).
- **LLM models, by task**:
  - *Investigators (5 parallel)* → **Llama 3.3 70B Instruct** via NIM (`ChatNVIDIA(model="meta/llama-3.3-70b-instruct")`).
  - *Synthesizer, build / iteration* → **DeepSeek-R1** via NIM (`ChatNVIDIA(model="deepseek-ai/deepseek-r1")`). Free, strong thinking model.
  - *Synthesizer, final rehearsal + demo* → **Anthropic Opus 4.7** (`ChatAnthropic(model="claude-opus-4-7")`). The quality lever, bought only when judges watch.
  - Synthesizer choice is selected by `EXPERTVIEW_SYNTH_MODEL` env var, read by the factory in `agents/llms.py`.
- **Embeddings**: **`nv-embed-v2`** via `NVIDIAEmbeddings`. Top-MTEB quality at zero marginal cost.
- **Reranker**: **`nv-rerankqa-mistral-4b-v3`** (or current equivalent NIM reranker) via `NVIDIARerank`.
- **Vector store**: LangChain `InMemoryVectorStore` wrapped behind the `KnowledgeStore` protocol (v1) — locked 2026-05-25 in [decisions.md](decisions.md). FAISS via `langchain-community` is the pre-identified upgrade path if embedding-on-startup costs grow under NIM quota.
- **Schemas**: pydantic v2.
- **Logging**: structlog (structured, JSON-friendly) for application logs; LangSmith for LLM-call traces.
- **CLI / console output**: `rich` for readable demos.
- **Testing**: pytest, `pytest-asyncio` for async tests, optional `hypothesis` for schema property tests.
- **Lint / format**: ruff (single tool, fast).
- **Demo UI**: **Streamlit** — locked 2026-05-25 in [decisions.md](decisions.md). Single-screen app with incident input, live investigator-status panel + Mermaid topology diagram (`compiled_graph.get_graph().draw_mermaid()` rendered via `st.mermaid`), and final causal-report region with confidence bars + citations. A `--cli` mode with `rich` live tables is kept wired as Plan B for venue-laptop failures.

### Soft spot worth noting

- `langchain_anthropic`'s support for Anthropic prompt caching has historically lagged the raw SDK. If demo-time synthesizer caching matters, the demo-path synthesizer node may drop to the raw Anthropic SDK; the built-in `claude-api` skill governs that code path. The build-path (DeepSeek-R1 via `ChatNVIDIA`) is unaffected — NVIDIA NIM has no equivalent caching feature.

### Explicitly excluded

- **CrewAI, AutoGen** — opinionated agent-role abstractions that don't match the investigator + synthesizer + dynamic-spawn shape; LangGraph fits the shape and gives stronger industry signal.
- **Docker** for the demo path — single-laptop demo doesn't need it.
- **A real vector database** (Pinecone, Weaviate, Qdrant managed) — overkill for hackathon scale (<1k documents per domain). LangChain `InMemoryVectorStore` or `FAISS` covers v1.
- **Local-only model fallback path** (Ollama, llama.cpp) — per the cloud-only demo posture decision in [decisions.md](decisions.md) dated 2026-05-25. Hotspot + LangSmith trace replay is the mitigation, not a parallel offline code path.

## 8. Open architectural questions

All phase-0 architectural questions are resolved or formally deferred as of 2026-05-25 — see the resolution entries in [decisions.md](decisions.md). Demo UI (Streamlit), demo incident scenario (CNC out-of-tolerance), vector store (LangChain `InMemoryVectorStore`), and mock-corpus strategy (hybrid Claude draft + hand curation) are locked. Anthropic spend cap + NIM quota tracking are deferred until a functional end-to-end demo exists. New architectural questions arising during phase 1+ are tracked in [open_questions.md](open_questions.md).

## 9. What changes when

- **Stable**: module boundaries, the pattern (parallel + recursive + convergence), the `KnowledgeStore` / `Investigator` / `Synthesizer` protocols, the architecture rules in section 5, the choice of LangGraph + LangSmith as the orchestration substrate.
- **Expected to evolve**: the `ExpertViewState` TypedDict fields (we will add fields as nodes need them), pydantic model details in `evidence/models.py`, prompt templates (every demo rehearsal will adjust them), the spawning conditional-edge predicates, and the model identifiers selected by `agents/llms.py` (NIM catalog model names can change as NVIDIA rotates hosted models).
