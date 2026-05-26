"""Synthesizer LangGraph node factory.

Terminal node: reads `incident` and `findings` from `ExpertViewState`, calls
the synthesizer LLM (constructed elsewhere via `agents.llms`), and returns
`{"causal_report": CausalReport(...)}` as its state patch. The node is
side-effect free per the CLAUDE.md architecture rules: no disk writes, no
state writes outside the returned patch, no spawning.
"""

import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from string import Template
from typing import Protocol

from pydantic import TypeAdapter

from expertview.evidence.models import CausalReport, Finding, Incident
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
        report = _parse_causal_report(_response_text(response))
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


def _validate_report(report: CausalReport, incident: Incident) -> None:
    if report.incident_id != incident.id:
        raise ValueError(
            "Synthesizer report incident_id must match the input incident id: "
            f"got {report.incident_id!r}, expected {incident.id!r}."
        )
    if not report.top_hypotheses:
        raise ValueError("Synthesizer report must contain at least one hypothesis.")
