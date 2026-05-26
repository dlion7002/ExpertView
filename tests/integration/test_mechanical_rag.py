"""End-to-end test for the mechanical RAG loader.

First run downloads `BAAI/bge-small-en-v1.5` (~100 MB) and embeds the full
mechanical corpus. Subsequent runs hit `.cache/rag/mechanical/vectors.pkl`
and skip re-embedding. Marked `slow` so the cost is visible in pytest output;
the test still runs by default — it is the only path in CI that exercises
the real embedding model against the real corpus.
"""

from __future__ import annotations

import pytest

from expertview.agents.llms import create_embeddings
from expertview.evidence.models import Document
from expertview.rag.domains.mechanical import DOMAIN, load_mechanical_store

pytestmark = pytest.mark.slow


def test_load_mechanical_store_returns_populated_store() -> None:
    embeddings = create_embeddings()
    store = load_mechanical_store(embeddings)

    results = store.search("bearing batch new supplier", k=3)

    assert results, "search returned no results"
    assert all(isinstance(r, Document) for r in results)
    assert all(r.domain == DOMAIN for r in results)
    assert all(r.content.strip() for r in results)
    assert any("bearing" in r.content.lower() for r in results), (
        "expected at least one bearing-related document in the top-3 results"
    )


def test_load_mechanical_store_cache_round_trip_preserves_ranking() -> None:
    """Two consecutive loads must return the same top-k ranking for the same
    query — proves the cache round-trip preserves the vectors faithfully."""
    embeddings = create_embeddings()
    first = load_mechanical_store(embeddings)
    second = load_mechanical_store(embeddings)

    query = "hydraulic cylinder maintenance"
    first_ids = [d.id for d in first.search(query, k=5)]
    second_ids = [d.id for d in second.search(query, k=5)]

    assert first_ids == second_ids
