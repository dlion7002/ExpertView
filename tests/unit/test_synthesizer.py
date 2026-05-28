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
    """Returns scripted responses in call order; repeats the last once exhausted.

    The synthesizer now makes two passes (draft, then reasoning). Error-path tests
    that fail in the first pass never request the second, so a single-response
    construction still works for them; happy-path tests script both responses.
    """

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    async def ainvoke(self, input: str) -> FakeResponse:
        index = min(len(self.prompts), len(self.responses) - 1)
        self.prompts.append(input)
        return FakeResponse(self.responses[index])


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


_FAKE_REASONING_JSON = (
    '{"verdict_reasoning": '
    '"Bearing chatter and brinelling, set against the hydraulic-service timeline, '
    'point to a spindle bearing fault as the originating cause of the dimensional drift.", '
    '"alternatives_summary": '
    '"No competing originating cause surfaced; the remaining findings describe '
    'the same mechanical chain rather than an independent root cause."}'
)


@pytest.mark.asyncio
async def test_synthesizer_returns_causal_report_patch() -> None:
    llm = FakeLlm(_FAKE_LLM_JSON, _FAKE_REASONING_JSON)
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
async def test_synthesizer_populates_grounded_reasoning() -> None:
    llm = FakeLlm(_FAKE_LLM_JSON, _FAKE_REASONING_JSON)
    node = make_synthesizer_node(llm)

    report = (await node(_state()))["causal_report"]

    assert report.verdict_reasoning.startswith("Bearing chatter")
    assert "competing originating cause" in report.alternatives_summary

    # The reasoning pass is the *second* call and is grounded in the re-scored
    # report (final confidence + ranking basis) and the full findings list.
    assert len(llm.prompts) == 2
    reasoning_prompt = llm.prompts[1]
    assert "confidence" in reasoning_prompt.lower()
    assert report.top_hypotheses[0].claim in reasoning_prompt
    assert "mech-bearing-001" in reasoning_prompt


@pytest.mark.asyncio
async def test_synthesizer_accepts_empty_alternatives_summary() -> None:
    reasoning = '{"verdict_reasoning": "One clear originating cause.", "alternatives_summary": ""}'
    node = make_synthesizer_node(FakeLlm(_FAKE_LLM_JSON, reasoning))

    report = (await node(_state()))["causal_report"]

    assert report.verdict_reasoning == "One clear originating cause."
    assert report.alternatives_summary == ""


@pytest.mark.asyncio
async def test_synthesizer_rejects_malformed_reasoning() -> None:
    node = make_synthesizer_node(FakeLlm(_FAKE_LLM_JSON, "not a reasoning object"))

    with pytest.raises(ValueError):
        await node(_state())


@pytest.mark.asyncio
async def test_synthesizer_strips_markdown_json_fence() -> None:
    fenced_report = f"```json\n{_FAKE_LLM_JSON.strip()}\n```"
    fenced_reasoning = f"```json\n{_FAKE_REASONING_JSON.strip()}\n```"
    node = make_synthesizer_node(FakeLlm(fenced_report, fenced_reasoning))

    patch = await node(_state())

    report = patch["causal_report"]
    assert isinstance(report, CausalReport)
    assert report.incident_id == "cnc-out-of-tolerance-2026-05-24"
    assert report.verdict_reasoning.startswith("Bearing chatter")


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
