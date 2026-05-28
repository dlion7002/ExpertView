# Task 1 — LLM Hardening: Retry/Backoff, Determinism, and the Embedding Cache-Invalidation Rule

> **Branch suggestion**: `feature/phase-7-llm-hardening`
> **Parallelism**: **Parallelizable with Task 2.** Both unblock immediately on Phase 6 close; they edit disjoint surfaces. No shared editing surface with Task 2.
> **Depends on**: Phase 6 complete (`v0.7.0-demo` tagged).

## Purpose

Make the OpenRouter call path resilient and reproducible. Today `agents/llms.py` constructs `ChatOpenAI` clients (one for investigators, wrapped in a semaphore; one for the synthesizer) with `temperature=0.0` and no retry, no seed, no documented cache-invalidation contract. This task adds three small, additive changes inside that single module:

1. A retry/backoff wrapper covering OpenRouter `429` rate limits and transient `5xx` responses, layered around the existing `ChatOpenAI.ainvoke(...)` calls so the orchestration layer remains unaware.
2. A deterministic seed applied to the synthesizer client (and any other LLM call that supports it) so the same incident produces the same draft `CausalReport` text across runs, modulo upstream-provider non-determinism that no client-side setting can control.
3. A docstring/comment block near `create_embeddings()` that formalizes the **embedding cache invalidation rule** — the local RAG caches under `rag/domains/*` are keyed by the embedding model identity, so bumping the model name invalidates every cached index.

This task does **not** touch the graph topology, the investigator nodes, the synthesizer node body, the convergence math, the prompts, the streaming core, the Streamlit app, or the CLI. It does not introduce a new dependency. The retry wrapper is composed with the existing `ThrottledInvestigatorLlm` so the semaphore still gates concurrency before the retry loop starts.

## Why it matters

- [build_plan.md §Phase 7](../../build_plan.md) lists "retry/backoff wrapper inside `agents/llms.py` covering the OpenRouter `ChatOpenAI` client (429s, transient 5xxs)" as a required output, and the [risk register](../../build_plan.md) names "OpenRouter rate-limit during live demo" as a top in-event risk with this retry as its real fix. The Phase 3 semaphore caps concurrency but cannot recover from a `429`; this task is the recovery layer.
- [build_plan.md §Phase 7](../../build_plan.md) also requires "deterministic seed for any sampling; embedding cache invalidation rule documented." Both are surface decisions inside `agents/llms.py` — the only legal LLM-client construction site per [architecture.md §5](../../architecture.md) and [CLAUDE.md architecture rules](../../../CLAUDE.md) — so they belong together here.
- The Phase 7 human rehearsal (performed by the user post-merge — see [[task-3-paid-synth-rehearsal-and-readme]]) makes one paid-frontier synthesizer call per incident, against a billed lane on the user's $5 OpenRouter credit. A transient `429`/`5xx` without retry terminates that run, wastes the call's prefix tokens, and leaves no trace to export. Landing this task before Task 3 is what turns the paid swap from "best-effort" into a robust rehearsal once the user fires it.
- The seed and the cache-invalidation rule together make demo runs reproducible — the same incident + same corpus + same model identity yields the same CausalReport on repeat invocations. This matters both for `agent-trace-replay`-style reasoning and for any post-hoc comparison the user runs between rehearsal attempts.

## Concrete steps (what to produce)

1. **Add a retry/backoff wrapper inside `agents/llms.py`** — a small async helper (a class mirroring the existing `ThrottledInvestigatorLlm` shape, or a thin async function) that takes an object satisfying `_InvokableLlm` and wraps its `ainvoke(...)` in a bounded retry loop. Retry on OpenRouter `429` (rate-limited) and `5xx` (transient upstream) responses; do not retry on `4xx` other than `429` (those are deterministic prompt or auth errors). Use exponential backoff with jitter and a low retry cap (suggested: 3 attempts total, base ~1s, ceiling ~8s — the executing agent picks exact constants). Honor any `Retry-After` header OpenRouter returns. On exhaustion, re-raise the last exception with its context intact so the CLI's existing error handling can surface it.
2. **Compose the retry wrapper with the existing factories** so callers do not change:
   - `create_investigator_llm(...)` wraps `ChatOpenAI` in the retry wrapper *and then* in `ThrottledInvestigatorLlm`, preserving the rule that the semaphore gates entry before a retry loop holds a slot.
   - `create_synthesizer_llm(...)` wraps `ChatOpenAI` in the retry wrapper directly (no semaphore — the synthesizer is single-call).
   The return type of each factory should remain assignment-compatible with what the investigator and synthesizer nodes import today (the `_InvokableLlm` protocol is sufficient). No node code under `agents/investigators/*` or `agents/synthesizer.py` is edited in this task.
3. **Add a deterministic seed to the synthesizer client.** `ChatOpenAI` accepts a `seed` parameter that OpenRouter forwards to the upstream provider when the provider supports it (OpenAI, Anthropic via OR, DeepSeek, etc.). Choose a named module-level constant (e.g., `SYNTHESIZER_SEED: Final = 17`) and pass it via `model_kwargs={"seed": SYNTHESIZER_SEED}` (or the equivalent constructor surface in the installed `langchain-openai` version). Document in the docstring that the seed is a best-effort knob — upstream providers may ignore it, and OpenRouter routing may select an upstream that does not honor seeds; the goal is reproducibility when possible, not a hard guarantee. The investigator client may also receive the same seed if the executing agent judges it useful for Phase 7's reproducibility goal; default is to apply it to the synthesizer only since that is the call whose text the demo reads.
4. **Formalize the embedding cache-invalidation rule** as a docstring block on (or immediately above) `create_embeddings()`. The rule: the embedding model identity (`EMBEDDING_MODEL_NAME`) is the cache key for every per-domain index under `rag/domains/*`. If `EMBEDDING_MODEL_NAME` changes, every cached `.pkl` / serialized index under `data/cache/` (or wherever the loaders cache) is stale and must be deleted before next run. State this as a hard invariant in the docstring, not in prose anywhere else; cite the loader paths that depend on it (e.g., `rag/domains/mechanical.py`, `rag/domains/process.py`, etc.). This is documentation only — no code is added to invalidate caches automatically, because the rule is a contract for the developer changing the model name, not a runtime concern.
5. **Add unit tests** under `tests/unit/test_llms.py` (new if absent) that cover the retry wrapper with a fake transport:
   - A fake `_InvokableLlm` whose `ainvoke` raises a 429-shaped exception twice and succeeds on the third call → assert the wrapper returns the third call's result and made three attempts.
   - A fake whose `ainvoke` raises a 500-shaped exception twice and succeeds on the third → same assertion.
   - A fake whose `ainvoke` raises a 400-shaped exception once → assert the wrapper re-raises without retrying.
   - A fake whose `ainvoke` raises a 429 four times in a row → assert the wrapper exhausts retries and re-raises the last exception (the cap is enforced).
   - A test that confirms `create_synthesizer_llm()` constructs a `ChatOpenAI` with the chosen seed visible (either via constructor arg inspection or by patching the constructor and asserting kwargs). No live HTTP — patch `ChatOpenAI` or its transport so the test runs in CI without network.
   Tests must run deterministically (no real sleeps if backoff jitter is involved — patch `asyncio.sleep` or expose the sleep callable for injection).
6. **Verify locally**: `uv run pytest tests/unit/test_llms.py` green; `uv run pytest` green overall; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** ships the retry/backoff capability itself — the load-bearing resilience improvement for the live demo and the paid-synth rehearsal.
- **Step 2** wires it in without changing any caller, satisfying [architecture.md §5](../../architecture.md)'s rule that LLM-client concerns stay inside `agents/llms.py`. The semaphore-then-retry order keeps Phase 3's concurrency cap honest under retry pressure.
- **Step 3** is the deterministic-seed knob; small, additive, and explicitly best-effort so the docstring is honest about upstream-provider variance.
- **Step 4** turns a tribal-knowledge invariant into a documented contract at the cache key's source — the embedding model name. Future cache-related confusion lands at the right docstring.
- **Step 5** is the regression guard that proves the retry policy matches its spec without spending OpenRouter quota or flaking on the network.
- **Step 6** is the local quality gate.

## Code locations

- `src/expertview/agents/llms.py` (edit — add a retry/backoff wrapper class or helper next to `ThrottledInvestigatorLlm`; thread it through both factories; add `SYNTHESIZER_SEED` constant and pass it to the synthesizer `ChatOpenAI`; expand `create_embeddings`'s docstring with the cache-invalidation rule and the dependent loader paths).
- `tests/unit/test_llms.py` (new if absent — fake-transport tests for the retry policy and the seed propagation; no live HTTP, no real sleep).

## Connections

**Upstream**:

- `agents/llms.py` (Phase 1, iterated through Phase 3) — the existing `ChatOpenAI` factories and `ThrottledInvestigatorLlm` are the composition surface; this task edits the file, it does not rewrite it.
- `rag/domains/*.py` loaders (Phase 2–3) — name them in the cache-invalidation docstring as the dependents whose serialized indexes must be deleted when `EMBEDDING_MODEL_NAME` changes. This is a documentation reference only; no import.

**Downstream**:

- [[task-3-paid-synth-rehearsal-and-readme]] — the paid-synth swap depends on retry/backoff to survive transient OpenRouter responses and on the seed for reproducibility across the rehearsal runs.
- `agents/investigators/*` and `agents/synthesizer.py` consume the factory return types unchanged; the retry wrapper is invisible to them by design.
- The `Phase 7` quality-gate language about "retries on transient OpenRouter failures" in [build_plan.md](../../build_plan.md) is satisfied here.

## Parallelism rationale

- This task edits only `src/expertview/agents/llms.py` and adds `tests/unit/test_llms.py`. [[task-2-trace-export-and-replay]] edits export tooling and a new artifact path under `data/traces/`. No file overlap, no shared symbol churn.
- The retry wrapper is composed with `ThrottledInvestigatorLlm` *inside* `agents/llms.py` per [architecture.md §5](../../architecture.md)'s *"LLM provider clients are instantiated only in `agents/llms.py`"* rule. No downstream node import changes, so no downstream PR is blocked by this task.
- Tests use a fake transport — they consume no OpenRouter quota and run offline, so Task 1 can be developed and verified without coordinating with Task 2's trace-capture work.

## Risks / constraints / assumptions

- **Constraint**: LLM clients are constructed only in `agents/llms.py` ([CLAUDE.md architecture rules](../../../CLAUDE.md), [architecture.md §5](../../architecture.md)). The retry wrapper lives in the same module; it does not become a new top-level package.
- **Constraint**: prompts live as files under `src/expertview/prompts/` ([CLAUDE.md hard rules](../../../CLAUDE.md)). This task touches no prompt.
- **Constraint**: no new dependency in `pyproject.toml` ([CLAUDE.md hard rules](../../../CLAUDE.md)). The retry wrapper uses `asyncio.sleep` + standard exception handling; `langchain-openai`'s exception surface is the existing source of the 429/5xx signal. If the executing agent finds a case where a third-party retry library is unavoidable, that is a `decisions.md`-gated dependency change requiring user approval, not a silent add.
- **Constraint**: the existing `ThrottledInvestigatorLlm` semaphore stays in place; the composition order (semaphore → retry → ChatOpenAI) preserves Phase 3's concurrency cap. Swapping the order so retry sits outside the semaphore would let a retrying call hold no slot, defeating the cap; do not invert.
- **Risk — retry storm under sustained 429s**: a tight retry loop against a real rate limit can amplify the problem. Mitigation: low retry cap (3 attempts), exponential backoff with jitter, and honoring `Retry-After` when OpenRouter sends it. Document the cap in the wrapper's docstring so a future tuner sees the design choice.
- **Risk — exception-class fragility**: `langchain-openai`'s exception types around HTTP errors can shift between versions; matching on raw HTTP status codes is more robust than `isinstance` checks. Mitigation: read the status code off the exception (or from the underlying `httpx.HTTPStatusError` if available); fall through to a permissive catch-all only with a logged warning.
- **Risk — silent seed-ignored**: OpenRouter may route a synthesizer call to an upstream provider that does not honor the `seed` parameter, breaking the reproducibility goal without an error. Mitigation: the docstring on `SYNTHESIZER_SEED` calls this out explicitly so a reader knows the knob is best-effort; the reproducibility claim in the Task 3 README is also hedged.
- **Risk — non-deterministic tests via real `asyncio.sleep`**: backoff jitter would make tests flaky. Mitigation: inject the sleep callable (default `asyncio.sleep`) so tests can pass an instantaneous fake; or use `unittest.mock.patch("asyncio.sleep", AsyncMock())`. Either is fine; pick the pattern that reads cleanest.
- **Assumption**: OpenRouter's 5xx surface is genuinely transient (gateway timeouts, upstream availability). If a 5xx is in fact a permanent prompt-shape issue routed through 5xx by OpenRouter, retrying does nothing harmful — the cap exhausts and the original error surfaces. The retry policy does not need to discriminate further at this phase.
- **Assumption**: the cache-invalidation rule remains a *contract*, not an enforced check, in v1. If a future phase wants automatic invalidation, it adds it in `rag/domains/*` loaders consuming the model identity at startup; that is out of scope here.

## Definition of done

- `agents/llms.py` exports the existing `create_investigator_llm`, `create_synthesizer_llm`, and `create_embeddings` with unchanged call signatures, now backed by a retry/backoff wrapper around the `ChatOpenAI.ainvoke(...)` path. Investigator clients are wrapped semaphore-then-retry; synthesizer clients are wrapped retry-only.
- The retry policy: bounded (≤3 attempts), exponential backoff with jitter, honors `Retry-After`, retries on `429` + `5xx`, re-raises immediately on other `4xx`, re-raises the last exception on exhaustion.
- `agents/llms.py` defines `SYNTHESIZER_SEED` (or equivalent named constant) and passes it to the synthesizer `ChatOpenAI` constructor. The docstring on the constant notes that upstream providers may ignore the seed.
- `create_embeddings()` carries a docstring section documenting the embedding cache invalidation rule as a hard contract, citing the dependent loader paths under `rag/domains/*`.
- `tests/unit/test_llms.py` exists and passes with the cases from step 5 (429 retried then succeeds; 5xx retried then succeeds; 400 re-raises immediately; cap exhaustion re-raises; seed propagates to the synthesizer constructor). Tests are offline and deterministic.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/phase-7-llm-hardening` per [branching_strategy.md §5](../../branching_strategy.md). PR description:
  - Summarizes the retry policy (status codes, cap, base/ceiling, `Retry-After` handling) in two or three sentences.
  - Names the chosen seed value and notes the best-effort upstream caveat.
  - Quotes the cache-invalidation docstring lines verbatim and lists the loader paths cited.
  - Confirms no node under `agents/investigators/` or `agents/synthesizer.py` was edited.
