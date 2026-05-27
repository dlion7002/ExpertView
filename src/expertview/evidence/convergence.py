"""Pure convergence math for evidence-weighted causal reports."""

from itertools import pairwise

from expertview.evidence.models import CausalLink, Finding, Hypothesis, Incident, Symptom

__all__ = ["link_causes", "score_hypothesis", "weight_finding"]

_CITATION_LIFT = 0.03
_MAX_CITATION_LIFT = 0.12
_SUPPORT_LIFT = 0.03
_MAX_SUPPORT_LIFT = 0.09
_CROSS_DOMAIN_LIFT = 0.04
_MAX_CHAIN_LENGTH = 3
_MAX_SYMPTOM_LINKS = 3


def weight_finding(finding: Finding) -> float:
    # Citation lift rewards externally anchored evidence without baking in incident domains.
    citation_lift = min(len(finding.citations) * _CITATION_LIFT, _MAX_CITATION_LIFT)
    return _clamp(finding.confidence + citation_lift)


def score_hypothesis(hypothesis: Hypothesis) -> Hypothesis:
    if not hypothesis.supporting_findings:
        return hypothesis.model_copy(update={"confidence": 0.0})

    finding_weights = [weight_finding(finding) for finding in hypothesis.supporting_findings]
    base_score = sum(finding_weights) / len(finding_weights)
    # Support lift distinguishes convergent evidence from one strong finding while staying bounded.
    support_lift = min(
        max(len(hypothesis.supporting_findings) - 1, 0) * _SUPPORT_LIFT,
        _MAX_SUPPORT_LIFT,
    )
    domain_count = len(
        {finding.investigator_domain for finding in hypothesis.supporting_findings}
        | {hypothesis.domain_origin}
    )
    cross_domain_lift = _CROSS_DOMAIN_LIFT if domain_count > 1 else 0.0

    confidence = _round_confidence(base_score + support_lift + cross_domain_lift)
    return hypothesis.model_copy(update={"confidence": confidence})


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


def _round_confidence(value: float) -> float:
    return round(_clamp(value), 4)


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)
