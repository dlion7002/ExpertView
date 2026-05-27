"""Pure spawning predicates for dynamic sub-investigation routing."""

from expertview.evidence.models import Finding

__all__ = ["is_bearing_anomaly"]

_ANOMALY_TERMS = (
    "anomaly",
    "brinelling",
    "chatter",
    "fault",
    "preload",
    "runout",
    "variation",
    "wear",
)


def is_bearing_anomaly(finding: Finding) -> bool:
    claim = finding.claim.lower()
    return (
        finding.investigator_domain == "mechanical"
        and "bearing" in claim
        and any(term in claim for term in _ANOMALY_TERMS)
    )
