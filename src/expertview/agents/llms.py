"""Provider factory for ExpertView LLM and embedding clients.

This module is the only legal construction site for LLM provider clients.
Callers are responsible for loading environment variables before calling
these constructors; this module reads `os.environ` directly and never loads
`.env` files (`tests/conftest.py` is the sanctioned test-process loader).

LLMs are routed through OpenRouter via the OpenAI-compatible API surface,
so every model (free open-weight for build, paid frontier for demo) is
reachable through a single `ChatOpenAI` client and a single
`OPENROUTER_API_KEY`. Investigators run on `openrouter/owl-alpha` (free,
1M context, agentic). The synthesizer model is selectable at runtime via
`EXPERTVIEW_SYNTH_MODEL`, holding an OpenRouter model ID directly
(default `deepseek/deepseek-v4-flash:free` for build,
`anthropic/claude-opus-4.7` or similar at demo time).

Embeddings run locally via `sentence-transformers` (`BAAI/bge-small-en-v1.5`)
to keep the OpenRouter credit unspent and to remove the network dependency
from RAG ingest.

Resilience: every `ChatOpenAI` returned by these factories is wrapped in a
`RetryingLlm` that retries OpenRouter `429` rate limits and transient `5xx`
upstream errors with bounded exponential backoff + jitter. The investigator
factory composes the retry wrapper *inside* `ThrottledInvestigatorLlm`, so
the semaphore still gates entry before the retry loop holds a slot.
"""

import asyncio
import email.utils
import logging
import os
import random
from collections.abc import Awaitable, Callable
from typing import Final, Protocol

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY_ENV: Final = "OPENROUTER_API_KEY"
SYNTHESIZER_MODEL_ENV: Final = "EXPERTVIEW_SYNTH_MODEL"

OPENROUTER_BASE_URL: Final = "https://openrouter.ai/api/v1"

INVESTIGATOR_MODEL_ID: Final = "openrouter/owl-alpha"
DEFAULT_SYNTHESIZER_MODEL_ID: Final = "deepseek/deepseek-v4-flash:free"

EMBEDDING_MODEL_NAME: Final = "BAAI/bge-small-en-v1.5"

# Deterministic seed for the synthesizer client. ChatOpenAI forwards `seed`
# to OpenRouter, which forwards it to whichever upstream provider it routes
# to. The knob is best-effort: upstreams (OpenAI, DeepSeek, Anthropic-via-OR)
# may ignore the seed, and routing may shift between calls. The goal is
# reproducibility when the upstream honors it, not a hard guarantee.
SYNTHESIZER_SEED: Final = 17

# Retry policy for OpenRouter calls. Bounded by design — a tight loop against
# a real rate limit would amplify the problem. Honor `Retry-After` when set.
RETRY_MAX_ATTEMPTS: Final = 3
RETRY_BASE_SECONDS: Final = 1.0
RETRY_MAX_SECONDS: Final = 8.0
RETRY_MULTIPLIER: Final = 2.0

# The cap of 5 deliberately matches the dispatcher's fan-out width: all five
# investigator branches can dispatch in parallel, but Phase 4's spawned
# sub-investigations will queue rather than amplifying OpenRouter free-tier
# rate-limit pressure.
INVESTIGATOR_CONCURRENCY: Final = 5
_INVESTIGATOR_SEMAPHORE = asyncio.Semaphore(INVESTIGATOR_CONCURRENCY)


class _InvokableLlm(Protocol):
    async def ainvoke(self, input: str) -> object: ...


SleepFn = Callable[[float], Awaitable[None]]


def _extract_status_code(exc: BaseException) -> int | None:
    """Best-effort HTTP status extraction from an LLM-client exception.

    Matching on raw status codes is more robust than `isinstance` checks
    against ``langchain-openai`` / ``openai`` exception hierarchies, which
    have shifted between SDK versions. Probe the common attribute names
    and return ``None`` if none of them yields an int — callers treat
    ``None`` as non-retryable.
    """
    for attr in ("status_code", "http_status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status
    return None


def _extract_retry_after_seconds(exc: BaseException) -> float | None:
    """Parse a `Retry-After` header off the exception's response, if any.

    Accepts integer/float seconds or HTTP-date format. Returns ``None``
    when the header is absent or unparseable; callers fall back to the
    computed backoff.
    """
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("Retry-After") if hasattr(headers, "get") else None
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(str(raw))
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    import datetime as _dt

    now = _dt.datetime.now(tz=parsed.tzinfo) if parsed.tzinfo else _dt.datetime.utcnow()
    delta = (parsed - now).total_seconds()
    return max(delta, 0.0)


def _is_retryable_status(status: int | None) -> bool:
    if status is None:
        return False
    if status == 429:
        return True
    return 500 <= status < 600


def _compute_backoff(attempt: int, rng: random.Random) -> float:
    """Exponential backoff with full jitter, capped at ``RETRY_MAX_SECONDS``.

    ``attempt`` is the 1-based index of the *upcoming* sleep (so attempt 1
    is the wait between try 1 and try 2). Full jitter avoids retry storms
    where every client wakes up in lockstep.
    """
    raw = RETRY_BASE_SECONDS * (RETRY_MULTIPLIER ** (attempt - 1))
    capped = min(raw, RETRY_MAX_SECONDS)
    return capped * rng.uniform(0.5, 1.0)


class RetryingLlm:
    """Async wrapper that retries OpenRouter `429` and transient `5xx` errors.

    Retries up to ``RETRY_MAX_ATTEMPTS`` total (initial call + retries),
    with exponential backoff (base ``RETRY_BASE_SECONDS``, multiplier
    ``RETRY_MULTIPLIER``, ceiling ``RETRY_MAX_SECONDS``) and full jitter.
    Honors a `Retry-After` header on the failing response when present.

    Any non-retryable error (including `4xx` other than `429`) is re-raised
    on the first attempt with traceback intact, so the CLI's existing error
    surface still sees deterministic prompt/auth failures immediately.

    The wrapper does not introduce a new dependency; it composes with the
    existing ``ThrottledInvestigatorLlm`` semaphore wrapper. The intended
    composition is semaphore-outside, retry-inside, so the concurrency cap
    is honored before a retry loop starts holding a slot.
    """

    def __init__(
        self,
        llm: _InvokableLlm,
        *,
        max_attempts: int = RETRY_MAX_ATTEMPTS,
        sleep: SleepFn = asyncio.sleep,
        rng: random.Random | None = None,
    ) -> None:
        self._llm = llm
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._rng = rng or random.Random()

    async def ainvoke(self, input: str) -> object:
        last_exc: BaseException | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await self._llm.ainvoke(input)
            except Exception as exc:
                status = _extract_status_code(exc)
                if not _is_retryable_status(status):
                    if status is None:
                        logger.warning(
                            "RetryingLlm: non-retryable exception with no extractable "
                            "HTTP status (%s); re-raising.",
                            type(exc).__name__,
                        )
                    raise
                last_exc = exc
                if attempt >= self._max_attempts:
                    break
                retry_after = _extract_retry_after_seconds(exc)
                delay = (
                    retry_after if retry_after is not None else _compute_backoff(attempt, self._rng)
                )
                logger.info(
                    "RetryingLlm: status %s on attempt %d/%d; sleeping %.2fs.",
                    status,
                    attempt,
                    self._max_attempts,
                    delay,
                )
                await self._sleep(delay)
        assert last_exc is not None
        raise last_exc


class ThrottledInvestigatorLlm:
    """Async wrapper that gates investigator calls through a shared semaphore.

    Investigator nodes accept any object satisfying their ``InvestigatorLlm``
    protocol (``async def ainvoke(self, input: str) -> object``). Wrapping the
    real ``ChatOpenAI`` here keeps the throttle invisible to the orchestration
    layer and satisfies the architecture rule that LLM-client concerns live
    only in ``agents/llms.py``.
    """

    def __init__(self, llm: _InvokableLlm, semaphore: asyncio.Semaphore) -> None:
        self._llm = llm
        self._semaphore = semaphore

    async def ainvoke(self, input: str) -> object:
        async with self._semaphore:
            return await self._llm.ainvoke(input)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"{name} is required to construct this provider client.")
    return value


def _selected_synthesizer_model() -> str:
    selected = os.environ.get(SYNTHESIZER_MODEL_ENV, DEFAULT_SYNTHESIZER_MODEL_ID).strip()
    if not selected:
        raise ValueError(f"{SYNTHESIZER_MODEL_ENV} must be a non-empty OpenRouter model ID.")
    return selected


def create_investigator_llm(
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> ThrottledInvestigatorLlm:
    llm = ChatOpenAI(
        model=INVESTIGATOR_MODEL_ID,
        base_url=OPENROUTER_BASE_URL,
        api_key=_required_env(OPENROUTER_API_KEY_ENV),
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return ThrottledInvestigatorLlm(RetryingLlm(llm), _INVESTIGATOR_SEMAPHORE)


def create_synthesizer_llm(
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> RetryingLlm:
    llm = ChatOpenAI(
        model=_selected_synthesizer_model(),
        base_url=OPENROUTER_BASE_URL,
        api_key=_required_env(OPENROUTER_API_KEY_ENV),
        temperature=temperature,
        max_tokens=max_tokens,
        seed=SYNTHESIZER_SEED,
    )
    return RetryingLlm(llm)


def create_embeddings() -> HuggingFaceEmbeddings:
    """Construct the local sentence-transformers embedding client.

    **Embedding cache invalidation rule (hard contract).**
    ``EMBEDDING_MODEL_NAME`` is the cache key for every per-domain index
    under ``src/expertview/rag/domains/`` — specifically
    ``mechanical.py``, ``process.py``, ``supply_chain.py``,
    ``environmental.py``, and ``human_factors.py``. Each loader serializes
    its embedded corpus under ``.cache/rag/<domain>/`` keyed by the corpus
    manifest hash and the embedding signature derived from this constant.

    If ``EMBEDDING_MODEL_NAME`` changes, every cached pickle / serialized
    index under ``.cache/rag/`` is stale and **must** be deleted before
    the next run. This is a developer-time contract enforced by convention,
    not a runtime check — the loaders compute the cache key off the current
    model identity but do not delete prior entries on mismatch. The intent
    is to keep the cache invariant visible at the cache key's source
    (this constant) rather than scattered across loader docstrings.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        encode_kwargs={"normalize_embeddings": True},
    )
