"""Unit tests for the human-factors investigator node contract."""

from datetime import UTC, datetime

import pytest

from expertview.agents.investigators.human_factors import (
    make_human_factors_investigator_node,
)
from expertview.evidence.models import Document, Finding, Incident
from expertview.orchestration.state import ExpertViewState

_OBSERVED_AT = datetime(2026, 5, 24, 22, 40, tzinfo=UTC)


class FakeStore:
    domain = "human_factors"

    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, k: int = 5) -> list[Document]:
        self.queries.append((query, k))
        return self.documents


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
        symptoms=["lean shift 3 coverage", "dimensional drift above 0.05mm"],
        affected_assets=["cnc-line-2", "cnc-line-2-cnc-04"],
    )


def _state() -> ExpertViewState:
    return {
        "incident": _incident(),
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }


def _document() -> Document:
    return Document(
        id="handover-shift-2-to-3-incident-day",
        content=(
            "The shift handover listed hydraulic service but did not flag the "
            "line as remaining in restart verification status."
        ),
        source="data/domains/human_factors/handover-shift-2-to-3-incident-day.md",
        domain="human_factors",
        metadata={"asset": "cnc-line-2-cnc-04"},
    )


@pytest.mark.asyncio
async def test_human_factors_investigator_returns_valid_findings_patch() -> None:
    document = _document()
    store = FakeStore([document])
    llm = FakeLlm(
        """
        [
          {
            "investigator_domain": "human_factors",
            "claim": "The handover did not clearly preserve restart-verification status.",
            "confidence": 0.82,
            "citations": ["handover-shift-2-to-3-incident-day"]
          }
        ]
        """
    )

    node = make_human_factors_investigator_node(store, llm, k=3)
    patch = await node(_state())

    assert set(patch) == {"findings"}
    findings = patch["findings"]
    assert len(findings) == 1
    assert all(isinstance(finding, Finding) for finding in findings)
    assert findings[0].investigator_domain == "human_factors"
    assert findings[0].citations == ["handover-shift-2-to-3-incident-day"]
    assert store.queries == [
        (
            "CNC line 2 producing out-of-tolerance parts after hydraulic service. "
            "lean shift 3 coverage dimensional drift above 0.05mm "
            "cnc-line-2 cnc-line-2-cnc-04",
            3,
        )
    ]
    assert "handover-shift-2-to-3-incident-day" in llm.prompts[0]
    assert "lean shift 3 coverage" in llm.prompts[0]
    assert "system-level factors" in llm.prompts[0]


@pytest.mark.asyncio
async def test_human_factors_investigator_strips_markdown_json_fence() -> None:
    document = _document()
    store = FakeStore([document])
    llm = FakeLlm(
        "```json\n"
        "[\n"
        "  {\n"
        '    "investigator_domain": "human_factors",\n'
        '    "claim": "Fenced output should still parse cleanly.",\n'
        '    "confidence": 0.6,\n'
        '    "citations": ["handover-shift-2-to-3-incident-day"]\n'
        "  }\n"
        "]\n"
        "```"
    )

    node = make_human_factors_investigator_node(store, llm, k=3)
    patch = await node(_state())

    findings = patch["findings"]
    assert len(findings) == 1
    assert findings[0].investigator_domain == "human_factors"
    assert findings[0].citations == ["handover-shift-2-to-3-incident-day"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            """
            [
              {
                "investigator_domain": "human_factors",
                "claim": "A finding without citations is invalid.",
                "confidence": 0.5,
                "citations": []
              }
            ]
            """,
            "at least one citation",
        ),
        (
            """
            [
              {
                "investigator_domain": "human_factors",
                "claim": "A finding with an unknown citation is invalid.",
                "confidence": 0.5,
                "citations": ["not-a-retrieved-document"]
              }
            ]
            """,
            "retrieved document ids or sources",
        ),
        (
            """
            [
              {
                "investigator_domain": "process",
                "claim": "A finding with the wrong domain is invalid.",
                "confidence": 0.5,
                "citations": ["handover-shift-2-to-3-incident-day"]
              }
            ]
            """,
            "must use domain",
        ),
    ],
)
async def test_human_factors_investigator_rejects_invalid_findings(
    content: str,
    message: str,
) -> None:
    node = make_human_factors_investigator_node(FakeStore([_document()]), FakeLlm(content))

    with pytest.raises(ValueError, match=message):
        await node(_state())
