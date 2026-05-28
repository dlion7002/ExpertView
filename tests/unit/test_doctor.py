"""Unit tests for the `expertview doctor` pre-flight subcommand.

Every check is exercised against fakes — no live HTTP, no real
`sentence-transformers` download, no LangSmith network call. Tests
monkeypatch the symbols `_run_doctor` resolves at call time so the
production wiring stays under test without paying the cost.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from expertview import cli
from expertview.cli import (
    _DOCTOR_FAIL,
    _DOCTOR_INFO,
    _DOCTOR_PASS,
    _DOCTOR_SKIP,
    _run_doctor,
)
from expertview.orchestration.runner import LANGSMITH_API_KEY_ENV


class _FakeEmbeddings:
    def embed_query(self, _text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class _FakeLangSmithClient:
    def list_projects(self, *, limit: int = 1) -> list[Any]:
        assert limit == 1
        return [object()]


def _set_full_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    monkeypatch.setenv(LANGSMITH_API_KEY_ENV, "ls-test-key")
    monkeypatch.delenv("EXPERTVIEW_SYNTH_MODEL", raising=False)


def _wire_happy_doctor(monkeypatch: MonkeyPatch) -> None:
    """Wire fakes for the embedding + LangSmith checks. Incident YAMLs and
    Streamlit imports run against the real repo state (both are present)."""
    monkeypatch.setattr(cli, "create_embeddings", lambda: _FakeEmbeddings())
    monkeypatch.setattr(cli, "LangSmithClient", lambda: _FakeLangSmithClient())


def _statuses_by_name(captured: dict[str, list[tuple[str, str, str]]]) -> dict[str, str]:
    return {name: status for name, status, _detail in captured["rows"]}


def _capture_doctor_rows(monkeypatch: MonkeyPatch) -> dict[str, list[tuple[str, str, str]]]:
    """Wrap `Table.add_row` so the test can read back each row's status without
    parsing rich's rendered output."""
    captured: dict[str, list[tuple[str, str, str]]] = {"rows": []}

    real_add_row = cli.Table.add_row

    def add_row(self: cli.Table, *cells: Any, **kwargs: Any) -> None:
        name = str(cells[0]) if cells else ""
        status_text = cells[1]
        detail = str(cells[2]) if len(cells) > 2 else ""
        status = (
            status_text.plain.strip().lower()
            if hasattr(status_text, "plain")
            else str(status_text).strip().lower()
        )
        captured["rows"].append((name, status, detail))
        real_add_row(self, *cells, **kwargs)

    monkeypatch.setattr(cli.Table, "add_row", add_row)
    return captured


def test_doctor_passes_with_full_environment(monkeypatch: MonkeyPatch) -> None:
    _set_full_env(monkeypatch)
    _wire_happy_doctor(monkeypatch)
    captured = _capture_doctor_rows(monkeypatch)

    exit_code = _run_doctor(skip_embedding=False, skip_langsmith=False)

    assert exit_code == 0
    statuses = _statuses_by_name(captured)
    fail_rows = [name for name, status in statuses.items() if status == _DOCTOR_FAIL]
    assert fail_rows == [], f"expected no failures, got {fail_rows}"
    assert any(status == _DOCTOR_PASS for status in statuses.values())
    assert any(status == _DOCTOR_INFO for status in statuses.values()), (
        "synth model row should be informational"
    )


def test_doctor_fails_without_openrouter_key(monkeypatch: MonkeyPatch) -> None:
    _set_full_env(monkeypatch)
    _wire_happy_doctor(monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    captured = _capture_doctor_rows(monkeypatch)

    exit_code = _run_doctor(skip_embedding=False, skip_langsmith=False)

    assert exit_code == 1
    statuses = _statuses_by_name(captured)
    assert statuses["OPENROUTER_API_KEY set"] == _DOCTOR_FAIL
    assert statuses[f"{LANGSMITH_API_KEY_ENV} set"] == _DOCTOR_PASS


def test_doctor_fails_without_langsmith_key_but_keeps_other_rows_passing(
    monkeypatch: MonkeyPatch,
) -> None:
    _set_full_env(monkeypatch)
    _wire_happy_doctor(monkeypatch)
    monkeypatch.delenv(LANGSMITH_API_KEY_ENV, raising=False)
    captured = _capture_doctor_rows(monkeypatch)

    exit_code = _run_doctor(skip_embedding=False, skip_langsmith=False)

    assert exit_code == 1
    statuses = _statuses_by_name(captured)
    assert statuses[f"{LANGSMITH_API_KEY_ENV} set"] == _DOCTOR_FAIL
    assert statuses["OPENROUTER_API_KEY set"] == _DOCTOR_PASS
    assert statuses["Incident YAMLs parse"] == _DOCTOR_PASS
    assert statuses["Streamlit deps import"] == _DOCTOR_PASS
    assert statuses["Trace subcommands present"] == _DOCTOR_PASS


def test_doctor_reports_missing_incident_yaml(monkeypatch: MonkeyPatch) -> None:
    _set_full_env(monkeypatch)
    _wire_happy_doctor(monkeypatch)
    monkeypatch.setattr(
        cli,
        "_DOCTOR_INCIDENT_PATHS",
        (Path("data/incidents/does_not_exist.yaml"),),
    )
    captured = _capture_doctor_rows(monkeypatch)

    exit_code = _run_doctor(skip_embedding=False, skip_langsmith=False)

    assert exit_code == 1
    statuses = _statuses_by_name(captured)
    assert statuses["Incident YAMLs parse"] == _DOCTOR_FAIL
    incident_detail = next(
        detail for name, _status, detail in captured["rows"] if name == "Incident YAMLs parse"
    )
    assert "does_not_exist.yaml" in incident_detail
    assert "FileNotFoundError" in incident_detail


def test_doctor_skips_embedding_when_flag_set(monkeypatch: MonkeyPatch) -> None:
    _set_full_env(monkeypatch)
    _wire_happy_doctor(monkeypatch)

    embed_calls = {"count": 0}

    def boom() -> _FakeEmbeddings:
        embed_calls["count"] += 1
        raise AssertionError("embedding factory should not be called when skipped")

    monkeypatch.setattr(cli, "create_embeddings", boom)
    captured = _capture_doctor_rows(monkeypatch)

    exit_code = _run_doctor(skip_embedding=True, skip_langsmith=False)

    assert exit_code == 0
    statuses = _statuses_by_name(captured)
    assert statuses["Embedding round-trip"] == _DOCTOR_SKIP
    assert embed_calls["count"] == 0


def test_doctor_skips_langsmith_when_flag_set(monkeypatch: MonkeyPatch) -> None:
    _set_full_env(monkeypatch)
    _wire_happy_doctor(monkeypatch)

    client_calls = {"count": 0}

    def boom() -> _FakeLangSmithClient:
        client_calls["count"] += 1
        raise AssertionError("LangSmithClient should not be constructed when skipped")

    monkeypatch.setattr(cli, "LangSmithClient", boom)
    captured = _capture_doctor_rows(monkeypatch)

    exit_code = _run_doctor(skip_embedding=False, skip_langsmith=True)

    assert exit_code == 0
    statuses = _statuses_by_name(captured)
    assert statuses["LangSmith connectivity"] == _DOCTOR_SKIP
    assert client_calls["count"] == 0


def test_doctor_detects_missing_trace_subcommands(monkeypatch: MonkeyPatch) -> None:
    _set_full_env(monkeypatch)
    _wire_happy_doctor(monkeypatch)

    def stripped_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="expertview")
        subparsers = parser.add_subparsers(dest="command", required=True)
        subparsers.add_parser("demo")
        return parser

    monkeypatch.setattr(cli, "_build_parser", stripped_parser)
    captured = _capture_doctor_rows(monkeypatch)

    exit_code = _run_doctor(skip_embedding=False, skip_langsmith=False)

    assert exit_code == 1
    statuses = _statuses_by_name(captured)
    assert statuses["Trace subcommands present"] == _DOCTOR_FAIL
    trace_detail = next(
        detail for name, _status, detail in captured["rows"] if name == "Trace subcommands present"
    )
    assert "trace-export" in trace_detail
    assert "replay" in trace_detail


def test_doctor_reports_embedding_failure_with_exception_class(monkeypatch: MonkeyPatch) -> None:
    _set_full_env(monkeypatch)
    _wire_happy_doctor(monkeypatch)

    class _ExplodingEmbeddings:
        def embed_query(self, _text: str) -> list[float]:
            raise RuntimeError("model not downloaded")

    monkeypatch.setattr(cli, "create_embeddings", lambda: _ExplodingEmbeddings())
    captured = _capture_doctor_rows(monkeypatch)

    exit_code = _run_doctor(skip_embedding=False, skip_langsmith=False)

    assert exit_code == 1
    detail = next(
        detail for name, _status, detail in captured["rows"] if name == "Embedding round-trip"
    )
    assert "RuntimeError" in detail
    assert "model not downloaded" in detail
