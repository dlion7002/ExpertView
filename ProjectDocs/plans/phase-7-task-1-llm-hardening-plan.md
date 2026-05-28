# Plan — Phase 7 Task 1: LLM Hardening (Retry/Backoff, Seed, Cache-Invalidation Rule)

> Source task: [ProjectDocs/phases/phase-7/task-1-llm-hardening.md](../phases/phase-7/task-1-llm-hardening.md)
> Branch: `feature/phase-7-llm-hardening`

## Files affected

- **Edit**: `src/expertview/agents/llms.py`
- **New**: `tests/unit/test_llms.py`
- **New**: `ProjectDocs/plans/phase-7-task-1-llm-hardening-plan.md` (this file)

No other files touched. No node code, no prompts, no dependencies.

## Locked decisions (this turn)

1. **Seed scope** → synthesizer only. Investigator already runs at `temperature=0.0`; the synthesizer is the call whose text the demo reads.
2. **Status detection** → read status off exception attributes (`status_code`, `response.status_code`, `.code`), with a permissive catch-all that logs a warning. Avoids `isinstance` against `langchain-openai`/`openai` SDK exception hierarchy churn.
3. **Sleep pattern** → inject sleep callable on `RetryingLlm.__init__` (default `asyncio.sleep`). Tests pass an instantaneous fake; no module-level patch.
4. **Wrapper shape** → class `RetryingLlm` mirroring `ThrottledInvestigatorLlm`'s `_InvokableLlm` shape. Composes symmetrically.

These will also be logged in `ProjectDocs/decisions.md` per CLAUDE.md.

## Retry policy spec

- Cap: **3 attempts** total (initial + 2 retries).
- Backoff: base **1.0s**, multiplier **2.0** → 1s, 2s. Ceiling **8s**. Jitter: full-jitter, multiply by `random.uniform(0.5, 1.0)`.
- `Retry-After` (seconds or HTTP-date) honored when present on the exception's response; takes precedence over computed backoff for that attempt.
- Retry on: HTTP **429** and **5xx** (500–599). Re-raise immediately on any other 4xx and on exceptions that carry no recoverable status (after the permissive catch-all logs once and treats as non-retryable).
- On exhaustion: re-raise the last exception, preserving traceback context.

## Composition order

- `create_investigator_llm` → `ThrottledInvestigatorLlm(RetryingLlm(ChatOpenAI(...)), _INVESTIGATOR_SEMAPHORE)`. Semaphore gates entry **before** retry loop holds the slot — preserves Phase 3's concurrency cap honestly under retry pressure.
- `create_synthesizer_llm` → `RetryingLlm(ChatOpenAI(..., model_kwargs={"seed": SYNTHESIZER_SEED}))`. No semaphore.
- Return types remain assignment-compatible with `_InvokableLlm`. Factory signatures unchanged.

## Seed surface

```python
SYNTHESIZER_SEED: Final = 17
```

Passed via `model_kwargs={"seed": SYNTHESIZER_SEED}` on the synthesizer `ChatOpenAI` constructor. Docstring on the constant calls out the best-effort upstream caveat.

## Embedding cache-invalidation docstring (verbatim target wording)

A multi-line docstring section on `create_embeddings`:

> **Embedding cache invalidation rule (hard contract).**
> `EMBEDDING_MODEL_NAME` is the cache key for every per-domain index under
> `rag/domains/*` (`mechanical.py`, `process.py`, `supply_chain.py`,
> `environmental.py`, `human_factors.py`). If `EMBEDDING_MODEL_NAME` changes,
> every cached pickle/serialized index under `.cache/rag/` is stale and **must**
> be deleted before next run. This is a developer-time contract, not a runtime
> check.

(Cited loader paths verified against `src/expertview/rag/domains/`.)

## Tests (offline, deterministic)

In `tests/unit/test_llms.py`:

1. `test_retry_succeeds_after_two_429s` — fake `ainvoke` raises 429-shaped error twice, succeeds on third; assert result and attempt count == 3.
2. `test_retry_succeeds_after_two_500s` — same shape, 500.
3. `test_retry_reraises_400_without_retrying` — 400 → re-raised on first attempt; assert attempt count == 1.
4. `test_retry_exhausts_cap_on_persistent_429` — 429 four times → assert raises after 3 attempts.
5. `test_retry_honors_retry_after_header` — 429 with `Retry-After: 0.5` then success → assert injected sleep was called with ≥0.5 on that attempt.
6. `test_synthesizer_seed_propagates_to_chatopenai` — monkeypatch `ChatOpenAI` constructor; assert `model_kwargs={"seed": 17}` was passed.
7. `test_investigator_factory_composes_retry_inside_semaphore` — monkeypatch `ChatOpenAI`; assert returned object is `ThrottledInvestigatorLlm` wrapping a `RetryingLlm`.

All tests inject a synchronous `asyncio.sleep` replacement; no real sleeps, no network.

## decisions.md entry

Append one entry: "Phase 7 Task 1 — RetryingLlm wrapper + SYNTHESIZER_SEED=17 + embedding cache-invalidation contract. Seed applied to synthesizer only. Status detection by attribute lookup, not `isinstance`. Sleep callable injected for testability."

## Risks

- `langchain-openai` may not surface raw HTTP status on every exception. Mitigation: try `e.status_code`, `e.response.status_code`, `e.code`; fall through to log + non-retryable.
- `model_kwargs={"seed": ...}` constructor surface may differ on the installed `langchain-openai` version. Mitigation: if `model_kwargs` rejects `seed`, fall back to passing `seed=` directly on `ChatOpenAI` (caught at construction time by tests).
- `Retry-After` may be HTTP-date format. Mitigation: parse with `email.utils.parsedate_to_datetime`; on failure, ignore the header and use computed backoff.

## Verification

```powershell
uv run pytest tests/unit/test_llms.py -v
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

All four must be green before commit.

## Out of scope (explicit)

- No edits under `agents/investigators/*` or `agents/synthesizer.py`.
- No graph topology changes.
- No new dependency.
- No automatic cache invalidation code in `rag/domains/*`.
- No streaming/CLI/Streamlit changes.
