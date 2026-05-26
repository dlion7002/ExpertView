# Phase 1 — Skeleton + Contracts: Start-Here Guide

> **Scope of this guide**: what Phase 1 delivers, how to activate it on a fresh checkout, and how to verify its quality gate before moving on to [Phase 2](../build_plan.md#phase-2--vertical-slice-this-is-the-milestone-that-proves-the-architecture). It does not cover any Phase 2 work (real investigator runs, embedded corpora, end-to-end demo).

---

## 1. What Phase 1 does

Phase 1 lays the **structural foundation** for ExpertView — every cross-agent contract, every module boundary, and every provider entry point — without running any real investigation yet. It is the phase that locks shape, not behavior.

Concretely, Phase 1 produces:

- **Package layout** under [src/expertview/](../../src/expertview/) matching [architecture.md §2](../architecture.md): `agents/`, `rag/`, `evidence/`, `orchestration/`, `prompts/`.
- **Pydantic v2 schemas** in [evidence/models.py](../../src/expertview/evidence/models.py): `Finding`, `Hypothesis`, `CausalLink`, `CausalReport`, `Incident`, `Document`. These are the only legal cross-agent payloads.
- **LangGraph state schema** in [orchestration/state.py](../../src/expertview/orchestration/state.py): `ExpertViewState` TypedDict with `operator.add` reducers on the list fields so the Phase 3 fan-out merges instead of last-writer-wins.
- **LangGraph runner skeleton** in [orchestration/runner.py](../../src/expertview/orchestration/runner.py): `make_graph()` compiles a `StateGraph` with a single no-op placeholder node, plus opt-in LangSmith tracing configured from env. Phase 2 replaces the node body; the public import path does not change.
- **KnowledgeStore protocol** in [rag/base.py](../../src/expertview/rag/base.py) and an in-memory implementation in [rag/inmemory.py](../../src/expertview/rag/inmemory.py) wrapping LangChain's `InMemoryVectorStore`.
- **Agent protocols** in [agents/base.py](../../src/expertview/agents/base.py): `Investigator` and `Synthesizer` protocols — the structural contracts every Phase 2+ node implements.
- **Provider factory** in [agents/llms.py](../../src/expertview/agents/llms.py): the *only* legal construction site for `ChatOpenAI` (pointed at OpenRouter) and `HuggingFaceEmbeddings`. Honors `EXPERTVIEW_SYNTH_MODEL` (holds an OpenRouter model ID directly) to swap the synthesizer between a free build-phase ID (`deepseek/deepseek-v4-flash:free` default) and a paid frontier ID at demo time.
- **Tests**: schema round-trips, state shape, in-memory RAG, runner-skeleton smoke tests in [tests/unit/](../../tests/unit/); live provider-key round-trips in [tests/integration/test_provider_keys.py](../../tests/integration/test_provider_keys.py).

**What Phase 1 explicitly does NOT do** (these belong to Phase 2 and later):

- No real investigator implementation, no domain corpora, no embedded documents.
- No synthesizer LLM call wired into the graph.
- No CLI demo command.
- No dispatcher / fan-out / spawning / convergence logic.

---

## 2. Quick-start: activate Phase 1 on a fresh checkout

PowerShell on Windows is assumed (per [CLAUDE.md](../../CLAUDE.md)).

### 2.1 Install dependencies

```powershell
uv sync
```

`uv sync` reads [pyproject.toml](../../pyproject.toml) and creates `.venv/` with `langgraph`, `langchain-core`, `langchain-openai`, `langchain-huggingface`, `langchain-community`, `sentence-transformers`, `langsmith`, `pydantic`, `structlog`, `rich`, `pytest`, `pytest-asyncio`, `python-dotenv` (dev), and `ruff`.

### 2.2 Configure environment

```powershell
Copy-Item .env.example .env
```

Then fill in real values in `.env` (never commit it). Phase 1 only requires keys for the tests you intend to run; missing keys cause integration tests to skip cleanly, not fail.

| Env var | Required for | Phase 1 use |
|---|---|---|
| `OPENROUTER_API_KEY` | `test_openrouter_*` integration tests | Investigator (Owl Alpha) + synthesizer (DeepSeek V4 Flash) one-token round-trips |
| `LANGSMITH_API_KEY` | LangSmith tracing | Optional; tracing turns itself on iff this is set |
| `LANGSMITH_PROJECT` | LangSmith grouping | Optional; defaults handled by LangSmith |
| `EXPERTVIEW_SYNTH_MODEL` | Synthesizer selector (OpenRouter model ID) | `deepseek/deepseek-v4-flash:free` (default) during build; a paid frontier ID (e.g. `anthropic/claude-opus-4.7`) only for the demo path |

**Per [CLAUDE.md](../../CLAUDE.md), never edit `.env` from Claude Code.** The user owns `.env`; the assistant only edits `.env.example`.

---

## 3. Verify the Phase 1 quality gate

All four checks below must be green before Phase 2 starts. They map 1:1 to the gate defined in [build_plan.md — Phase 1](../build_plan.md#phase-1--skeleton--contracts).

### 3.1 Lint

```powershell
uv run ruff check .
```

Expected: no errors.

### 3.2 Format check

```powershell
uv run ruff format --check .
```

Expected: no diffs.

### 3.3 Tests

```powershell
uv run pytest
```

Expected:

- **All unit tests pass** — schemas round-trip, `ExpertViewState` reducers concatenate, in-memory `KnowledgeStore` upserts/queries, and `make_graph()` returns a `CompiledStateGraph` with and without LangSmith env vars.
- **Integration tests pass or skip** — the OpenRouter round-trips skip cleanly if `OPENROUTER_API_KEY` is absent; the local-embeddings round-trip always runs (no key required, ~130 MB one-time `BAAI/bge-small-en-v1.5` download). A skip is **not a failure** for Phase 1; it is the documented behavior for fresh clones without keys.

To prove keys + connectivity (recommended at least once before Phase 2):

```powershell
uv run pytest tests/integration/test_provider_keys.py -v
```

The synthesizer round-trip runs against whatever `EXPERTVIEW_SYNTH_MODEL` selects (default `deepseek/deepseek-v4-flash:free`, free). Setting it to a paid frontier ID (e.g. `anthropic/claude-opus-4.7`) at this stage is unnecessary and would burn the $5 OpenRouter credit — by design, paid IDs are for phase-7 rehearsal and demo time per the [free-tier-first decision](../decisions.md).

### 3.4 Graph compiles end-to-end

```powershell
uv run python -c "from expertview.orchestration.runner import make_graph; make_graph()"
```

Expected: no output, exit code 0. This is the smoke test that the placeholder topology compiles before Phase 2 swaps in real nodes.

---

## 4. Optional: confirm LangSmith tracing is wired

If `LANGSMITH_API_KEY` is set in `.env`, `make_graph()` flips `LANGSMITH_TRACING=true` so any subsequent LangGraph run is traced. Phase 1's placeholder graph emits a trivial span; the real value of tracing arrives in Phase 2 once an investigator actually does work. To eyeball it now:

```powershell
uv run python -c "import asyncio; from expertview.orchestration.runner import make_graph; from expertview.evidence.models import Incident; g = make_graph(); print(asyncio.run(g.ainvoke({'incident': Incident(id='smoke', summary='phase-1 smoke'), 'findings': [], 'hypotheses': [], 'spawned_subinvestigations': [], 'causal_report': None})))"
```

Then check the LangSmith dashboard for a one-node trace under the project named in `LANGSMITH_PROJECT`. Skip this step if you have not set up LangSmith yet.

---

## 5. Exit criteria — proceed to Phase 2 only when ALL of these hold

- [ ] `uv run ruff check .` — clean.
- [ ] `uv run ruff format --check .` — clean.
- [ ] `uv run pytest` — green (unit pass; integration pass or skip).
- [ ] `make_graph()` import-and-call smoke test — exit 0.
- [ ] `.env` contains at minimum a real `OPENROUTER_API_KEY` (Phase 2 needs it for the investigator LLM call; verify with `test_openrouter_*` actually running rather than skipping).
- [ ] [open_questions.md](../open_questions.md) has no Phase-1-blocking items still open.

When all six are checked, Phase 1 is locked. Start Phase 2 from the [Phase 2 section of build_plan.md](../build_plan.md#phase-2--vertical-slice-this-is-the-milestone-that-proves-the-architecture).

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'expertview'` | Editable install missing | `uv sync` again; ensure `pyproject.toml` lists the package |
| `RuntimeError: OPENROUTER_API_KEY is required ...` from a provider call | Env not loaded into the test process | `tests/conftest.py` loads `.env` via `python-dotenv` for the test process. Outside tests, export the var in your shell or run via `uv run` after copying `.env.example` → `.env`. |
| Integration tests *fail* instead of skipping when keys are absent | Keys are present-but-empty or whitespace-only | Either remove the line from `.env` or fill it with a real value; the skip guard requires the env var to be missing or strictly empty |
| `ruff format --check` reports diffs | Local edits not formatted | `uv run ruff format .` then re-run the check |
| LangSmith dashboard shows no traces | `LANGSMITH_API_KEY` not set, or graph never invoked | Set the key; run the optional smoke command in §4 |

---

## 7. Out of scope for Phase 1 (deliberate deferrals)

These belong to later phases and should **not** be added now even if tempting:

- A real CLI (`python -m expertview.cli demo`) — Phase 2.
- Domain corpora and embedding caches — Phase 2 (mechanical only) and Phase 3 (remaining four).
- A real synthesizer prompt and call — Phase 2.
- Dispatcher / `Send` API fan-out — Phase 3.
- Conditional-edge spawning — Phase 4.
- Streamlit UI — Phase 6.

Resist the urge to scaffold these now. Phase 1's value is precisely that it locks contracts before behavior. Every line of behavior added here is a line that has to be reworked when Phase 2 starts.
