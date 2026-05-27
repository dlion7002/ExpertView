"""Supply-chain investigator LangGraph node factory."""

import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from string import Template
from typing import Protocol

from pydantic import TypeAdapter

from expertview.evidence.models import Document, Finding, Incident
from expertview.orchestration.state import ExpertViewState
from expertview.rag.base import KnowledgeStore

__all__ = ["make_supply_chain_investigator_node"]

_PROMPT_PATH = Path(__file__).parents[2] / "prompts" / "investigator" / "supply_chain.md"
_FINDINGS_ADAPTER = TypeAdapter(list[Finding])
# Real OpenRouter models routinely wrap JSON in ```json ... ``` fences despite
# explicit prompt instructions. Strip them at the boundary before validation.
_JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)

SupplyChainInvestigatorNode = Callable[[ExpertViewState], Awaitable[dict[str, list[Finding]]]]


class InvestigatorLlm(Protocol):
    async def ainvoke(self, input: str) -> object: ...


def make_supply_chain_investigator_node(
    store: KnowledgeStore,
    llm: InvestigatorLlm,
    *,
    k: int = 5,
) -> SupplyChainInvestigatorNode:
    prompt_template = Template(_PROMPT_PATH.read_text(encoding="utf-8"))

    async def supply_chain_investigator_node(
        state: ExpertViewState,
    ) -> dict[str, list[Finding]]:
        incident = state["incident"]
        documents = store.search(_incident_query(incident), k=k)
        prompt = _render_prompt(prompt_template, incident, documents)
        response = await llm.ainvoke(prompt)
        findings = _parse_findings(_response_text(response))
        _validate_findings(findings, documents)
        return {"findings": findings}

    return supply_chain_investigator_node


def _incident_query(incident: Incident) -> str:
    parts = [incident.summary, *incident.symptoms, *incident.affected_assets]
    return " ".join(part for part in parts if part.strip())


def _render_prompt(
    prompt_template: Template,
    incident: Incident,
    documents: list[Document],
) -> str:
    return prompt_template.substitute(
        incident_json=incident.model_dump_json(indent=2),
        retrieved_documents_json=_documents_json(documents),
    )


def _documents_json(documents: list[Document]) -> str:
    return TypeAdapter(list[Document]).dump_json(documents, indent=2).decode()


def _response_text(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    raise TypeError("Supply-chain investigator LLM response content must be text.")


def _parse_findings(response_text: str) -> list[Finding]:
    return _FINDINGS_ADAPTER.validate_json(_strip_json_fence(response_text))


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    match = _JSON_FENCE_PATTERN.match(stripped)
    if match is not None:
        return match.group(1).strip()
    return stripped


def _validate_findings(findings: list[Finding], documents: list[Document]) -> None:
    valid_citations = {document.id for document in documents} | {
        document.source for document in documents
    }
    for finding in findings:
        if finding.investigator_domain != "supply_chain":
            raise ValueError('Supply-chain investigator findings must use domain "supply_chain".')
        if not finding.citations:
            raise ValueError(
                "Supply-chain investigator findings must include at least one citation."
            )
        unknown = sorted(set(finding.citations) - valid_citations)
        if unknown:
            raise ValueError(
                "Supply-chain investigator citations must reference retrieved document "
                "ids or sources: " + ", ".join(unknown)
            )
