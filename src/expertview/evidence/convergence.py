"""Pure convergence math for evidence-weighted causal reports."""

from itertools import pairwise

from expertview.evidence.models import CausalLink, Finding, Hypothesis, Incident, Symptom

__all__ = [
    "corroborating_domains",
    "link_causes",
    "mean_evidence_weight",
    "score_hypothesis",
    "weight_finding",
]

_CITATION_LIFT = 0.03
_MAX_CITATION_LIFT = 0.12
# Confidence is a weighted blend (weights sum to 1.0) of the mean finding weight
# and two convergence signals. The blend keeps confidence in [0, 1] with headroom
# below the ceiling, so realistic high-confidence findings (investigators rarely
# emit below ~0.8) do not all saturate at 1.0 — the dominant cause then separates
# from also-rans on how many independent domains corroborate it and how much
# evidence stacks behind it, rather than on an alphabetical tie-break.
_BASE_WEIGHT = 0.7
_BREADTH_WEIGHT = 0.2
_DEPTH_WEIGHT = 0.1
# Extra distinct domains / extra supporting findings that saturate each signal.
_BREADTH_SPAN = 2
_DEPTH_SPAN = 3
_MAX_CHAIN_LENGTH = 3
_MAX_SYMPTOM_LINKS = 3


def weight_finding(finding: Finding) -> float:
    # Citation lift rewards externally anchored evidence without baking in incident domains.
    citation_lift = min(len(finding.citations) * _CITATION_LIFT, _MAX_CITATION_LIFT)
    return _clamp(finding.confidence + citation_lift)


def corroborating_domains(hypothesis: Hypothesis) -> tuple[str, ...]:
    """Distinct investigator domains backing a hypothesis (origin first, then sorted).

    The deterministic "breadth" half of the hybrid reasoning surface: how many
    independent domains corroborate the cause. Mirrors the domain set
    `score_hypothesis` uses, so the rendered/explained breadth matches the score.
    """
    others = sorted(
        {finding.investigator_domain for finding in hypothesis.supporting_findings}
        - {hypothesis.domain_origin}
    )
    return (hypothesis.domain_origin, *others)


def mean_evidence_weight(hypothesis: Hypothesis) -> float:
    """Mean citation-lifted evidence weight across a hypothesis's findings (0.0 if none)."""
    findings = hypothesis.supporting_findings
    if not findings:
        return 0.0
    return _round_confidence(sum(weight_finding(finding) for finding in findings) / len(findings))


def score_hypothesis(hypothesis: Hypothesis) -> Hypothesis:
    findings = hypothesis.supporting_findings
    if not findings:
        return hypothesis.model_copy(update={"confidence": 0.0})

    finding_weights = [weight_finding(finding) for finding in findings]
    mean_weight = sum(finding_weights) / len(finding_weights)

    # Breadth: independent domains corroborating the hypothesis (the cross-domain
    # convergence that the architecture is built to surface). Depth: how many
    # findings stack behind it. Both normalized to [0, 1].
    domain_count = len(
        {finding.investigator_domain for finding in findings} | {hypothesis.domain_origin}
    )
    breadth_signal = _normalize(domain_count - 1, _BREADTH_SPAN)
    depth_signal = _normalize(len(findings) - 1, _DEPTH_SPAN)

    confidence = (
        _BASE_WEIGHT * mean_weight + _BREADTH_WEIGHT * breadth_signal + _DEPTH_WEIGHT * depth_signal
    )
    return hypothesis.model_copy(update={"confidence": _round_confidence(confidence)})


def link_causes(hypotheses: list[Hypothesis], incident: Incident) -> list[CausalLink]:
    scored_hypotheses = [score_hypothesis(hypothesis) for hypothesis in hypotheses]
    ranked_hypotheses = sorted(
        scored_hypotheses,
        key=lambda hypothesis: (
            -hypothesis.confidence,
            hypothesis.domain_origin,
            hypothesis.id,
            hypothesis.claim,
        ),
    )
    if not ranked_hypotheses:
        return []

    chain_hypotheses = _top_cross_domain_hypotheses(ranked_hypotheses)
    links = [
        CausalLink(
            cause=cause,
            effect=effect,
            strength=_round_confidence((cause.confidence + effect.confidence) / 2),
            rationale=(
                f"Evidence-weighted {cause.domain_origin} hypothesis feeds the "
                f"{effect.domain_origin} hypothesis."
            ),
        )
        for cause, effect in pairwise(chain_hypotheses)
    ]

    terminal_hypothesis = chain_hypotheses[-1]
    links.extend(_terminal_symptom_links(terminal_hypothesis, incident))
    return links


def _top_cross_domain_hypotheses(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    selected = [hypotheses[0]]
    seen_domains = {hypotheses[0].domain_origin}
    for hypothesis in hypotheses[1:]:
        if hypothesis.domain_origin in seen_domains:
            continue
        selected.append(hypothesis)
        seen_domains.add(hypothesis.domain_origin)
        if len(selected) == _MAX_CHAIN_LENGTH:
            break
    return selected


def _terminal_symptom_links(hypothesis: Hypothesis, incident: Incident) -> list[CausalLink]:
    return [
        CausalLink(
            cause=hypothesis,
            effect=Symptom(description=symptom, observed_at=incident.observed_at),
            strength=hypothesis.confidence,
            rationale=(
                f"Evidence-weighted {hypothesis.domain_origin} hypothesis explains "
                f"incident symptom: {symptom}."
            ),
        )
        for symptom in incident.symptoms[:_MAX_SYMPTOM_LINKS]
    ]


def _normalize(value: int, span: int) -> float:
    return _clamp(value / span)


def _round_confidence(value: float) -> float:
    return round(_clamp(value), 4)


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)
