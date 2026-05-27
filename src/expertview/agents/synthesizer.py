"""Synthesizer LangGraph node factory.

Terminal node: reads `incident` and `findings` from `ExpertViewState`, calls
the synthesizer LLM (constructed elsewhere via `agents.llms`), then applies the
deterministic post-LLM re-scoring from `evidence/convergence.py` and returns
`{"causal_report": CausalReport(...)}` as its state patch. The LLM only drafts
hypotheses and causal links; convergence owns the final confidence/strength
numbers, so the report's scores are reproducible Python rather than LLM whim.
The node is side-effect free per the CLAUDE.md architecture rules: no disk
writes, no state writes outside the returned patch, no spawning. Re-scoring is
a pure transform of the parsed report into a new frozen report.
"""

import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from string import Template
from typing import Protocol

from pydantic import TypeAdapter

from expertview.evidence.convergence import link_causes, score_hypothesis
from expertview.evidence.models import CausalReport, Finding, Hypothesis, Incident
from expertview.orchestration.state import ExpertViewState

__all__ = ["make_synthesizer_node"]

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "synthesizer" / "default.md"
_FINDINGS_ADAPTER = TypeAdapter(list[Finding])
# Real OpenRouter models routinely wrap JSON in ```json ... ``` fences despite
# explicit prompt instructions. Strip them at the boundary before validation.
_JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)

SynthesizerNode = Callable[[ExpertViewState], Awaitable[dict[str, CausalReport]]]


class SynthesizerLlm(Protocol):
    async def ainvoke(self, input: str) -> object: ...


def make_synthesizer_node(llm: SynthesizerLlm) -> SynthesizerNode:
    prompt_template = Template(_PROMPT_PATH.read_text(encoding="utf-8"))

    async def synthesizer_node(state: ExpertViewState) -> dict[str, CausalReport]:
        incident = state["incident"]
        findings = state["findings"]
        prompt = _render_prompt(prompt_template, incident, findings)
        response = await llm.ainvoke(prompt)
        draft = _parse_causal_report(_response_text(response))
        report = _rescore_report(draft, incident)
        _validate_report(report, incident)
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


def _response_text(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    raise TypeError("Synthesizer LLM response content must be text.")


def _parse_causal_report(response_text: str) -> CausalReport:
    return CausalReport.model_validate_json(_strip_json_fence(response_text))


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
