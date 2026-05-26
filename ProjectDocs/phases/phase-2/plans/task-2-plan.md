# Task 2 — Mechanical RAG Loader — Implementation Plan

> **Scope source**: [../task-2-mechanical-rag-loader.md](../task-2-mechanical-rag-loader.md)
> **Branch**: `feature/mechanical-rag-loader`
> **Author**: Claude (Opus 4.7) executing session of 2026-05-26
> **Status**: Awaiting user approval

## Locked decisions for this task (from clarifying Q&A, 2026-05-26)

- **Cache serialization**: pickle of `(Document, embedding)` pairs under `.cache/rag/mechanical/`. One `.pkl` file per domain. Pickle is acceptable because (a) cache is a local dev artifact, never shipped; (b) Python version is pinned via `requires-python = ">=3.11"`; (c) `Document` is a pydantic model and pickles cleanly.
- **Test marker**: `@pytest.mark.slow`, registered in `pyproject.toml`, **runs by default** in `uv run pytest`. The first run pays the `BAAI/bge-small-en-v1.5` download (~100 MB). Subsequent runs hit the local `sentence-transformers` cache then our `.cache/rag/mechanical/`.

## Files affected

### New

| Path | Purpose |
|---|---|
| `src/expertview/rag/domains/mechanical.py` | Public factory `load_mechanical_store(embeddings)` returning a populated `InMemoryKnowledgeStore`. |
| `src/expertview/rag/cache.py` | Generic embedding-cache helpers (`corpus_manifest_hash`, `load_cached_vectors`, `write_cache`). Sits in `rag/` because it is RAG-internal; not exposed past the loader. Phase 3's four other domain loaders will reuse it. |
| `tests/integration/test_mechanical_rag.py` | End-to-end test: real embedding model, real corpus, real `InMemoryKnowledgeStore.search`. Asserts at least one returned `Document` has `domain == "mechanical"` and non-empty `content`, and that cache hit on second call is byte-identical to the first. |

### Edited

| Path | Change |
|---|---|
| `.gitignore` | Add `.cache/` line. (`data/cache/` is already excluded; `.cache/` at the repo root is not.) |
| `pyproject.toml` | Register the `slow` pytest marker under `[tool.pytest.ini_options].markers`. No dependency changes. |

### Untouched

- `src/expertview/rag/base.py` (`KnowledgeStore` protocol). The cache is hidden behind `load_mechanical_store()`; the protocol stays as-is per architecture rule.
- `src/expertview/rag/inmemory.py`. `InMemoryKnowledgeStore` accepts an `Embeddings` instance; we use its existing `ingest()` for the cache-miss path.
- `src/expertview/agents/llms.py`. The loader **imports** `create_embeddings` but never instantiates `HuggingFaceEmbeddings` itself — architecture rule.
- `src/expertview/rag/domains/__init__.py`. Already exists as empty package marker.

## Sketch of the change

### `rag/cache.py`

```python
# Pseudocode shape — final names may differ.

CACHE_ROOT = Path(".cache/rag")

def corpus_manifest_hash(paths: Iterable[Path]) -> str:
    """SHA-256 over the sorted list of (relative_path, sha256_of_bytes) pairs."""

def cache_path(domain: str) -> Path:
    return CACHE_ROOT / domain / "vectors.pkl"

def write_cache(domain: str, manifest_hash: str, items: list[tuple[Document, list[float]]]) -> None:
    """Atomic write: pickle to a temp file, then replace."""

def load_cached_vectors(domain: str, manifest_hash: str) -> list[tuple[Document, list[float]]] | None:
    """Return cached items if the manifest hash matches; None otherwise. On any
    deserialization failure, return None (the caller re-embeds and overwrites)."""
```

### `rag/domains/mechanical.py`

```python
# Pseudocode shape.

CORPUS_DIR = Path("data/domains/mechanical")
DOMAIN = "mechanical"

def load_mechanical_store(embeddings: Embeddings) -> InMemoryKnowledgeStore:
    docs = _read_corpus()                              # pydantic Documents
    manifest = corpus_manifest_hash(_corpus_paths())
    cached = load_cached_vectors(DOMAIN, manifest)

    store = InMemoryKnowledgeStore(domain=DOMAIN, embeddings=embeddings)
    if cached is not None:
        _ingest_precomputed(store, cached)             # bypass re-embedding
    else:
        store.ingest(docs)                             # embeds via Embeddings
        vectors = embeddings.embed_documents([d.content for d in docs])
        write_cache(DOMAIN, manifest, list(zip(docs, vectors)))
    return store
```

Notes on `_ingest_precomputed`:

- `InMemoryVectorStore` exposes `add_texts(texts, metadatas, ids, embeddings=...)`-style insertion in current `langchain-core` releases. We use that to push the cached vectors in without invoking the embedder. If the installed version does not expose a vectors-as-arg path, we fall back to a thin wrapper that constructs `LCDocument`s and writes directly into `_store.store` (private attribute access is acceptable inside `rag/` — that is the layer that owns the LangChain coupling). This fallback is the *only* place we touch `InMemoryKnowledgeStore` internals.
- Either path produces a store whose `.search()` returns the same pydantic `Document`s as the cache-miss path.

### `tests/integration/test_mechanical_rag.py`

```python
import pytest
from expertview.agents.llms import create_embeddings
from expertview.rag.domains.mechanical import load_mechanical_store

pytestmark = pytest.mark.slow

def test_load_mechanical_store_returns_populated_store():
    """First run downloads BAAI/bge-small-en-v1.5 (~100 MB) and embeds the
    mechanical corpus. Subsequent runs hit the .cache/rag/mechanical/ pickle."""
    embeddings = create_embeddings()
    store = load_mechanical_store(embeddings)

    results = store.search("bearing batch", k=3)

    assert results
    assert any(r.domain == "mechanical" and r.content for r in results)
    assert any("bearing" in r.content.lower() for r in results)

def test_load_mechanical_store_cache_hit_is_consistent(tmp_path, monkeypatch):
    """Two consecutive loads return stores with the same search ranking for
    the same query — proves the cache round-trip preserves vectors."""
    embeddings = create_embeddings()
    s1 = load_mechanical_store(embeddings)
    s2 = load_mechanical_store(embeddings)
    q = "hydraulic cylinder maintenance"
    assert [d.id for d in s1.search(q, k=5)] == [d.id for d in s2.search(q, k=5)]
```

## Risks

- **Cache invariance under embedding-model change**: the manifest hash covers corpus files only, not the embedding model name. If the model in `agents/llms.py` ever changes, the cache silently serves stale vectors of the old model. Mitigation: include `EMBEDDING_MODEL_NAME` in the manifest hash. (Will implement this in `cache.py` from the start; cheap.)
- **`InMemoryVectorStore` API drift**: the "precomputed-vectors" insertion path depends on a method signature that varies across `langchain-core` minor versions. Mitigation: a single try/except inside `_ingest_precomputed`, with the fallback documented inline.
- **First-run test time**: pulling the embedding model on a clean machine can take several minutes. Mitigation: documented in the test docstring; marked `slow` so the developer sees the marker; default `pytest` still runs it but no other test depends on it.
- **Pickle / `Document` schema drift**: if `Document`'s pydantic fields change, old caches deserialize wrong. Mitigation: cache files are gitignored and disposable; the manifest hash mismatch will cause a re-embed; if pickle itself raises on schema change, the loader catches and re-embeds.

## Architecture-rule compliance

- `rag/domains/mechanical.py` imports `agents.llms` **only via the test** (via `create_embeddings`) — the loader itself takes `embeddings` as a parameter and never constructs one. This honors the `CLAUDE.md` rule that `rag/` does not instantiate provider clients.
- The loader returns the project's pydantic `Document`. LangChain's `LCDocument` does not leak past `_ingest_precomputed` (and is already not leaked by `InMemoryKnowledgeStore.search`).
- No imports from `agents/` (other than `llms`), `orchestration/`, or `evidence/` except `evidence.models.Document`.

## Verification

```powershell
uv run pytest tests/integration/test_mechanical_rag.py   # task DoD
uv run pytest                                            # whole suite stays green
uv run ruff check .                                      # lint
uv run ruff format --check .                             # format
```

If `uv run ruff format --check .` fails, run `uv run ruff format .` and amend.

## Deliverable

- Branch: `feature/mechanical-rag-loader` off latest `main` (which has Task 1's corpus).
- Commit(s): per `branching_strategy.md` §6 — `<area>: <one-line summary>`. Likely two commits: `rag: add mechanical domain loader with embedding cache` and `chore: register slow pytest marker`.
- PR opened with summary, files-touched list, verification command output, and a callout that this is Phase 2 Task 2.

## What this plan does **not** do

- Does not modify `KnowledgeStore` protocol — cache stays loader-internal per Task 2 §Risks.
- Does not implement the four other domain loaders (Phase 3).
- Does not wire the loader into the LangGraph runner (Task 5 of Phase 2).
- Does not introduce a reranker (dropped from v1 per 2026-05-26 decision).
