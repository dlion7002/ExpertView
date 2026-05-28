"""Unit tests for the `expertview replay` subcommand.

Replay must:
- Re-render the captured `CausalReport` through the same `_render_report` the
  live demo uses.
- Print a clearly-labeled `(replay from <path>)` line so observers know the
  output is captured, not live.
- Make no LangSmith or OpenRouter HTTP calls.
- Fail loudly on malformed JSON or captured reports that fail validation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from rich.console import Console

from expertview import cli
from expertview.cli import _run_replay
from expertview.evidence.models import CausalReport, Symptom

_NOW = datetime(2026, 5, 28, 14, 30, 0, tzinfo=UTC)


def _causal_report_dict(*, with_symptom_effect: bool = False) -> dict[str, Any]:
    finding = {
        "investigator_domain": "mechanical",
        "claim": "Bearing chatter detected.",
        "confidence": 0.7,
        "citations": ["mech-doc-001"],
        "raised_at": _NOW.isoformat(),
    }
    hypothesis = {
        "id": "hyp-1",
        "claim": "Spindle bearing wear drove the out-of-tolerance bore.",
        "confidence": 0.81,
        "domain_origin": "mechanical",
        "supporting_findings": [finding],
    }
    causal_chain: list[dict[str, Any]] = []
    if with_symptom_effect:
        causal_chain.append(
            {
                "cause": hypothesis,
                "effect": {
                    "description": "Bore measurement out of tolerance.",
                    "observed_at": _NOW.isoformat(),
                },
                "strength": 0.85,
                "rationale": "Bearing chatter cascades into bore drift.",
            }
        )
    return {
        "incident_id": "incident_alpha",
        "top_hypotheses": [hypothesis],
        "causal_chain": causal_chain,
        "confidence_summary": "Mechanical wear is dominant.",
        "verdict_reasoning": "Bearing chatter explains the bore drift.",
        "alternatives_summary": "Vibration ruled out below threshold.",
        "generated_at": _NOW.isoformat(),
    }


def _write_artifact(
    tmp_path: Path,
    *,
    causal_report: dict[str, Any] | None,
    run_url: str | None = "https://smith.langchain.com/run-1",
    name: str = "trace.json",
) -> Path:
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "exported_at": _NOW.isoformat(),
        "langsmith": {
            "project": "expertview-tests",
            "run_id": "abc-123",
            "run_name": "LangGraph",
            "run_url": run_url,
            "start_time": _NOW.isoformat(),
            "end_time": _NOW.isoformat(),
            "status": "success",
            "error": None,
        },
        "synthesizer_model": "anthropic/claude-opus-4.7",
        "incident": {"id": "incident_alpha"},
        "causal_report": causal_report,
        "findings_by_domain": {},
        "child_run_summaries": [],
    }
    path = tmp_path / name
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


def _capture_replay_console(monkeypatch: pytest.MonkeyPatch) -> Console:
    recorder = Console(record=True, width=200, force_terminal=False, legacy_windows=False)
    monkeypatch.setattr(cli, "Console", lambda **_kwargs: recorder)
    return recorder


def test_replay_renders_report_sections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _capture_replay_console(monkeypatch)
    trace_path = _write_artifact(tmp_path, causal_report=_causal_report_dict())

    exit_code = _run_replay(trace_path)
    rendered = recorder.export_text()

    assert exit_code == 0
    assert "Spindle bearing wear" in rendered
    assert "Bearing chatter explains the bore drift" in rendered
    assert "Vibration ruled out below threshold" in rendered
    assert "mech-doc-001" in rendered
    assert f"(replay from {trace_path})" in rendered
    assert "captured run abc-123" in rendered
    assert "expertview-tests" in rendered
    assert "https://smith.langchain.com/run-1" in rendered


def test_replay_handles_symptom_effect_in_causal_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _capture_replay_console(monkeypatch)
    report_dict = _causal_report_dict(with_symptom_effect=True)
    trace_path = _write_artifact(tmp_path, causal_report=report_dict)

    # First sanity-check that pydantic resolves the union correctly.
    report = CausalReport.model_validate(report_dict)
    assert isinstance(report.causal_chain[0].effect, Symptom)

    exit_code = _run_replay(trace_path)
    rendered = recorder.export_text()

    assert exit_code == 0
    assert "Bore measurement out of tolerance" in rendered


def test_replay_omits_url_line_when_artifact_has_no_run_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _capture_replay_console(monkeypatch)
    trace_path = _write_artifact(tmp_path, causal_report=_causal_report_dict(), run_url=None)

    exit_code = _run_replay(trace_path)
    rendered = recorder.export_text()

    assert exit_code == 0
    assert f"(replay from {trace_path})" in rendered
    assert "Original LangSmith trace:" not in rendered


def test_replay_fails_on_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _capture_replay_console(monkeypatch)
    exit_code = _run_replay(tmp_path / "does-not-exist.json")
    assert exit_code == 1


def test_replay_fails_on_malformed_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _capture_replay_console(monkeypatch)
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")

    exit_code = _run_replay(bad)
    assert exit_code == 1


def test_replay_fails_on_missing_causal_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture_replay_console(monkeypatch)
    trace_path = _write_artifact(tmp_path, causal_report=None)

    exit_code = _run_replay(trace_path)
    assert exit_code == 1


def test_replay_fails_on_invalid_causal_report_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture_replay_console(monkeypatch)
    # Missing required `incident_id` and `confidence_summary` fields.
    bad_report = {"top_hypotheses": []}
    trace_path = _write_artifact(tmp_path, causal_report=bad_report)

    exit_code = _run_replay(trace_path)
    assert exit_code == 1


def test_replay_does_not_call_langsmith_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture_replay_console(monkeypatch)
    trace_path = _write_artifact(tmp_path, causal_report=_causal_report_dict())

    def _explode(*_a: object, **_k: object) -> None:
        raise AssertionError("Replay must not construct LangSmithClient")

    with patch.object(cli, "LangSmithClient", side_effect=_explode):
        exit_code = _run_replay(trace_path)

    assert exit_code == 0
