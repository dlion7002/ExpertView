"""Unit tests for spawning predicates."""

from expertview.agents.spawning import is_bearing_anomaly
from expertview.evidence.models import Finding


def _finding(domain: str, claim: str) -> Finding:
    return Finding(
        investigator_domain=domain,
        claim=claim,
        confidence=0.7,
        citations=["source-001"],
    )


def test_is_bearing_anomaly_matches_representative_mechanical_bearing_findings() -> None:
    claims = [
        "Bearing chatter and brinelling indicate a spindle bearing fault.",
        "Warm runout growth points to bearing preload loss on spindle-04.",
        "Bearing lot variation may explain preload adjustment difficulty.",
    ]

    assert all(is_bearing_anomaly(_finding("mechanical", claim)) for claim in claims)


def test_is_bearing_anomaly_rejects_non_bearing_mechanical_findings() -> None:
    assert not is_bearing_anomaly(
        _finding(
            "mechanical",
            "Hydraulic cylinder service preceded clamp-settle oscillation.",
        )
    )


def test_is_bearing_anomaly_rejects_bearing_mentions_without_anomaly_language() -> None:
    assert not is_bearing_anomaly(
        _finding(
            "mechanical",
            "Bearing batch B-227 was listed on the maintenance traveler.",
        )
    )


def test_is_bearing_anomaly_rejects_other_domains() -> None:
    assert not is_bearing_anomaly(
        _finding(
            "supply_chain",
            "Bearing Supplier - North remains under controlled-use monitoring.",
        )
    )


def test_is_bearing_anomaly_is_pure_over_finding_model() -> None:
    finding = _finding(
        "mechanical",
        "Bearing chatter after warm-up indicates possible preload loss.",
    )
    before = finding.model_dump()

    first = is_bearing_anomaly(finding)
    second = is_bearing_anomaly(finding)

    assert first is True
    assert second is True
    assert finding.model_dump() == before
