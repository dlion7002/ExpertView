"""On-disk embedding cache for domain RAG loaders.

Phase 2 introduces this so demo rehearsals do not pay the embedding cost on
every run. Cache layout: one pickle file per domain under `.cache/rag/<domain>/`
holding `(Document, embedding_vector)` pairs plus a manifest hash. Cache hit
when the recomputed manifest matches the stored one; any deserialization
failure or hash miss triggers a fresh embed and overwrite.

The cache is loader-internal: it never crosses the `KnowledgeStore` protocol
boundary. Phase 3's four other domain loaders will reuse these helpers.
"""

from __future__ import annotations

import hashlib
import pickle
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from expertview.evidence.models import Document

_CACHE_ROOT = Path(".cache/rag")
_CACHE_FILE = "vectors.pkl"


@dataclass(frozen=True)
class CachedCorpus:
    manifest_hash: str
    items: list[tuple[Document, list[float]]]


def corpus_manifest_hash(paths: Iterable[Path], embedding_signature: str) -> str:
    """Hash over sorted (relative_path, content_sha256) pairs plus the
    embedding signature. Embedding signature is included so a model swap
    invalidates the cache automatically — otherwise stale vectors of the old
    model would silently serve queries computed against the new model."""
    digest = hashlib.sha256()
    digest.update(embedding_signature.encode("utf-8"))
    digest.update(b"\x00")
    for path in sorted(paths):
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\x00")
        digest.update(content_hash.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


def cache_path(domain: str) -> Path:
    return _CACHE_ROOT / domain / _CACHE_FILE


def load_cached_corpus(domain: str, manifest_hash: str) -> CachedCorpus | None:
    path = cache_path(domain)
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            cached: CachedCorpus = pickle.load(f)
    except (pickle.UnpicklingError, EOFError, AttributeError, ImportError):
        # Corrupted or schema-incompatible cache: signal a miss; caller re-embeds.
        return None
    if not isinstance(cached, CachedCorpus) or cached.manifest_hash != manifest_hash:
        return None
    return cached


def write_cache(
    domain: str,
    manifest_hash: str,
    items: list[tuple[Document, list[float]]],
) -> None:
    path = cache_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = CachedCorpus(manifest_hash=manifest_hash, items=items)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def embedding_signature(embeddings: object) -> str:
    """Best-effort identifier for the embedding model behind an `Embeddings`
    instance. `HuggingFaceEmbeddings` exposes `.model_name`; other providers
    may not — fall back to the class name so the signature is at least stable
    within a single provider choice."""
    return str(getattr(embeddings, "model_name", type(embeddings).__name__))
