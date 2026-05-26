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

    # Converts Documents to LangChain format and ingests them to the vector store
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
