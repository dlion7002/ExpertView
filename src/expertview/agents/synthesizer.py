"""Synthesizer LangGraph node factory.

Terminal node, two LLM passes. Pass 1 reads `incident` and `findings` from
`ExpertViewState` and drafts hypotheses and causal links; the deterministic
post-LLM re-scoring from `evidence/convergence.py` then assigns the final
confidence/strength numbers and ranking. Pass 2 reads the *re-scored* report
back to the LLM and asks only for the deductive narrative — `verdict_reasoning`
(why the top hypothesis is the conclusion) and `alternatives_summary` (the one
comparative paragraph on what was considered and ruled out). The LLM never owns
the numbers; convergence does, so the scores stay reproducible Python and the
narrative is grounded in them rather than in the LLM's pre-scoring guesses.
The node returns `{"causal_report": CausalReport(...)}` and is side-effect free
per the CLAUDE.md architecture rules: no disk writes, no state writes outside
the returned patch, no spawning.
"""

import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from string import Template
from typing import Protocol

from pydantic import BaseModel, ConfigDict, TypeAdapter

from expertview.evidence.convergence import (
    corroborating_domains,
    link_causes,
    mean_evidence_weight,
    score_hypothesis,
)
from expertview.evidence.models import CausalReport, Finding, Hypothesis, Incident
from expertview.orchestration.state import ExpertViewState

__all__ = ["make_synthesizer_node"]

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "synthesizer"
_PROMPT_PATH = _PROMPTS_DIR / "default.md"
_REASONING_PROMPT_PATH = _PROMPTS_DIR / "reasoning.md"
_FINDINGS_ADAPTER = TypeAdapter(list[Finding])
# Real OpenRouter models routinely wrap JSON in ```json ... ``` fences despite
# explicit prompt instructions. Strip them at the boundary before validation.
_JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)

SynthesizerNode = Callable[[ExpertViewState], Awaitable[dict[str, CausalReport]]]


class SynthesizerLlm(Protocol):
    async def ainvoke(self, input: str) -> object: ...


class _ReasoningNarrative(BaseModel):
    # Boundary model for the pass-2 LLM response. Extra keys are ignored; an
    # absent or malformed narrative raises here rather than being patched over.
    model_config = ConfigDict(frozen=True)

    verdict_reasoning: str
    alternatives_summary: str = ""


def make_synthesizer_node(llm: SynthesizerLlm) -> SynthesizerNode:
    prompt_template = Template(_PROMPT_PATH.read_text(encoding="utf-8"))
    reasoning_template = Template(_REASONING_PROMPT_PATH.read_text(encoding="utf-8"))

    async def synthesizer_node(state: ExpertViewState) -> dict[str, CausalReport]:
        incident = state["incident"]
        findings = state["findings"]
        prompt = _render_prompt(prompt_template, incident, findings)
        response = await llm.ainvoke(prompt)
        draft = _parse_causal_report(_response_text(response))
        report = _rescore_report(draft, incident)
        _validate_report(report, incident)

        reasoning_prompt = _render_reasoning_prompt(reasoning_template, incident, report, findings)
        reasoning_response = await llm.ainvoke(reasoning_prompt)
        narrative = _parse_reasoning(_response_text(reasoning_response))
        report = report.model_copy(
            update={
                "verdict_reasoning": narrative.verdict_reasoning,
                "alternatives_summary": narrative.alternatives_summary,
            }
        )
        return {"causal_report": report}

    return synthesizer_node


def _render_prompt(
    prompt_template: Template,
    incident: Incident,
    findings: list[Finding],
) -> str:
    return prompt_template.substitute(
        incident_json=incident.model_dump_json(indent=2),
        findings_json=_findings_json(findings),
    )


def _findings_json(findings: list[Finding]) -> str:
    return _FINDINGS_ADAPTER.dump_json(findings, indent=2).decode()


def _render_reasoning_prompt(
    reasoning_template: Template,
    incident: Incident,
    report: CausalReport,
    findings: list[Finding],
) -> str:
    return reasoning_template.substitute(
        incident_json=incident.model_dump_json(indent=2),
        ranking_basis=_ranking_basis(report.top_hypotheses),
        all_findings_json=_findings_json(findings),
    )


def _ranking_basis(hypotheses: list[Hypothesis]) -> str:
    # Deterministic "math" half handed to the reasoning LLM: each ranked
    # hypothesis with its final convergence score and the breadth/depth signals
    # behind it, so the narrative can explain the numbers without re-deriving them.
    lines: list[str] = []
    for rank, hypothesis in enumerate(hypotheses, start=1):
        domains = corroborating_domains(hypothesis)
        lines.append(
            f"{rank}. [confidence {hypothesis.confidence:.0%}] ({hypothesis.domain_origin}) "
            f"{hypothesis.claim}\n"
            f"   - corroborated by {len(domains)} domain(s): {', '.join(domains)}\n"
            f"   - {len(hypothesis.supporting_findings)} supporting finding(s), "
            f"mean evidence weight {mean_evidence_weight(hypothesis):.2f}"
        )
    return "\n".join(lines)


def _response_text(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    raise TypeError("Synthesizer LLM response content must be text.")


def _parse_causal_report(response_text: str) -> CausalReport:
    return CausalReport.model_validate_json(_strip_json_fence(response_text))


def _parse_reasoning(response_text: str) -> _ReasoningNarrative:
    return _ReasoningNarrative.model_validate_json(_strip_json_fence(response_text))


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    match = _JSON_FENCE_PATTERN.match(stripped)
    if match is not None:
        return match.group(1).strip()
    return stripped


def _rescore_report(draft: CausalReport, incident: Incident) -> CausalReport:
    # Post-LLM re-scoring: the LLM's draft confidences/strengths are advisory;
    # convergence assigns the final numbers deterministically. `score_hypothesis`
    # copies every non-confidence field (including `supporting_findings` and their
    # citations) verbatim, so the prompt's citation-preservation contract survives.
    scored = [score_hypothesis(hypothesis) for hypothesis in draft.top_hypotheses]
    # Match `link_causes`'s internal ordering so `top_hypotheses[0]` is the same
    # top cause that heads the re-scored causal chain.
    ranked = sorted(scored, key=_hypothesis_rank_key)
    causal_chain = link_causes(ranked, incident)
    return draft.model_copy(
        update={
            "top_hypotheses": ranked,
            "causal_chain": causal_chain,
            "confidence_summary": _summarize_confidence(ranked),
        }
    )


def _hypothesis_rank_key(hypothesis: Hypothesis) -> tuple[float, str, str, str]:
    return (
        -hypothesis.confidence,
        hypothesis.domain_origin,
        hypothesis.id,
        hypothesis.claim,
    )


def _summarize_confidence(ranked: list[Hypothesis]) -> str:
    # Assembled from the computed scores, not the LLM's prose, so the summary
    # always reflects the re-scored numbers the report actually shows. The empty
    # case is left to `_validate_report`, which rejects a hypothesis-free report.
    if not ranked:
        return "No supportable hypothesis emerged from the gathered findings."

    top = ranked[0]
    domains = {hypothesis.domain_origin for hypothesis in ranked}
    if len(ranked) == 1:
        return (
            f"Evidence converges on a single {top.domain_origin} hypothesis at "
            f"{top.confidence:.0%} confidence."
        )

    margin = top.confidence - ranked[1].confidence
    return (
        f"Top cause is {top.domain_origin}-led at {top.confidence:.0%} confidence, "
        f"leading the next hypothesis by {margin:.0%} across {len(ranked)} hypotheses "
        f"spanning {len(domains)} domain(s)."
    )


def _validate_report(report: CausalReport, incident: Incident) -> None:
    if report.incident_id != incident.id:
        raise ValueError(
            "Synthesizer report incident_id must match the input incident id: "
            f"got {report.incident_id!r}, expected {incident.id!r}."
        )
    if not report.top_hypotheses:
        raise ValueError("Synthesizer report must contain at least one hypothesis.")
