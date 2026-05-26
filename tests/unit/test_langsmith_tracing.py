"""Unit tests for the LangSmith tracing helper.

Phase 2's ``make_graph()`` eagerly constructs LLM clients and the mechanical
RAG store, so it is no longer reachable in a unit-test environment without
provider keys or the embedding model loaded. The valuable assertion from
the Phase 1 skeleton suite — that ``_configure_langsmith_tracing()`` is a
no-op without keys and activates tracing with them — is preserved here by
testing the helper directly.
"""

import os

from pytest import MonkeyPatch

from expertview.orchestration import runner


def test_configure_langsmith_tracing_is_noop_without_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv(runner.LANGSMITH_API_KEY_ENV, raising=False)
    monkeypatch.delenv(runner.LANGSMITH_TRACING_ENV, raising=False)

    runner._configure_langsmith_tracing()

    assert runner.LANGSMITH_TRACING_ENV not in os.environ


def test_configure_langsmith_tracing_is_noop_with_blank_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(runner.LANGSMITH_API_KEY_ENV, "   ")
    monkeypatch.delenv(runner.LANGSMITH_TRACING_ENV, raising=False)

    runner._configure_langsmith_tracing()

    assert runner.LANGSMITH_TRACING_ENV not in os.environ


def test_configure_langsmith_tracing_activates_with_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(runner.LANGSMITH_API_KEY_ENV, "fake-langsmith-key")
    monkeypatch.setenv(runner.LANGSMITH_PROJECT_ENV, " expertview-test ")
    monkeypatch.delenv(runner.LANGSMITH_TRACING_ENV, raising=False)

    runner._configure_langsmith_tracing()

    assert os.environ[runner.LANGSMITH_TRACING_ENV] == "true"
    assert os.environ[runner.LANGSMITH_PROJECT_ENV] == "expertview-test"


def test_configure_langsmith_tracing_preserves_explicit_tracing_value(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv(runner.LANGSMITH_API_KEY_ENV, "fake-langsmith-key")
    monkeypatch.setenv(runner.LANGSMITH_TRACING_ENV, "false")

    runner._configure_langsmith_tracing()

    assert os.environ[runner.LANGSMITH_TRACING_ENV] == "false"
