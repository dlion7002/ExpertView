"""JSON round-trip + boundary-validation tests for the cross-agent schemas.

The round-trip pattern (build → model_dump_json → model_validate_json →
equality) is the anti-drift mechanism behind the architecture rule that
forbids raw dicts across agent boundaries. If a future schema change breaks
serialization, these tests fail immediately rather than at the next demo
rehearsal.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from expertview.evidence.models import (
    CausalLink,
    CausalReport,
    Document,
    Finding,
    Hypothesis,
    Incident,
    Symptom,
)

_FIXED_TS = datetime(2026, 5, 25, 14, 30, 0, tzinfo=UTC)


def _roundtrip[T](instance: T) -> T:
    return type(instance).model_validate_json(instance.model_dump_json())


def test_document_roundtrip() -> None:
    doc = Document(
        id="mech-hydraulic-001",
        content="Hydraulic cylinder service log: replaced seal kit on 2026-05-20.",
        source="data/domains/mechanical/hydraulic_service_log.md",
        domain="mechanical",
        metadata={"author": "shift-3-tech", "tags": ["hydraulic", "maintenance"]},
    )
    assert _roundtrip(doc) == doc


def test_incident_roundtrip() -> None:
    incident = Incident(
        id="cnc-out-of-tolerance-2026-05-24",
        summary="CNC line 2 producing out-of-tolerance parts on shift 3.",
        observed_at=_FIXED_TS,
        symptoms=["dimensional drift > 0.05mm", "audible bearing chatter"],
        affected_assets=["cnc-line-2", "spindle-04"],
    )
    assert _roundtrip(incident) == incident


def test_finding_roundtrip() -> None:
    finding = Finding(
        investigator_domain="mechanical",
        claim="Bearing wear pattern consistent with batch-level lubrication shortfall.",
        confidence=0.78,
        citations=["mech-hydraulic-001", "mech-bearing-batch-2026-05"],
        raised_at=_FIXED_TS,
    )
    assert _roundtrip(finding) == finding


def test_hypothesis_roundtrip() -> None:
    finding = Finding(
        investigator_domain="supply_chain",
        claim="New supplier bearing batch arrived 2026-05-18.",
        confidence=0.91,
        citations=["supply-po-44213"],
        raised_at=_FIXED_TS,
    )
    hypothesis = Hypothesis(
        id="hyp-bearing-batch",
        claim="Out-of-spec bearings from new supplier batch are the proximate cause.",
        supporting_findings=[finding],
        confidence=0.74,
        domain_origin="supply_chain",
    )
    assert _roundtrip(hypothesis) == hypothesis


def test_symptom_roundtrip_with_observed_at() -> None:
    symptom = Symptom(
        description="Out-of-tolerance dimension on part X-104.",
        observed_at=_FIXED_TS,
    )
    assert _roundtrip(symptom) == symptom


def test_symptom_roundtrip_without_observed_at() -> None:
    symptom = Symptom(description="Operator reports unusual spindle noise.")
    assert _roundtrip(symptom) == symptom


def _make_hypothesis(claim: str, domain: str, conf: float = 0.7) -> Hypothesis:
    return Hypothesis(
        id=f"hyp-{abs(hash(claim)) % 10_000}",
        claim=claim,
        supporting_findings=[],
        confidence=conf,
        domain_origin=domain,
    )


def test_causal_link_roundtrip_hypothesis_effect() -> None:
    link = CausalLink(
        cause=_make_hypothesis("New supplier batch is out of spec.", "supply_chain", 0.8),
        effect=_make_hypothesis("Spindle bearings degrade prematurely.", "mechanical", 0.7),
        strength=0.65,
        rationale="Out-of-spec bearings reduce service life by an order of magnitude.",
    )
    assert _roundtrip(link) == link


def test_causal_link_roundtrip_symptom_effect() -> None:
    link = CausalLink(
        cause=_make_hypothesis("Spindle bearings degrade prematurely.", "mechanical", 0.7),
        effect=Symptom(description="Dimensional drift > 0.05mm.", observed_at=_FIXED_TS),
        strength=0.82,
        rationale="Worn bearings introduce runout that propagates to part dimensions.",
    )
    assert _roundtrip(link) == link


def test_causal_report_roundtrip() -> None:
    top_hyp = _make_hypothesis("Supplier batch root cause.", "supply_chain", 0.74)
    link = CausalLink(
        cause=top_hyp,
        effect=Symptom(description="Out-of-tolerance parts."),
        strength=0.7,
        rationale="See chain.",
    )
    report = CausalReport(
        incident_id="cnc-out-of-tolerance-2026-05-24",
        top_hypotheses=[top_hyp],
        causal_chain=[link],
        confidence_summary=(
            "Primary cause: supplier-batch bearings (0.74). Secondary: shift handover gap."
        ),
        generated_at=_FIXED_TS,
    )
    assert _roundtrip(report) == report


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, -1.0, 2.0])
def test_finding_rejects_out_of_range_confidence(bad_confidence: float) -> None:
    with pytest.raises(ValidationError):
        Finding(
            investigator_domain="mechanical",
            claim="x",
            confidence=bad_confidence,
            citations=[],
        )


@pytest.mark.parametrize("bad_confidence", [-0.5, 1.5])
def test_hypothesis_rejects_out_of_range_confidence(bad_confidence: float) -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            claim="x",
            supporting_findings=[],
            confidence=bad_confidence,
            domain_origin="mechanical",
        )


@pytest.mark.parametrize("bad_strength", [-0.1, 1.1])
def test_causal_link_rejects_out_of_range_strength(bad_strength: float) -> None:
    cause = _make_hypothesis("a", "mechanical", 0.5)
    effect = _make_hypothesis("b", "process", 0.5)
    with pytest.raises(ValidationError):
        CausalLink(cause=cause, effect=effect, strength=bad_strength, rationale="x")
