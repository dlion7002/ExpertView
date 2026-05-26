# Task 2 — Mechanical RAG Loader

> **Branch suggestion**: `feature/mechanical-rag-loader`
> **Parallelism**: **Parallelizable with Tasks 3 and 4.**
> **Depends on**: Task 1 (corpus files exist under `data/domains/mechanical/`).

## Purpose

Ship the first domain loader: a function that reads `data/domains/mechanical/*.md`, embeds each document with the local `HuggingFaceEmbeddings` factory from `agents/llms.py`, populates an `InMemoryKnowledgeStore`, and caches the resulting vector index so we only re-embed on corpus change. This is the pattern Phase 3 will replicate four more times for the other domains, so the structure here sets the template.

## Why it matters

- [architecture.md §5](../../architecture.md) makes `KnowledgeStore` the sole legal entry into the RAG layer. This task delivers the first concrete instance of that contract being honored end-to-end against a real corpus.
- [build_plan.md §Phase 2](../../build_plan.md) calls for the embedding cache so iteration doesn't pay the embedding cost on every demo run. Caching is a phase-2 deliverable, not an optimization.
- The local-embeddings choice ([decisions.md 2026-05-26](../../decisions.md)) means we have a zero-cost retrieval path; the loader is what makes that benefit real.

## Concrete steps (what to produce)

1. **Create `src/expertview/rag/domains/__init__.py`** (empty package marker) and **`src/expertview/rag/domains/mechanical.py`**. Public surface: a factory function (suggested name `load_mechanical_store()`) that returns an `InMemoryKnowledgeStore` populated with the mechanical corpus.
2. **Implement the loader** to:
   - Read every `*.md` under `data/domains/mechanical/`.
   - Wrap each file's contents in the project's pydantic `Document` (from `evidence/models.py`) with `domain="mechanical"`, `source` set to the relative file path, and a stable `id` (e.g. the filename stem). Populate `metadata` with anything cheap to compute (file mtime, line count) if useful for citations.
   - Construct the embeddings via `agents/llms.create_embeddings()` — never instantiate `HuggingFaceEmbeddings` inside `rag/` ([CLAUDE.md architecture rules](../../../CLAUDE.md)).
   - Instantiate `InMemoryKnowledgeStore(domain="mechanical", embeddings=...)` from Phase 1 Task 3 and ingest the documents.
3. **Add an embedding cache** to disk so re-runs don't pay the embedding cost when the corpus is unchanged:
   - Cache key derived from the set of `(file_path, file_hash)` pairs across `data/domains/mechanical/`. A single hash over the sorted manifest is enough.
   - Cache location under a `.cache/` directory at the repo root; add `.cache/` to `.gitignore` if not already excluded.
   - On load: if the cache hash matches the current corpus manifest, deserialize the cached vectors into a fresh `InMemoryKnowledgeStore` and skip re-embedding. Otherwise embed fresh and rewrite the cache.
4. **Add an integration test** in `tests/integration/test_mechanical_rag.py` that:
   - Calls `load_mechanical_store()`.
   - Issues a search query keyed to the corpus (e.g. "bearing batch") and asserts at least one returned `Document` has the expected `domain` and a non-empty `content`.
   - Marks the test with `@pytest.mark.slow` or similar if embedding load time would otherwise dominate the unit suite. The test does need to run in CI — it's the only thing that exercises the real embedding model in the RAG layer.
5. **Verify locally**: `uv run pytest tests/integration/test_mechanical_rag.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** establishes the `rag/domains/` sub-package the four other domains will join in Phase 3. The factory-function shape (rather than a class) keeps the loader trivially callable from `make_graph()` at wire time.
- **Step 2** is the contract: corpus files → pydantic `Document`s → `InMemoryKnowledgeStore`. Note the layering: `rag/` does not construct embeddings; `agents/llms.py` does. This task imports the factory and uses it.
- **Step 3** is the iteration-cost mitigation. Without it, every demo rehearsal pays the embedding cost again.
- **Step 4** proves end-to-end retrieval works against real embeddings against the real corpus — the first time the local `BAAI/bge-small-en-v1.5` path actually services a query in this project.
- **Step 5** is the local quality gate.

## Code locations

- `src/expertview/rag/domains/__init__.py` (new).
- `src/expertview/rag/domains/mechanical.py` (new).
- `.cache/` (new, gitignored — created at first run, not committed).
- `tests/integration/test_mechanical_rag.py` (new).
- `.gitignore` (edit to include `.cache/` if not already covered).

## Connections

**Upstream**:

- Task 1's mechanical corpus files.
- Phase 1 Task 3's `InMemoryKnowledgeStore` and `KnowledgeStore` protocol.
- Phase 1 Task 4's `create_embeddings()` factory in `agents/llms.py`.
- Phase 1 Task 2's `Document` pydantic model.

**Downstream**:

- [[task-3-mechanical-investigator]] will query a `KnowledgeStore` — that store is built here. The investigator does *not* import `load_mechanical_store()`; the wiring task does.
- [[task-5-runner-cli-wiring]] calls `load_mechanical_store()` once at graph-build time and binds the resulting store into the mechanical investigator node.
- Phase 3's `rag/domains/{process,supply_chain,environmental,human_factors}.py` loaders will copy this pattern.

## Parallelism rationale

- Tasks 2, 3, and 4 import only from Phase 1 contracts (`evidence/`, `rag/base`, `agents/base`, `agents/llms`) and stdlib / third-party libraries. They do not import from each other.
- The architecture rule "module boundaries are walls" ([architecture.md §5](../../architecture.md)) keeps the three branches conflict-free. Merge order among Tasks 2/3/4 does not matter.

## Risks / constraints / assumptions

- **Constraint**: `rag/` may import `langchain_core` and `langchain_community` but **must not** import from `agents/` other than the `llms` factory — and the embeddings object is *passed in* by the wiring layer, not constructed here. Architecture rule from [architecture.md §5](../../architecture.md).
- **Constraint**: the loader returns the project's pydantic `Document`, never LangChain's native `Document`. Translation belongs inside `rag/inmemory.py` (already implemented in Phase 1 Task 3) or here at the load boundary — never leaking past the `KnowledgeStore.search()` return type.
- **Risk**: the embedding cache becomes stale silently (corpus edited, hash collision, cache file corrupted). Mitigation: the manifest hash covers `(path, hash)` pairs; if the cache deserialization fails, embed fresh and overwrite without raising.
- **Risk**: `BAAI/bge-small-en-v1.5` model weights are downloaded on first run, adding minutes to the first test. Mitigation: document the first-run cost in the integration test docstring; subsequent runs use the local `sentence-transformers` cache.
- **Assumption**: `InMemoryVectorStore` exposes a way to round-trip its vectors (or the loader can serialize the `(Document, embedding)` pairs and reconstruct the store). If not, the cache falls back to serializing the manifest + raw embeddings and rebuilding `InMemoryVectorStore` from them — *do not* extend the `KnowledgeStore` protocol to expose cache internals.

## Definition of done

- `rag/domains/mechanical.py` exports a `load_mechanical_store()` (or equivalently named) factory returning an `InMemoryKnowledgeStore` populated with the mechanical corpus.
- Cache present: first run embeds, second run reads from cache; cache invalidates on corpus change.
- Integration test in `tests/integration/test_mechanical_rag.py` passes against the real embedding model and the real corpus.
- `rag/domains/mechanical.py` does not import from `agents/` except `agents/llms` for the embeddings factory; does not import from `orchestration/`.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- `.cache/` is gitignored; no embedding artifacts committed.
- PR opened on `feature/mechanical-rag-loader` per [branching_strategy.md §5](../../branching_strategy.md).
