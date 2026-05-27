"""Supply-chain-domain RAG loader."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from langchain_core.embeddings import Embeddings

from expertview.evidence.models import Document
from expertview.rag.cache import (
    corpus_manifest_hash,
    embedding_signature,
    load_cached_corpus,
    write_cache,
)
from expertview.rag.inmemory import InMemoryKnowledgeStore

DOMAIN = "supply_chain"
CORPUS_DIR = Path("data/domains/supply_chain")


def load_supply_chain_store(embeddings: Embeddings) -> InMemoryKnowledgeStore:
    paths = _corpus_paths()
    docs = [_read_document(p) for p in paths]
    manifest = corpus_manifest_hash(paths, embedding_signature(embeddings))
    store = InMemoryKnowledgeStore(domain=DOMAIN, embeddings=embeddings)

    cached = load_cached_corpus(DOMAIN, manifest)
    if cached is not None:
        _ingest_precomputed(store, cached.items)
        return store

    store.ingest(docs)
    vectors = embeddings.embed_documents([d.content for d in docs])
    write_cache(DOMAIN, manifest, list(zip(docs, vectors, strict=True)))
    return store


def _corpus_paths() -> list[Path]:
    return sorted(CORPUS_DIR.glob("*.md"))


def _read_document(path: Path) -> Document:
    content = path.read_text(encoding="utf-8")
    return Document(
        id=path.stem,
        content=content,
        source=path.as_posix(),
        domain=DOMAIN,
        metadata={"line_count": content.count("\n") + 1},
    )


def _ingest_precomputed(
    store: InMemoryKnowledgeStore,
    items: Iterable[tuple[Document, list[float]]],
) -> None:
    """Bypass the embedder by writing directly into the underlying
    `InMemoryVectorStore`'s dict. Touching `_store` internals here is the
    deliberate price of a precomputed-vectors path; it is scoped to a single
    helper and never crosses the `KnowledgeStore` protocol boundary."""
    internal = store._store.store
    for doc, vector in items:
        internal[doc.id] = {
            "id": doc.id,
            "vector": list(vector),
            "text": doc.content,
            "metadata": {"source": doc.source, "domain": doc.domain, **doc.metadata},
        }
