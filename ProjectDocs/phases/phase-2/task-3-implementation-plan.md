# Task 3 Implementation Plan — Mechanical Investigator

## Goal

Add the first real investigator node for the Phase 2 vertical slice. The node is bound to a `KnowledgeStore` and an investigator LLM at graph-build time, queries mechanical evidence from the incident context, and returns a LangGraph state patch containing validated `Finding` models.

## Affected Files

- `src/expertview/prompts/investigator/mechanical.md` — versioned prompt for the mechanical investigator.
- `src/expertview/agents/investigators/mechanical.py` — node factory and LLM-boundary parsing.
- `tests/unit/test_mechanical_investigator.py` — deterministic unit coverage with fake store and fake LLM.

## Change Sketch

- Create a mechanical investigator prompt that requires evidence-only reasoning, JSON-array output, `investigator_domain="mechanical"`, confidence scores in `[0, 1]`, and citations using retrieved document `id` or `source`.
- Implement `make_mechanical_investigator_node(store, llm, *, k=5)` so Task 5 can inject the real mechanical store and OpenRouter investigator LLM.
- Derive the retrieval query from the incident summary, symptoms, and affected assets.
- Parse the LLM response with `TypeAdapter(list[Finding])` at the model boundary, then enforce mechanical domain and citation validity before returning `{"findings": findings}`.

## Risks

- Real `openrouter/owl-alpha` may return prose or fenced JSON despite the prompt. This PR intentionally raises clear validation errors; Task 5's end-to-end verification is where real-model prompt behavior is exercised.
- Retrieval quality depends on the mechanical corpus wording from Task 1 and the loader from Task 2. This task keeps query derivation broad enough to include summary, symptoms, and affected assets.

## Verification

- `uv run pytest tests/unit/test_mechanical_investigator.py`
- `uv run pytest`
- `uv run ruff check .`
- `uv run ruff format --check .`
