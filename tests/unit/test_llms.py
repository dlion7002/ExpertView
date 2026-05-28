"""Unit tests for the LLM-client retry policy and seed propagation.

These tests cover the resilience surface added in Phase 7 Task 1:
- `RetryingLlm` retries `429`/`5xx` with bounded backoff, honors
  `Retry-After`, and re-raises non-retryable errors immediately.
- `create_synthesizer_llm` constructs `ChatOpenAI` with the deterministic
  `SYNTHESIZER_SEED`.
- `create_investigator_llm` composes the retry wrapper *inside* the
  semaphore wrapper so the concurrency cap is honored before the retry
  loop starts holding a slot.

All tests are offline — `ChatOpenAI` is patched at construction time and
`asyncio.sleep` is replaced with an instantaneous fake.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from expertview.agents import llms as llms_module
from expertview.agents.llms import (
    SYNTHESIZER_SEED,
    RetryingLlm,
    ThrottledInvestigatorLlm,
    create_investigator_llm,
    create_synthesizer_llm,
)


class _FakeResponse:
    def __init__(self, status_code: int, retry_after: str | None = None) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        if retry_after is not None:
            self.headers["Retry-After"] = retry_after


class _FakeHttpError(Exception):
    """Mimics the langchain-openai HTTP error surface enough for the wrapper.

    The wrapper probes ``status_code`` / ``response.status_code`` / ``code``
    in that order; this fake exposes ``status_code`` and ``response`` so
    both probe paths are exercised across the suite.
    """

    def __init__(self, status_code: int, retry_after: str | None = None) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.response = _FakeResponse(status_code, retry_after)


class _ScriptedLlm:
    """Fake `_InvokableLlm` that returns/raises scripted entries in order."""

    def __init__(self, *script: object) -> None:
        self._script = list(script)
        self.attempts = 0

    async def ainvoke(self, input: str) -> object:
        self.attempts += 1
        index = min(self.attempts - 1, len(self._script) - 1)
        entry = self._script[index]
        if isinstance(entry, BaseException):
            raise entry
        return entry


class _SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _wrapper(llm: _ScriptedLlm, sleep: _SleepRecorder | None = None) -> RetryingLlm:
    return RetryingLlm(
        llm,
        sleep=sleep or _SleepRecorder(),
        rng=random.Random(0),
    )


@pytest.mark.asyncio
async def test_retry_succeeds_after_two_429s() -> None:
    llm = _ScriptedLlm(_FakeHttpError(429), _FakeHttpError(429), "ok")
    sleep = _SleepRecorder()
    result = await _wrapper(llm, sleep).ainvoke("prompt")
    assert result == "ok"
    assert llm.attempts == 3
    assert len(sleep.delays) == 2


@pytest.mark.asyncio
async def test_retry_succeeds_after_two_500s() -> None:
    llm = _ScriptedLlm(_FakeHttpError(500), _FakeHttpError(503), "ok")
    sleep = _SleepRecorder()
    result = await _wrapper(llm, sleep).ainvoke("prompt")
    assert result == "ok"
    assert llm.attempts == 3
    assert len(sleep.delays) == 2


@pytest.mark.asyncio
async def test_retry_reraises_400_without_retrying() -> None:
    llm = _ScriptedLlm(_FakeHttpError(400), "should-not-reach")
    sleep = _SleepRecorder()
    with pytest.raises(_FakeHttpError) as info:
        await _wrapper(llm, sleep).ainvoke("prompt")
    assert info.value.status_code == 400
    assert llm.attempts == 1
    assert sleep.delays == []


@pytest.mark.asyncio
async def test_retry_exhausts_cap_on_persistent_429() -> None:
    llm = _ScriptedLlm(
        _FakeHttpError(429),
        _FakeHttpError(429),
        _FakeHttpError(429),
        _FakeHttpError(429),
    )
    sleep = _SleepRecorder()
    with pytest.raises(_FakeHttpError) as info:
        await _wrapper(llm, sleep).ainvoke("prompt")
    assert info.value.status_code == 429
    assert llm.attempts == 3
    assert len(sleep.delays) == 2


@pytest.mark.asyncio
async def test_retry_honors_retry_after_header() -> None:
    llm = _ScriptedLlm(_FakeHttpError(429, retry_after="0.5"), "ok")
    sleep = _SleepRecorder()
    result = await _wrapper(llm, sleep).ainvoke("prompt")
    assert result == "ok"
    assert sleep.delays == [0.5]


@pytest.mark.asyncio
async def test_retry_treats_unknown_exception_as_non_retryable() -> None:
    """Exception with no extractable status code is non-retryable.

    The wrapper logs a warning and re-raises on the first attempt rather
    than swallowing arbitrary errors into the retry loop.
    """
    llm = _ScriptedLlm(RuntimeError("boom"), "should-not-reach")
    sleep = _SleepRecorder()
    with pytest.raises(RuntimeError, match="boom"):
        await _wrapper(llm, sleep).ainvoke("prompt")
    assert llm.attempts == 1
    assert sleep.delays == []


def test_synthesizer_factory_passes_seed_to_chatopenai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        async def ainvoke(self, input: str) -> object:  # pragma: no cover
            return None

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("EXPERTVIEW_SYNTH_MODEL", "deepseek/test-model")
    monkeypatch.setattr(llms_module, "ChatOpenAI", _FakeChatOpenAI)

    wrapped = create_synthesizer_llm()

    assert isinstance(wrapped, RetryingLlm)
    assert captured.get("seed") == SYNTHESIZER_SEED
    assert captured.get("model") == "deepseek/test-model"
    assert captured.get("base_url") == llms_module.OPENROUTER_BASE_URL


def test_investigator_factory_composes_retry_inside_semaphore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        async def ainvoke(self, input: str) -> object:  # pragma: no cover
            return None

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(llms_module, "ChatOpenAI", _FakeChatOpenAI)

    wrapped = create_investigator_llm()

    assert isinstance(wrapped, ThrottledInvestigatorLlm)
    inner = wrapped._llm
    assert isinstance(inner, RetryingLlm)
    assert isinstance(inner._llm, _FakeChatOpenAI)
