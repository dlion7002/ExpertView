"""Unit tests for the synthesizer node contract."""

from datetime import UTC, datetime

import pytest

from expertview.agents.synthesizer import make_synthesizer_node
from expertview.evidence.models import CausalReport, Finding, Incident
from expertview.orchestration.state import ExpertViewState

_OBSERVED_AT = datetime(2026, 5, 24, 3, 15, tzinfo=UTC)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLlm:
    def __init__(self, content: str) -> None:
        self.content = content
        self.prompts: list[str] = []

    async def ainvoke(self, input: str) -> FakeResponse:
        self.prompts.append(input)
        return FakeResponse(self.content)


def _incident() -> Incident:
    return Incident(
        id="cnc-out-of-tolerance-2026-05-24",
        summary="CNC line 2 producing out-of-tolerance parts after hydraulic service.",
        observed_at=_OBSERVED_AT,
        symptoms=["audible bearing chatter", "dimensional drift above 0.05mm"],
        affected_assets=["cnc-line-2", "spindle-04"],
    )


def _findings() -> list[Finding]:
    return [
        Finding(
            investigator_domain="mechanical",
            claim="Bearing chatter and brinelling indicate a spindle bearing fault.",
            confidence=0.82,
            citations=["mech-bearing-001"],
        ),
        Finding(
            investigator_domain="mechanical",
            claim="Hydraulic cylinder service preceded the bearing chatter onset.",
            confidence=0.71,
            citations=["mech-hydraulic-014", "data/domains/mechanical/service_log.md"],
        ),
    ]


def _state() -> ExpertViewState:
    return {
        "incident": _incident(),
        "findings": _findings(),
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }


_FAKE_LLM_JSON = """
{
  "incident_id": "cnc-out-of-tolerance-2026-05-24",
  "top_hypotheses": [
    {
      "id": "hyp-spindle-bearing-fault",
      "claim": "Spindle bearing damage from hydraulic service caused the drift.",
      "supporting_findings": [
        {
          "investigator_domain": "mechanical",
          "claim": "Bearing chatter and brinelling indicate a spindle bearing fault.",
          "confidence": 0.82,
          "citations": ["mech-bearing-001"]
        },
        {
          "investigator_domain": "mechanical",
          "claim": "Hydraulic cylinder service preceded the bearing chatter onset.",
          "confidence": 0.71,
          "citations": ["mech-hydraulic-014", "data/domains/mechanical/service_log.md"]
        }
      ],
      "confidence": 0.78,
      "domain_origin": "mechanical"
    }
  ],
  "causal_chain": [],
  "confidence_summary": "Mechanical findings point to a spindle bearing fault from recent service."
}
"""


@pytest.mark.asyncio
async def test_synthesizer_returns_causal_report_patch() -> None:
    llm = FakeLlm(_FAKE_LLM_JSON)
    node = make_synthesizer_node(llm)

    patch = await node(_state())

    assert set(patch) == {"causal_report"}
    report = patch["causal_report"]
    assert isinstance(report, CausalReport)
    assert report.incident_id == "cnc-out-of-tolerance-2026-05-24"
    assert len(report.top_hypotheses) >= 1

    input_citations = {citation for finding in _findings() for citation in finding.citations}
    surfaced_citations = {
        citation
        for hypothesis in report.top_hypotheses
        for supporting in hypothesis.supporting_findings
        for citation in supporting.citations
    }
    assert input_citations & surfaced_citations, (
        "At least one input citation must surface in Hypothesis.supporting_findings."
    )

    rendered_prompt = llm.prompts[0]
    assert "cnc-out-of-tolerance-2026-05-24" in rendered_prompt
    assert "mech-bearing-001" in rendered_prompt
    assert "mech-hydraulic-014" in rendered_prompt


@pytest.mark.asyncio
async def test_synthesizer_strips_markdown_json_fence() -> None:
    fenced = f"```json\n{_FAKE_LLM_JSON.strip()}\n```"
    node = make_synthesizer_node(FakeLlm(fenced))

    patch = await node(_state())

    report = patch["causal_report"]
    assert isinstance(report, CausalReport)
    assert report.incident_id == "cnc-out-of-tolerance-2026-05-24"


@pytest.mark.asyncio
async def test_synthesizer_rejects_mismatched_incident_id() -> None:
    mismatched_json = _FAKE_LLM_JSON.replace(
        "cnc-out-of-tolerance-2026-05-24",
        "wrong-incident-id",
    )
    node = make_synthesizer_node(FakeLlm(mismatched_json))

    with pytest.raises(ValueError, match="incident_id must match"):
        await node(_state())


@pytest.mark.asyncio
async def test_synthesizer_rejects_empty_hypotheses() -> None:
    empty_json = """
    {
      "incident_id": "cnc-out-of-tolerance-2026-05-24",
      "top_hypotheses": [],
      "causal_chain": [],
      "confidence_summary": "No supportable hypothesis emerged."
    }
    """
    node = make_synthesizer_node(FakeLlm(empty_json))

    with pytest.raises(ValueError, match="at least one hypothesis"):
        await node(_state())
