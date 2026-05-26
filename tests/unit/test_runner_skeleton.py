"""Smoke tests for the Phase 1 LangGraph runner skeleton."""

import os

from langgraph.graph.state import CompiledStateGraph
from pytest import MonkeyPatch

from expertview.orchestration import runner


def test_make_graph_returns_compiled_state_graph() -> None:
    compiled = runner.make_graph()

    assert isinstance(compiled, CompiledStateGraph)


def test_make_graph_compiles_without_provider_keys(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv(runner.LANGSMITH_API_KEY_ENV, raising=False)
    monkeypatch.delenv(runner.LANGSMITH_TRACING_ENV, raising=False)

    compiled = runner.make_graph()

    assert isinstance(compiled, CompiledStateGraph)
    assert runner.LANGSMITH_TRACING_ENV not in os.environ


def test_fake_langsmith_key_enables_tracing_without_network(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(runner.LANGSMITH_API_KEY_ENV, "fake-langsmith-key")
    monkeypatch.setenv(runner.LANGSMITH_PROJECT_ENV, " expertview-test ")
    monkeypatch.delenv(runner.LANGSMITH_TRACING_ENV, raising=False)

    compiled = runner.make_graph()

    assert isinstance(compiled, CompiledStateGraph)
    assert os.environ[runner.LANGSMITH_TRACING_ENV] == "true"
    assert os.environ[runner.LANGSMITH_PROJECT_ENV] == "expertview-test"
