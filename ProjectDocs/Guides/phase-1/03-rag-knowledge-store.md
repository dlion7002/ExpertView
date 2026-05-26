# RAG Knowledge Store

## Purpose

This guide explains the Phase 1 RAG boundary. Investigators will eventually query domain corpora through the `KnowledgeStore` protocol. Phase 1 implements that protocol with a LangChain `InMemoryVectorStore` wrapper while keeping LangChain's document type behind the boundary.

## Flow Summary

1. Caller creates project-level `Document` models from `evidence/models.py`.
2. Caller creates or receives an embeddings object from `agents/llms.py` later; Phase 1 tests use a deterministic fake embedding.
3. Caller creates `InMemoryKnowledgeStore(domain, embeddings)`.
4. `ingest()` converts each ExpertView `Document` into a LangChain `Document` and stores it by ID.
5. `search(query, k)` delegates to LangChain similarity search.
6. Search results are converted back into ExpertView `Document` models before leaving the RAG layer.

## Relevant Files

- `src/expertview/rag/base.py`: public `KnowledgeStore` protocol.
- `src/expertview/rag/inmemory.py`: v1 implementation backed by LangChain `InMemoryVectorStore`.
- `src/expertview/evidence/models.py`: owns the `Document` model used at the RAG boundary.
- `src/expertview/agents/llms.py`: creates the local `HuggingFaceEmbeddings` instance (`BAAI/bge-small-en-v1.5` via `sentence-transformers`).
- `tests/unit/test_rag_inmemory.py`: offline protocol and translation tests.

## Step 1 - Public RAG Protocol

### Location

`src/expertview/rag/base.py`

### Code

```python
"""Public surface for the RAG layer.

Investigators reach into domain knowledge only through `KnowledgeStore`.
Vector store internals stay behind this protocol per the architecture rule in
`ProjectDocs/architecture.md` §5 ("if a caller needs more, extend the
protocol"). The protocol is also what makes the v1 InMemoryVectorStore
implementation swappable for FAISS in a single file
(`ProjectDocs/decisions.md` 2026-05-25 vector store).
"""

from typing import Protocol

from expertview.evidence.models import Document


class KnowledgeStore(Protocol):
    domain: str

    def search(self, query: str, k: int = 5) -> list[Document]: ...
```

### What it does

`KnowledgeStore` defines the only public surface investigators should use to query RAG data: a `domain` label and a `search()` method returning project-level `Document` models.

### What it receives or depends on

- `typing.Protocol` for structural typing.
- `Document` from `evidence/models.py`.

### What it produces or changes

It produces a stable contract for any future store implementation. Callers can type against `KnowledgeStore` without knowing whether the backing store is in-memory, FAISS, or something else.

### What it connects to

- `rag/inmemory.py`: implements this protocol.
- Future investigator nodes: should accept or hold `KnowledgeStore`, not a concrete vector store.
- Future domain loaders under `rag/domains/`: should return objects satisfying this protocol.

### Why it matters

This keeps vector store internals from leaking across module boundaries. If the project upgrades from in-memory storage later, callers should not change.

## Step 2 - In-Memory Implementation And Document Translation

### Location

`src/expertview/rag/inmemory.py`

### Code

```python
"""v1 `KnowledgeStore` backed by LangChain's `InMemoryVectorStore`.

Domain corpora and per-domain loaders land in phase 2+. This module ships the
contract and a stub-quality implementation that round-trips through the
project's pydantic `Document` model. The translation step is what keeps
LangChain's native `Document` from leaking past the protocol boundary
(`ProjectDocs/architecture.md` §5).

Embeddings are passed in, never constructed here — only `agents/llms.py` may
instantiate model clients per `CLAUDE.md` architecture rules.
"""

from collections.abc import Iterable

from langchain_core.documents import Document as LCDocument
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from expertview.evidence.models import Document


class InMemoryKnowledgeStore:
    domain: str

    def __init__(self, domain: str, embeddings: Embeddings) -> None:
        self.domain = domain
        self._store = InMemoryVectorStore(embedding=embeddings)

    def ingest(self, documents: Iterable[Document]) -> None:
        docs = list(documents)
        self._store.add_documents(
            [_to_langchain(d) for d in docs],
            ids=[d.id for d in docs],
        )

    def search(self, query: str, k: int = 5) -> list[Document]:
        return [_from_langchain(r) for r in self._store.similarity_search(query, k=k)]


def _to_langchain(doc: Document) -> LCDocument:
    return LCDocument(
        id=doc.id,
        page_content=doc.content,
        metadata={"source": doc.source, "domain": doc.domain, **doc.metadata},
    )


def _from_langchain(lc: LCDocument) -> Document:
    # `source` and `domain` are first-class fields on our pydantic Document, so
    # they are stored at the top level of LangChain's metadata dict and lifted
    # back out here. Whatever remains is the caller's metadata payload.
    extra = dict(lc.metadata)
    source = extra.pop("source")
    domain = extra.pop("domain")
    return Document(
        id=lc.id,
        content=lc.page_content,
        source=source,
        domain=domain,
        metadata=extra,
    )
```

### What it does

`InMemoryKnowledgeStore` wraps LangChain's `InMemoryVectorStore` but exposes ExpertView's `Document` model at the boundary.

`ingest()` materializes the incoming iterable, converts each project `Document` into a LangChain document, and uses the project document IDs as store IDs.

`search()` asks LangChain for similar documents and converts every result back into the pydantic `Document` model.

`_to_langchain()` maps:

- `Document.id` -> LangChain document `id`
- `Document.content` -> `page_content`
- `Document.source`, `Document.domain`, and `Document.metadata` -> LangChain metadata

`_from_langchain()` reverses that mapping and lifts `source` and `domain` back into first-class pydantic fields.

### What it receives or depends on

- `Embeddings` instance passed into the constructor.
- `Document` models from callers.
- LangChain `InMemoryVectorStore`.

### What it produces or changes

- Produces stored vector documents inside the private `_store`.
- Produces `list[Document]` from `search()`.
- Does not construct provider clients or embeddings itself.

### What it connects to

- `agents/llms.py`: future real embeddings should be created there and passed in.
- `evidence/models.py`: the only document type that leaves this layer.
- Future `rag/domains/*` loaders: will build and seed this store.
- Future investigators: will call only `.search()`.

### Why it matters

The translation layer protects the architecture rule that RAG internals stay behind `KnowledgeStore`. It also makes a future FAISS swap localized to the implementation file.

## Step 3 - Offline Store Tests

### Location

`tests/unit/test_rag_inmemory.py`

### Code

```python
"""Unit tests for the v1 in-memory `KnowledgeStore`.

These tests lock the protocol contract — they exist to catch silent drift in
the LangChain↔pydantic Document translation, not to validate embedding
quality. Real-embedding tests belong with the phase 2 mechanical-domain
loader. A deterministic fake embeddings object keeps the test offline.
"""

from langchain_core.embeddings import DeterministicFakeEmbedding

from expertview.evidence.models import Document
from expertview.rag.base import KnowledgeStore
from expertview.rag.inmemory import InMemoryKnowledgeStore

_FAKE_EMBEDDING_DIM = 8


def _store() -> InMemoryKnowledgeStore:
    return InMemoryKnowledgeStore(
        domain="mechanical",
        embeddings=DeterministicFakeEmbedding(size=_FAKE_EMBEDDING_DIM),
    )


def _docs() -> list[Document]:
    return [
        Document(
            id="mech-001",
            content="Hydraulic cylinder seal kit replaced on shift 3.",
            source="data/domains/mechanical/hydraulic_service_log.md",
            domain="mechanical",
            metadata={"tags": ["hydraulic", "maintenance"]},
        ),
        Document(
            id="mech-002",
            content="Bearing batch B-227 from new supplier installed line 2.",
            source="data/domains/mechanical/bearing_batch_log.md",
            domain="mechanical",
            metadata={"supplier": "acme-bearings"},
        ),
        Document(
            id="mech-003",
            content="Spindle vibration trending upward over last 200 cycles.",
            source="data/domains/mechanical/vibration_report.md",
            domain="mechanical",
        ),
    ]


def test_inmemory_store_satisfies_protocol() -> None:
    store: KnowledgeStore = _store()
    assert store.domain == "mechanical"


def test_search_returns_pydantic_documents() -> None:
    store = _store()
    store.ingest(_docs())

    results = store.search("bearing", k=3)

    assert isinstance(results, list)
    assert len(results) == 3
    for doc in results:
        assert isinstance(doc, Document)
        assert doc.domain == "mechanical"


def test_search_preserves_document_fields() -> None:
    store = _store()
    seeded = _docs()
    store.ingest(seeded)

    results = store.search("hydraulic", k=3)

    by_id = {d.id: d for d in results}
    original = {d.id: d for d in seeded}
    assert by_id.keys() == original.keys()
    for doc_id, retrieved in by_id.items():
        assert retrieved == original[doc_id]


def test_search_respects_k() -> None:
    store = _store()
    store.ingest(_docs())

    assert len(store.search("anything", k=1)) == 1
    assert len(store.search("anything", k=2)) == 2


def test_empty_store_returns_empty_list() -> None:
    store = _store()
    assert store.search("anything") == []
```

### What it does

The tests seed the in-memory store with project `Document` instances and prove that search returns project `Document` instances with fields preserved.

`DeterministicFakeEmbedding` keeps these tests offline. They do not validate embedding quality or provider connectivity.

### What it connects to

- `KnowledgeStore`: structural protocol assignment verifies the implementation shape.
- `InMemoryKnowledgeStore`: ingest/search behavior is exercised.
- `Document`: pydantic translation is checked.
- `agents/llms.py`: real embeddings are intentionally not used here.

### Why it matters

This test catches the most likely RAG skeleton regressions: returning LangChain documents, dropping metadata, ignoring `k`, or failing on an empty store.

## Where To Look Next

After the RAG boundary, the next Phase 1 flow is the agent contract and provider factory:

- `04-agent-protocols-and-llm-factory.md`
- `src/expertview/agents/base.py`
- `src/expertview/agents/llms.py`
