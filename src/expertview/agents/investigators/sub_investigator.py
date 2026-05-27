"""Parameterized spawned-investigator LangGraph node factory."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Protocol

from pydantic import TypeAdapter

from expertview.agents.spawning import is_bearing_anomaly
from expertview.evidence.models import Document, Finding, Incident
from expertview.log import get_logger
from expertview.rag.base import KnowledgeStore

if TYPE_CHECKING:
    from expertview.orchestration.state import ExpertViewState

__all__ = ["make_sub_investigator_node"]

_LOGGER = get_logger("expertview.investigator")
_LOG_DOMAIN = "sub_investigator"
_PROMPT_PATH = Path(__file__).parents[2] / "prompts" / "investigator" / "sub_investigator.md"
_DOCUMENTS_ADAPTER = TypeAdapter(list[Document])
_FINDINGS_ADAPTER = TypeAdapter(list[Finding])
# Real OpenRouter models routinely wrap JSON in ```json ... ``` fences despite
# explicit prompt instructions. Strip them at the boundary before validation.
_JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)

SubInvestigatorNode = Callable[["ExpertViewState"], Awaitable[dict[str, list[Finding]]]]


class InvestigatorLlm(Protocol):
    async def ainvoke(self, input: str) -> object: ...


def make_sub_investigator_node(
    domain: str,
    store: KnowledgeStore,
    llm: InvestigatorLlm,
    *,
    k: int = 5,
) -> SubInvestigatorNode:
    prompt_template = Template(_PROMPT_PATH.read_text(encoding="utf-8"))

    async def sub_investigator_node(state: ExpertViewState) -> dict[str, list[Finding]]:
        incident = state["incident"]
        _LOGGER.info("investigator.start", domain=_LOG_DOMAIN, incident_id=incident.id)
        parent_finding = _parent_finding(state["findings"])
        documents = store.search(_supplier_history_query(incident, parent_finding), k=k)
        prompt = _render_prompt(prompt_template, incident, parent_finding, documents)
        response = await llm.ainvoke(prompt)
        findings = _parse_findings(_response_text(response))
        _validate_findings(findings, documents, domain)
        _LOGGER.info("investigator.finish", domain=_LOG_DOMAIN, finding_count=len(findings))
        return {"findings": findings}

    return sub_investigator_node


def _parent_finding(findings: list[Finding]) -> Finding:
    for finding in findings:
        if is_bearing_anomaly(finding):
            return finding
    raise ValueError("Sub-investigator requires a bearing-anomaly parent finding.")


def _supplier_history_query(incident: Incident, parent_finding: Finding) -> str:
    parts = [
        parent_finding.claim,
        incident.summary,
        *incident.symptoms,
        *incident.affected_assets,
        "supplier qualification audit prior batch bearing history",
    ]
    return " ".join(part for part in parts if part.strip())


def _render_prompt(
    prompt_template: Template,
    incident: Incident,
    parent_finding: Finding,
    documents: list[Document],
) -> str:
    return prompt_template.substitute(
        parent_finding_claim=parent_finding.claim,
        incident_json=incident.model_dump_json(indent=2),
        retrieved_documents_json=_documents_json(documents),
    )


def _documents_json(documents: list[Document]) -> str:
    return _DOCUMENTS_ADAPTER.dump_json(documents, indent=2).decode()


def _response_text(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    raise TypeError("Sub-investigator LLM response content must be text.")


def _parse_findings(response_text: str) -> list[Finding]:
    return _FINDINGS_ADAPTER.validate_json(_strip_json_fence(response_text))


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    match = _JSON_FENCE_PATTERN.match(stripped)
    if match is not None:
        return match.group(1).strip()
    return stripped


def _validate_findings(findings: list[Finding], documents: list[Document], domain: str) -> None:
    valid_citations = {document.id for document in documents} | {
        document.source for document in documents
    }
    for finding in findings:
        if finding.investigator_domain != domain:
            raise ValueError(f'Sub-investigator findings must use domain "{domain}".')
        if not finding.citations:
            raise ValueError("Sub-investigator findings must include at least one citation.")
        unknown = sorted(set(finding.citations) - valid_citations)
        if unknown:
            raise ValueError(
                "Sub-investigator citations must reference retrieved document "
                "ids or sources: " + ", ".join(unknown)
            )
