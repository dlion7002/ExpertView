# Task 3 — RAG Skeleton

> **Branch suggestion**: `feature/rag-skeleton`
> **Parallelism**: **Parallelizable with Tasks 4 and 5.**
> **Depends on**: Task 2 (`evidence/models.py` provides `Document`).

## Purpose

Define the `KnowledgeStore` protocol that *every* RAG store in the project must satisfy, and ship a v1 implementation that wraps LangChain's `InMemoryVectorStore`. This is the single public surface through which investigators query domain knowledge — Phase 2's mechanical loader and Phase 3's four additional domain loaders all build on top of it.

No real corpora are embedded here. This task delivers the *contract* and a *stub-quality implementation* that round-trips an empty or trivially seeded store. Domain corpora and loaders land in Phase 2 (mechanical) and Phase 3 (the other four).

## Why it matters

- [architecture.md §5](../../architecture.md) makes `KnowledgeStore` the sole legal entry point into the RAG layer: *"Callers cannot reach into vector store internals; if a caller needs more, extend the protocol."* This task establishes that wall.
- [decisions.md (2026-05-25 vector store)](../../decisions.md) locks `InMemoryVectorStore` for v1 with FAISS as the pre-identified upgrade path. The protocol is what makes that future swap cost ~one file.
- The Path B reusability story in [vision.md §6](../../vision.md) lists `rag/` as one of the priority lift-able units. A clean protocol is what makes that lift trivial.

## Concrete steps (what to produce)

1. **Create `src/expertview/rag/base.py`** with the `KnowledgeStore` Protocol from [architecture.md §3](../../architecture.md): a `domain: str` attribute and a `search(query: str, k: int = 5) -> list[Document]` method. Import `Document` from `evidence/models.py`. Keep the surface minimal — extend the protocol later if a caller needs more ([architecture.md §5](../../architecture.md)).
2. **Create `src/expertview/rag/inmemory.py`** with an `InMemoryKnowledgeStore` class that satisfies the `KnowledgeStore` protocol by wrapping LangChain's `InMemoryVectorStore`. Constructor takes the `domain` label and an embeddings instance (passed in, not constructed — keeps the LLM/embeddings client out of `rag/`, see architecture rule). Provide a way to ingest a list of `Document`s and a `search()` implementation that delegates to the underlying vector store and returns `Document` instances (translating from whatever LangChain returns into the project's pydantic `Document` model).
3. **Confirm the architecture wall**: `rag/inmemory.py` may import from `langchain_core` and `langchain_community` per [architecture.md §5](../../architecture.md), but **must not** import from `agents/` or `orchestration/`. Embeddings instances are *passed in*, never constructed inside `rag/` — `agents/llms.py` is the only legal construction site for any model client (architecture rule + [CLAUDE.md architecture rules](../../../CLAUDE.md)).
4. **Add a unit test** in `tests/unit/test_rag_inmemory.py` that:
   - Builds an `InMemoryKnowledgeStore` with a fake/stub embeddings object (a deterministic local fake is fine — this is a unit test, not a provider test).
   - Ingests two or three trivial `Document` instances.
   - Calls `search()` and asserts the return type is `list[Document]` with the right shape.
   The point of this test is to lock the protocol satisfaction, not to validate embedding quality. Real-embedding tests belong in Phase 2.
5. **Verify quality gates locally**: `uv run pytest tests/unit/test_rag_inmemory.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- Step 1 establishes the protocol. Once merged, Phase 2's mechanical loader and Phase 3's other loaders all *must* satisfy it, and investigator nodes can type their RAG handle as `KnowledgeStore` without caring about the implementation.
- Step 2 ships the v1 backing implementation. Investigators get a real (if currently empty) store to query.
- Step 3 enforces the module-boundary rules during review. If the implementation grows imports from `agents/`, the wall is violated.
- Step 4 proves the protocol implementation works in isolation, using a fake embeddings shim so the unit test does not hit the network. Provider connectivity is verified separately in Task 4.
- Step 5 is the local quality gate.

## Code locations

- `src/expertview/rag/base.py` (new).
- `src/expertview/rag/inmemory.py` (new).
- `tests/unit/test_rag_inmemory.py` (new).

## Connections

**Upstream**:

- Imports `Document` from Task 2's `evidence/models.py`.
- Project skeleton from Task 1 must exist.

**Downstream**:

- Phase 2 `rag/domains/mechanical.py` loader reads `data/domains/mechanical/*.md`, embeds via the local `HuggingFaceEmbeddings` instance constructed in `agents/llms.py`, and returns an `InMemoryKnowledgeStore`.
- Phase 3 adds `rag/domains/{process,supply_chain,environmental,human_factors}.py` loaders following the same pattern.
- Phase 2+ investigator nodes accept a `KnowledgeStore` and call `.search()` against it.
- Phase 7's optional FAISS upgrade swaps the implementation behind the protocol without touching any caller — that is exactly the swap the protocol exists to make cheap.

## Parallelism rationale

- Tasks 3, 4, and 5 each import only from `evidence/` (and stdlib / third-party libraries). They do **not** import from each other.
- The architecture rule "module boundaries are walls" ([architecture.md §5](../../architecture.md)) is what makes this safe: `rag/` cannot reach into `agents/` or `orchestration/`, so there is no shared editing surface to conflict on.
- A second agent can take Task 4 and a third agent can take Task 5 at the same time as this one, on separate `feature/*` branches. Merge order does not matter among Tasks 3/4/5.

## Risks / constraints / assumptions

- **Constraint**: `langchain_openai` and `langchain_huggingface` are forbidden in `rag/` ([architecture.md §5](../../architecture.md)). Only `langchain_core` and `langchain_community` are allowed.
- **Constraint**: embeddings instances are *passed in* to the store, never constructed inside `rag/`. Constructing a `ChatOpenAI` / `HuggingFaceEmbeddings` is exclusively `agents/llms.py`'s job ([CLAUDE.md architecture rules](../../../CLAUDE.md)).
- **Risk**: returning LangChain's native `Document` type instead of the project's pydantic `Document` would leak an internal type past the protocol boundary. The implementation must translate. This is exactly the kind of silent contract drift the protocol is meant to prevent.
- **Risk**: over-extending the protocol now ("we'll need filtering / metadata search / hybrid retrieval"). [CLAUDE.md coding standards](../../../CLAUDE.md): *"Don't add features, refactor, or introduce abstractions beyond what the task requires."* Phase 2 will tell you what `KnowledgeStore` actually needs.
- **Assumption**: a deterministic local fake embeddings object is good enough for the unit test. If `langchain_core` does not ship a usable test double, a one-class fake in the test file is acceptable.
- **Assumption**: the v1 implementation embeds at ingest time and does not persist to disk — per [decisions.md (2026-05-25 vector store)](../../decisions.md), persistence is the FAISS-upgrade trigger, not a v1 concern.

## Definition of done

- `KnowledgeStore` protocol exists in `rag/base.py` and matches the [architecture.md §3](../../architecture.md) sketch.
- `InMemoryKnowledgeStore` exists in `rag/inmemory.py`, satisfies the protocol, and translates results into the project's pydantic `Document` model.
- Unit test passes against the in-memory implementation using a stub embeddings object — no network call.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- No imports from `agents/` or `orchestration/` in `rag/` (architecture wall held).
- PR opened on `feature/rag-skeleton` per [branching_strategy.md §5](../../branching_strategy.md).
