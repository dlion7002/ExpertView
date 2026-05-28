"""Unit tests for pure evidence convergence functions."""

from datetime import UTC, datetime
from math import isfinite

import pytest

from expertview.evidence.convergence import (
    corroborating_domains,
    link_causes,
    mean_evidence_weight,
    score_hypothesis,
    weight_finding,
)
from expertview.evidence.models import CausalLink, Finding, Hypothesis, Incident, Symptom

_OBSERVED_AT = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)


def _finding(
    domain: str,
    claim: str,
    confidence: float,
    citations: list[str] | None = None,
) -> Finding:
    return Finding(
        investigator_domain=domain,
        claim=claim,
        confidence=confidence,
        citations=citations or ["source-001"],
        raised_at=_OBSERVED_AT,
    )


def _hypothesis(
    hypothesis_id: str,
    domain: str,
    findings: list[Finding],
    confidence: float = 0.5,
) -> Hypothesis:
    return Hypothesis(
        id=hypothesis_id,
        claim=f"{domain} hypothesis {hypothesis_id}",
        supporting_findings=findings,
        confidence=confidence,
        domain_origin=domain,
    )


def _incident() -> Incident:
    return Incident(
        id="incident-001",
        summary="Manufacturing incident with cross-domain symptoms.",
        observed_at=_OBSERVED_AT,
        symptoms=[
            "first symptom",
            "second symptom",
            "third symptom",
            "fourth symptom",
        ],
        affected_assets=["line-1"],
    )


@pytest.mark.parametrize(
    "domain",
    [
        "mechanical",
        "process",
        "supply_chain",
        "environmental",
        "human_factors",
        "quality_shadow_board",
    ],
)
def test_weight_finding_is_pure_total_and_finite(domain: str) -> None:
    finding = _finding(
        domain,
        f"{domain} evidence claim.",
        0.62,
        ["source-001", "source-002"],
    )
    before = finding.model_dump()

    first = weight_finding(finding)
    second = weight_finding(finding)

    assert first == second
    assert isfinite(first)
    assert 0.0 <= first <= 1.0
    assert finding.model_dump() == before


def test_score_hypothesis_returns_new_model_and_preserves_fields_except_confidence() -> None:
    finding = _finding("mechanical", "Bearing chatter increased.", 0.72, ["mech-001"])
    hypothesis = _hypothesis("hyp-mech", "mechanical", [finding], confidence=0.12)

    scored = score_hypothesis(hypothesis)

    assert scored is not hypothesis
    assert 0.0 <= scored.confidence <= 1.0
    assert scored.confidence != hypothesis.confidence
    assert hypothesis.confidence == 0.12
    assert scored.model_dump(exclude={"confidence"}) == hypothesis.model_dump(
        exclude={"confidence"}
    )


def test_score_hypothesis_handles_zero_supporting_findings() -> None:
    hypothesis = _hypothesis("hyp-empty", "process", [], confidence=0.88)

    scored = score_hypothesis(hypothesis)

    assert scored is not hypothesis
    assert scored.confidence == 0.0
    assert hypothesis.confidence == 0.88


def test_score_hypothesis_ranks_stronger_evidence_higher() -> None:
    weak = _hypothesis(
        "hyp-weak",
        "mechanical",
        [_finding("mechanical", "Weak support.", 0.35, ["weak-001"])],
    )
    strong = _hypothesis(
        "hyp-strong",
        "mechanical",
        [
            _finding("mechanical", "Strong support.", 0.82, ["strong-001", "strong-002"]),
            _finding("supply_chain", "Corroborating support.", 0.74, ["supply-001"]),
        ],
    )

    assert score_hypothesis(strong).confidence > score_hypothesis(weak).confidence


def test_score_hypothesis_keeps_single_domain_stack_below_ceiling() -> None:
    # Many high-confidence findings from one domain score high but must stay below
    # 1.0: this headroom is what stops every hypothesis from saturating and lets
    # cross-domain corroboration decide the top cause.
    hypothesis = _hypothesis(
        "hyp-high",
        "supply_chain",
        [
            _finding("supply_chain", f"High support {index}.", 0.99, ["a", "b", "c", "d"])
            for index in range(6)
        ],
    )

    scored = score_hypothesis(hypothesis)

    assert 0.7 < scored.confidence < 1.0


def test_score_hypothesis_reaches_ceiling_only_with_full_corroboration() -> None:
    # The ceiling is reached only when every signal maxes out: top-weight findings,
    # the depth span, and multiple corroborating domains.
    hypothesis = _hypothesis(
        "hyp-converged",
        "mechanical",
        [
            _finding("mechanical", "Top mechanical support.", 1.0, ["a", "b", "c", "d"]),
            _finding("supply_chain", "Top supply-chain support.", 1.0, ["a", "b", "c", "d"]),
            _finding("process", "Top process support.", 1.0, ["a", "b", "c", "d"]),
            _finding("environmental", "Top environmental support.", 1.0, ["a", "b", "c", "d"]),
        ],
    )

    scored = score_hypothesis(hypothesis)

    assert scored.confidence == 1.0


def test_score_hypothesis_rewards_cross_domain_corroboration() -> None:
    # Same finding count and confidence, but corroboration across domains outranks a
    # single-domain stack — the core "evidence-weighted convergence" property.
    single_domain = _hypothesis(
        "hyp-single",
        "mechanical",
        [
            _finding("mechanical", "Mechanical support one.", 0.8, ["m-001"]),
            _finding("mechanical", "Mechanical support two.", 0.8, ["m-002"]),
        ],
    )
    cross_domain = _hypothesis(
        "hyp-cross",
        "mechanical",
        [
            _finding("mechanical", "Mechanical support.", 0.8, ["m-001"]),
            _finding("supply_chain", "Supply-chain corroboration.", 0.8, ["sc-001"]),
        ],
    )

    assert score_hypothesis(cross_domain).confidence > score_hypothesis(single_domain).confidence


def test_link_causes_returns_deterministic_well_formed_links() -> None:
    hypotheses = [
        _hypothesis(
            "hyp-process",
            "process",
            [_finding("process", "Process drift.", 0.71, ["proc-001"])],
        ),
        _hypothesis(
            "hyp-mechanical",
            "mechanical",
            [
                _finding("mechanical", "Bearing fault.", 0.84, ["mech-001", "mech-002"]),
                _finding("supply_chain", "Supplier batch issue.", 0.76, ["supply-001"]),
            ],
        ),
        _hypothesis(
            "hyp-human",
            "human_factors",
            [_finding("human_factors", "Handover gap.", 0.66, ["human-001"])],
        ),
    ]
    input_ids = {hypothesis.id for hypothesis in hypotheses}
    incident = _incident()

    first = link_causes(hypotheses, incident)
    second = link_causes(hypotheses, incident)

    assert first == second
    assert len(first) == 5
    assert all(isinstance(link, CausalLink) for link in first)
    assert all(0.0 <= link.strength <= 1.0 for link in first)

    for link in first:
        assert link.cause.id in input_ids
        if isinstance(link.effect, Hypothesis):
            assert link.effect.id in input_ids
        else:
            assert isinstance(link.effect, Symptom)
            assert link.effect.description in incident.symptoms

    terminal_links = [link for link in first if isinstance(link.effect, Symptom)]
    assert len(terminal_links) == 3
    assert {link.effect.description for link in terminal_links} == set(incident.symptoms[:3])


def test_corroborating_domains_lists_origin_first_then_sorted_distinct() -> None:
    hypothesis = _hypothesis(
        "hyp-cross",
        "mechanical",
        [
            _finding("supply_chain", "Supplier batch issue.", 0.8, ["sc-001"]),
            _finding("mechanical", "Bearing fault.", 0.84, ["mech-001"]),
            _finding("supply_chain", "Second supply finding.", 0.7, ["sc-002"]),
        ],
    )

    assert corroborating_domains(hypothesis) == ("mechanical", "supply_chain")


def test_corroborating_domains_includes_origin_with_no_findings() -> None:
    assert corroborating_domains(_hypothesis("hyp-empty", "process", [])) == ("process",)


def test_mean_evidence_weight_matches_weight_finding_mean() -> None:
    findings = [
        _finding("mechanical", "First.", 0.80, ["a", "b"]),
        _finding("supply_chain", "Second.", 0.60, ["c"]),
    ]
    hypothesis = _hypothesis("hyp-mean", "mechanical", findings)

    expected = sum(weight_finding(finding) for finding in findings) / len(findings)

    assert mean_evidence_weight(hypothesis) == pytest.approx(expected, abs=1e-4)
    assert 0.0 <= mean_evidence_weight(hypothesis) <= 1.0


def test_mean_evidence_weight_is_zero_without_findings() -> None:
    assert mean_evidence_weight(_hypothesis("hyp-empty", "process", [])) == 0.0


def test_link_causes_returns_no_links_without_hypotheses() -> None:
    assert link_causes([], _incident()) == []


def test_distinct_finding_sets_produce_different_top_hypotheses() -> None:
    mechanical_led = [
        _hypothesis(
            "hyp-bearing",
            "mechanical",
            [
                _finding("mechanical", "Bearing fault.", 0.88, ["mech-001", "mech-002"]),
                _finding("supply_chain", "Supplier batch confirms lot issue.", 0.82, ["sc-001"]),
            ],
        ),
        _hypothesis(
            "hyp-process",
            "process",
            [_finding("process", "Minor process drift.", 0.48, ["proc-001"])],
        ),
    ]
    process_led = [
        _hypothesis(
            "hyp-bearing",
            "mechanical",
            [_finding("mechanical", "Low-confidence bearing noise.", 0.42, ["mech-001"])],
        ),
        _hypothesis(
            "hyp-process",
            "process",
            [
                _finding("process", "Mixer dwell-time drift.", 0.87, ["proc-001", "proc-002"]),
                _finding(
                    "environmental",
                    "Humidity shift worsened process window.",
                    0.78,
                    ["env-001"],
                ),
            ],
        ),
    ]

    mechanical_top = max(
        (score_hypothesis(hypothesis) for hypothesis in mechanical_led),
        key=lambda hypothesis: hypothesis.confidence,
    )
    process_top = max(
        (score_hypothesis(hypothesis) for hypothesis in process_led),
        key=lambda hypothesis: hypothesis.confidence,
    )

    assert mechanical_top.id == "hyp-bearing"
    assert process_top.id == "hyp-process"
    assert mechanical_top.id != process_top.id
