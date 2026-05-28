"""Unit tests for the `expertview trace-export` subcommand.

The export path is exercised against a fake `LangSmithClient` patched into
`expertview.cli.LangSmithClient` — no live HTTP, no live LangSmith project.
All run shapes are hand-crafted to mirror what `langsmith.Client.read_run`
and `Client.list_runs` actually return.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from pytest import MonkeyPatch

from expertview import cli
from expertview.cli import (
    TRACE_ARTIFACT_SCHEMA_VERSION,
    _build_artifact,
    _extract_causal_report,
    _redact_or_raise,
    _run_trace_export,
)
from expertview.evidence.models import CausalReport
from expertview.orchestration.runner import (
    LANGSMITH_API_KEY_ENV,
    LANGSMITH_PROJECT_ENV,
    MECHANICAL_NODE,
    PROCESS_NODE,
)

_RUN_ID = UUID("12345678-1234-5678-1234-567812345678")
_NOW = datetime(2026, 5, 28, 14, 30, 0, tzinfo=UTC)


class _FakeChildRun:
    def __init__(
        self,
        *,
        name: str,
        outputs: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        run_type: str = "chain",
        status: str = "success",
        error: str | None = None,
    ) -> None:
        self.name = name
        self.outputs = outputs
        self.inputs = inputs
        self.run_type = run_type
        self.status = status
        self.error = error
        self.start_time = _NOW
        self.end_time = _NOW + timedelta(seconds=5)


class _FakeRun:
    def __init__(
        self,
        *,
        run_id: UUID = _RUN_ID,
        outputs: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        child_runs: list[_FakeChildRun] | None = None,
        extra: dict[str, Any] | None = None,
        url: str | None = "https://smith.langchain.com/o/x/projects/p/r/run-1",
        error: str | None = None,
    ) -> None:
        self.id = run_id
        self.name = "LangGraph"
        self.run_type = "chain"
        self.inputs = inputs or {}
        self.outputs = outputs or {}
        self.child_runs = child_runs or []
        self.start_time = _NOW
        self.end_time = _NOW + timedelta(seconds=30)
        self.status = "success"
        self.error = error
        self.url = url
        # extra is intentionally accessible but should NEVER appear in the
        # exported artifact — the allow-list assembly skips it.
        self.extra = extra or {"invocation_params": {"openai_api_key": "sk-LEAK"}}


def _incident_dict() -> dict[str, Any]:
    return {
        "id": "incident_alpha",
        "summary": "Test incident.",
        "observed_at": _NOW.isoformat(),
        "symptoms": ["symptom-a"],
        "affected_assets": ["asset-1"],
    }


def _causal_report_dict() -> dict[str, Any]:
    return {
        "incident_id": "incident_alpha",
        "top_hypotheses": [
            {
                "id": "hyp-1",
                "claim": "Spindle bearing wear drove the out-of-tolerance bore.",
                "confidence": 0.81,
                "domain_origin": "mechanical",
                "supporting_findings": [
                    {
                        "investigator_domain": "mechanical",
                        "claim": "Bearing chatter detected.",
                        "confidence": 0.7,
                        "citations": ["mech-doc-001"],
                        "raised_at": _NOW.isoformat(),
                    }
                ],
            }
        ],
        "causal_chain": [],
        "confidence_summary": "Mechanical wear is dominant.",
        "verdict_reasoning": "Bearing chatter explains the bore drift.",
        "alternatives_summary": "Vibration ruled out below threshold.",
        "generated_at": _NOW.isoformat(),
    }


def _mech_child() -> _FakeChildRun:
    return _FakeChildRun(
        name=MECHANICAL_NODE,
        inputs={"prompt": "DO NOT EXPORT ME"},
        outputs={
            "findings": [
                {
                    "investigator_domain": "mechanical",
                    "claim": "Bearing chatter detected.",
                    "confidence": 0.7,
                    "citations": ["mech-doc-001"],
                    "raised_at": _NOW.isoformat(),
                }
            ]
        },
    )


def _process_child() -> _FakeChildRun:
    return _FakeChildRun(
        name=PROCESS_NODE,
        inputs={"prompt": "DO NOT EXPORT ME"},
        outputs={
            "findings": [
                {
                    "investigator_domain": "process",
                    "claim": "Spike in throughput.",
                    "confidence": 0.55,
                    "citations": ["proc-doc-002"],
                    "raised_at": _NOW.isoformat(),
                }
            ]
        },
    )


def _make_run() -> _FakeRun:
    return _FakeRun(
        inputs={"incident": _incident_dict()},
        outputs={"causal_report": _causal_report_dict()},
        child_runs=[_mech_child(), _process_child()],
    )


def test_export_writes_artifact_with_known_shape(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(LANGSMITH_API_KEY_ENV, "fake-key")
    monkeypatch.setenv(LANGSMITH_PROJECT_ENV, "expertview-tests")
    monkeypatch.setenv("EXPERTVIEW_SYNTH_MODEL", "anthropic/claude-opus-4.7")

    out_path = tmp_path / "trace.json"
    run = _make_run()
    client_instance = _FakeClient(read_run_return=run)

    with patch.object(cli, "LangSmithClient", return_value=client_instance):
        exit_code = _run_trace_export(run_id=str(_RUN_ID), out_path=out_path)

    assert exit_code == 0
    assert out_path.exists()

    artifact = json.loads(out_path.read_text(encoding="utf-8"))
    assert artifact["schema_version"] == TRACE_ARTIFACT_SCHEMA_VERSION
    assert set(artifact.keys()) == {
        "schema_version",
        "exported_at",
        "langsmith",
        "synthesizer_model",
        "incident",
        "causal_report",
        "findings_by_domain",
        "child_run_summaries",
    }
    assert artifact["langsmith"]["project"] == "expertview-tests"
    assert artifact["langsmith"]["run_id"] == str(_RUN_ID)
    assert artifact["langsmith"]["run_url"].endswith("/run-1")
    assert artifact["synthesizer_model"] == "anthropic/claude-opus-4.7"
    assert artifact["incident"]["id"] == "incident_alpha"
    assert artifact["causal_report"]["incident_id"] == "incident_alpha"
    assert MECHANICAL_NODE in artifact["findings_by_domain"]
    assert artifact["findings_by_domain"][MECHANICAL_NODE][0]["citations"] == ["mech-doc-001"]
    assert len(artifact["child_run_summaries"]) == 2
    # The leak-vector key must never have surfaced.
    serialized = json.dumps(artifact)
    assert "openai_api_key" not in serialized
    assert "sk-LEAK" not in serialized
    assert "DO NOT EXPORT ME" not in serialized


def test_export_round_trip_reconstructs_causal_report(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv(LANGSMITH_API_KEY_ENV, "fake-key")
    monkeypatch.setenv(LANGSMITH_PROJECT_ENV, "expertview-tests")

    out_path = tmp_path / "trace.json"
    client_instance = _FakeClient(read_run_return=_make_run())

    with patch.object(cli, "LangSmithClient", return_value=client_instance):
        exit_code = _run_trace_export(run_id=str(_RUN_ID), out_path=out_path)

    assert exit_code == 0
    artifact = json.loads(out_path.read_text(encoding="utf-8"))
    report = CausalReport.model_validate(artifact["causal_report"])
    assert report.incident_id == "incident_alpha"
    assert report.top_hypotheses[0].claim.startswith("Spindle bearing wear")


def test_export_auto_resolves_latest_run(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(LANGSMITH_API_KEY_ENV, "fake-key")
    monkeypatch.setenv(LANGSMITH_PROJECT_ENV, "expertview-tests")

    older = _FakeRun(run_id=uuid4())
    older.start_time = _NOW - timedelta(hours=2)
    newer = _FakeRun(
        run_id=uuid4(),
        inputs={"incident": _incident_dict()},
        outputs={"causal_report": _causal_report_dict()},
        child_runs=[_mech_child()],
    )
    newer.start_time = _NOW - timedelta(minutes=10)

    client_instance = _FakeClient(
        read_run_return=newer,
        list_runs_return=[older, newer],
    )

    out_path = tmp_path / "trace.json"
    with patch.object(cli, "LangSmithClient", return_value=client_instance):
        exit_code = _run_trace_export(run_id=None, out_path=out_path)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert str(newer.id) in captured.err
    # And read_run was called with the newer id.
    assert client_instance.last_read_run_id == newer.id


def test_export_fails_when_no_runs_found(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(LANGSMITH_API_KEY_ENV, "fake-key")
    monkeypatch.setenv(LANGSMITH_PROJECT_ENV, "empty-project")

    client_instance = _FakeClient(read_run_return=_make_run(), list_runs_return=[])
    out_path = tmp_path / "trace.json"

    with patch.object(cli, "LangSmithClient", return_value=client_instance):
        exit_code = _run_trace_export(run_id=None, out_path=out_path)

    assert exit_code == 1
    assert not out_path.exists()


def test_export_fails_without_langsmith_api_key(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv(LANGSMITH_API_KEY_ENV, raising=False)

    sentinel_calls: list[int] = []

    def _explode(*_a: object, **_k: object) -> None:
        sentinel_calls.append(1)
        raise AssertionError("LangSmithClient must not be constructed without a key")

    with patch.object(cli, "LangSmithClient", side_effect=_explode):
        exit_code = _run_trace_export(run_id=str(_RUN_ID), out_path=tmp_path / "x.json")

    assert exit_code == 1
    assert sentinel_calls == []


def test_export_rejects_invalid_run_id(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(LANGSMITH_API_KEY_ENV, "fake-key")
    monkeypatch.setenv(LANGSMITH_PROJECT_ENV, "expertview-tests")

    with patch.object(cli, "LangSmithClient", return_value=_FakeClient(_make_run())):
        exit_code = _run_trace_export(run_id="not-a-uuid", out_path=tmp_path / "x.json")

    assert exit_code == 1


def test_redactor_raises_on_secret_key() -> None:
    with pytest.raises(RuntimeError, match="api_key"):
        _redact_or_raise({"langsmith": {"api_key": "sk-EXPOSED"}})

    with pytest.raises(RuntimeError, match=r"(?i)authorization"):
        _redact_or_raise({"headers": [{"Authorization": "Bearer x"}]})


def test_redactor_passes_on_clean_artifact() -> None:
    _redact_or_raise(
        {
            "schema_version": 1,
            "langsmith": {"project": "p", "run_id": "uuid"},
            "causal_report": {"top_hypotheses": [{"claim": "x"}]},
        }
    )


def test_extract_causal_report_handles_both_outputs_shapes() -> None:
    nested = {"causal_report": _causal_report_dict()}
    bare = _causal_report_dict()

    assert _extract_causal_report(nested) == _causal_report_dict()
    assert _extract_causal_report(bare) == _causal_report_dict()
    assert _extract_causal_report(None) is None
    assert _extract_causal_report({"other_key": "value"}) is None


def test_build_artifact_omits_run_extra_and_child_inputs() -> None:
    run = _make_run()
    artifact = _build_artifact(run, project="p")
    # Smoke-check no allow-list expansion has crept in.
    assert "extra" not in artifact
    assert "extra" not in artifact["langsmith"]
    for summary in artifact["child_run_summaries"]:
        assert "inputs" not in summary
        assert "outputs" not in summary


class _FakeClient:
    """Minimal `LangSmithClient` stand-in exposing `read_run` + `list_runs`."""

    def __init__(
        self,
        read_run_return: object,
        list_runs_return: list[object] | None = None,
    ) -> None:
        self._read_run_return = read_run_return
        self._list_runs_return = list_runs_return or []
        self.last_read_run_id: UUID | None = None
        self.list_runs_calls: list[dict[str, Any]] = []

    def read_run(self, run_id: UUID, load_child_runs: bool = False) -> object:
        self.last_read_run_id = run_id
        _ = load_child_runs
        return self._read_run_return

    def list_runs(self, **kwargs: Any) -> list[object]:
        self.list_runs_calls.append(kwargs)
        return list(self._list_runs_return)
