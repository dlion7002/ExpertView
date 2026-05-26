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
