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
