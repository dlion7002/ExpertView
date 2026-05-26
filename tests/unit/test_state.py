"""ExpertViewState smoke + reducer behavior tests.

The reducer assertions guard against the silent-overwrite failure mode the
architecture's `operator.add` annotation is meant to prevent: if a future
edit drops the reducer, the 5-way Phase 3 investigator fan-out would
last-writer-win instead of merging. These tests fail immediately if that
annotation goes missing.
"""

import operator
from datetime import UTC, datetime
from typing import get_type_hints

from expertview.evidence.models import CausalReport, Finding, Incident
from expertview.orchestration.state import ExpertViewState

_FIXED_TS = datetime(2026, 5, 25, 14, 30, 0, tzinfo=UTC)


def _make_incident() -> Incident:
    return Incident(
        id="test-incident",
        summary="Test incident for state smoke.",
        observed_at=_FIXED_TS,
        symptoms=["s1"],
        affected_assets=["asset-1"],
    )


def _make_finding(claim: str, conf: float) -> Finding:
    return Finding(
        investigator_domain="mechanical",
        claim=claim,
        confidence=conf,
        citations=[],
        raised_at=_FIXED_TS,
    )


def test_expertviewstate_accepts_minimal_dict() -> None:
    state: ExpertViewState = {
        "incident": _make_incident(),
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }
    assert state["incident"].id == "test-incident"
    assert state["causal_report"] is None
    assert state["findings"] == []


def test_expertviewstate_accepts_populated_dict() -> None:
    finding = _make_finding("test claim", 0.5)
    state: ExpertViewState = {
        "incident": _make_incident(),
        "findings": [finding],
        "hypotheses": [],
        "spawned_subinvestigations": ["supply-history-sub-001"],
        "causal_report": None,
    }
    assert state["findings"][0].claim == "test claim"
    assert state["spawned_subinvestigations"] == ["supply-history-sub-001"]


def test_findings_reducer_is_operator_add() -> None:
    """The list-typed fields must carry operator.add as Annotated metadata."""
    hints = get_type_hints(ExpertViewState, include_extras=True)
    for field in ("findings", "hypotheses", "spawned_subinvestigations"):
        annotation = hints[field]
        assert hasattr(annotation, "__metadata__"), (
            f"{field} must be Annotated[list, reducer] — found bare {annotation!r}"
        )
        assert operator.add in annotation.__metadata__, (
            f"{field} reducer must be operator.add — found {annotation.__metadata__!r}"
        )


def test_causal_report_field_has_no_reducer() -> None:
    """causal_report is single-writer (synthesizer); accidental reducer would be wrong."""
    hints = get_type_hints(ExpertViewState, include_extras=True)
    annotation = hints["causal_report"]
    assert not hasattr(annotation, "__metadata__"), (
        "causal_report must not carry a reducer — synthesizer is the sole writer."
    )


def test_reducer_merges_concurrent_finding_patches() -> None:
    """Simulate two concurrent investigator branches emitting findings.

    LangGraph applies the Annotated reducer to merge patches. We exercise
    operator.add directly so this test is independent of the LangGraph
    runtime — if the annotation in state.py drops the reducer, the
    sibling test above fails; if operator.add semantics change (impossible,
    but), this test fails.
    """
    branch_a_patch = {"findings": [_make_finding("mechanical bearing anomaly", 0.7)]}
    branch_b_patch = {"findings": [_make_finding("supply-chain batch anomaly", 0.8)]}

    merged = operator.add(branch_a_patch["findings"], branch_b_patch["findings"])

    assert len(merged) == 2
    assert merged[0].claim == "mechanical bearing anomaly"
    assert merged[1].claim == "supply-chain batch anomaly"


def test_causal_report_typed_as_optional() -> None:
    """A pre-synthesis state must validly carry causal_report=None."""
    state: ExpertViewState = {
        "incident": _make_incident(),
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }
    assert state["causal_report"] is None

    report = CausalReport(
        incident_id="test-incident",
        top_hypotheses=[],
        causal_chain=[],
        confidence_summary="empty",
        generated_at=_FIXED_TS,
    )
    state["causal_report"] = report
    assert state["causal_report"].incident_id == "test-incident"
