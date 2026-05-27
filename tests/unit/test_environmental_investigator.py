"""Unit tests for the environmental investigator node contract."""

from datetime import UTC, datetime

import pytest

from expertview.agents.investigators.environmental import (
    make_environmental_investigator_node,
)
from expertview.evidence.models import Document, Finding, Incident
from expertview.orchestration.state import ExpertViewState

_OBSERVED_AT = datetime(2026, 5, 24, 22, 40, tzinfo=UTC)


class FakeStore:
    domain = "environmental"

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
        symptoms=["short temperature spike", "dimensional drift above 0.05mm"],
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


def _spec_document() -> Document:
    return Document(
        id="environmental-spec-operating-envelopes",
        content="Ambient temperature near CNC-04 is normal from 19.0 C to 25.0 C.",
        source="data/domains/environmental/environmental-spec-operating-envelopes.md",
        domain="environmental",
        metadata={"asset": "cnc-line-2-cnc-04"},
    )


def _reading_document() -> Document:
    return Document(
        id="ambient-temp-humidity-line-2-shift-3",
        content="The 22:25 temperature spike reached 24.2 C and cleared before the hold.",
        source="data/domains/environmental/ambient-temp-humidity-line-2-shift-3.md",
        domain="environmental",
        metadata={"asset": "cnc-line-2-cnc-04"},
    )


@pytest.mark.asyncio
async def test_environmental_investigator_returns_valid_findings_patch() -> None:
    document = _reading_document()
    store = FakeStore([document])
    llm = FakeLlm(
        """
        [
          {
            "investigator_domain": "environmental",
            "claim": "A short ambient temperature spike occurred before the quality hold.",
            "confidence": 0.38,
            "citations": ["ambient-temp-humidity-line-2-shift-3"]
          }
        ]
        """
    )

    node = make_environmental_investigator_node(store, llm, k=3)
    patch = await node(_state())

    assert set(patch) == {"findings"}
    findings = patch["findings"]
    assert len(findings) == 1
    assert all(isinstance(finding, Finding) for finding in findings)
    assert findings[0].investigator_domain == "environmental"
    assert findings[0].citations == ["ambient-temp-humidity-line-2-shift-3"]
    assert store.queries == [
        (
            "CNC line 2 producing out-of-tolerance parts after hydraulic service. "
            "short temperature spike dimensional drift above 0.05mm "
            "cnc-line-2 cnc-line-2-cnc-04",
            3,
        )
    ]
    assert "ambient-temp-humidity-line-2-shift-3" in llm.prompts[0]
    assert "short temperature spike" in llm.prompts[0]


@pytest.mark.asyncio
async def test_environmental_investigator_strips_markdown_json_fence() -> None:
    document = _reading_document()
    store = FakeStore([document])
    llm = FakeLlm(
        "```json\n"
        "[\n"
        "  {\n"
        '    "investigator_domain": "environmental",\n'
        '    "claim": "Fenced output should still parse cleanly.",\n'
        '    "confidence": 0.6,\n'
        '    "citations": ["ambient-temp-humidity-line-2-shift-3"]\n'
        "  }\n"
        "]\n"
        "```"
    )

    node = make_environmental_investigator_node(store, llm, k=3)
    patch = await node(_state())

    findings = patch["findings"]
    assert len(findings) == 1
    assert findings[0].investigator_domain == "environmental"
    assert findings[0].citations == ["ambient-temp-humidity-line-2-shift-3"]


@pytest.mark.asyncio
async def test_environmental_investigator_accepts_negative_evidence_finding() -> None:
    spec = _spec_document()
    reading = _reading_document()
    store = FakeStore([spec, reading])
    llm = FakeLlm(
        """
        [
          {
            "investigator_domain": "environmental",
            "claim": "Readings stayed in envelope; environmental cause is unsupported.",
            "confidence": 0.18,
            "citations": [
              "environmental-spec-operating-envelopes",
              "ambient-temp-humidity-line-2-shift-3"
            ]
          }
        ]
        """
    )

    node = make_environmental_investigator_node(store, llm, k=5)
    patch = await node(_state())

    findings = patch["findings"]
    assert len(findings) == 1
    assert findings[0].confidence < 0.3
    assert findings[0].citations == [
        "environmental-spec-operating-envelopes",
        "ambient-temp-humidity-line-2-shift-3",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            """
            [
              {
                "investigator_domain": "environmental",
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
                "investigator_domain": "environmental",
                "claim": "A finding with an unknown citation is invalid.",
                "confidence": 0.5,
                "citations": ["not-a-retrieved-document"]
              }
            ]
            """,
            "retrieved document ids or sources",
        ),
    ],
)
async def test_environmental_investigator_rejects_invalid_citations(
    content: str,
    message: str,
) -> None:
    node = make_environmental_investigator_node(FakeStore([_reading_document()]), FakeLlm(content))

    with pytest.raises(ValueError, match=message):
        await node(_state())
