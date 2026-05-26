"""Unit tests for the mechanical investigator node contract."""

from datetime import UTC, datetime

import pytest

from expertview.agents.investigators.mechanical import make_mechanical_investigator_node
from expertview.evidence.models import Document, Finding, Incident
from expertview.orchestration.state import ExpertViewState

_OBSERVED_AT = datetime(2026, 5, 24, 3, 15, tzinfo=UTC)


class FakeStore:
    domain = "mechanical"

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
        symptoms=["audible bearing chatter", "dimensional drift above 0.05mm"],
        affected_assets=["cnc-line-2", "spindle-04"],
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
        id="mech-bearing-001",
        content="Spindle bearing inspection found brinelling after hydraulic cylinder service.",
        source="data/domains/mechanical/bearing_inspection.md",
        domain="mechanical",
        metadata={"asset": "spindle-04"},
    )


@pytest.mark.asyncio
async def test_mechanical_investigator_returns_valid_findings_patch() -> None:
    document = _document()
    store = FakeStore([document])
    llm = FakeLlm(
        """
        [
          {
            "investigator_domain": "mechanical",
            "claim": "Bearing chatter and brinelling indicate a spindle bearing fault.",
            "confidence": 0.82,
            "citations": ["mech-bearing-001"]
          }
        ]
        """
    )

    node = make_mechanical_investigator_node(store, llm, k=3)
    patch = await node(_state())

    assert set(patch) == {"findings"}
    findings = patch["findings"]
    assert len(findings) == 1
    assert all(isinstance(finding, Finding) for finding in findings)
    assert findings[0].citations == ["mech-bearing-001"]
    assert store.queries == [
        (
            "CNC line 2 producing out-of-tolerance parts after hydraulic service. "
            "audible bearing chatter dimensional drift above 0.05mm cnc-line-2 spindle-04",
            3,
        )
    ]
    assert "mech-bearing-001" in llm.prompts[0]
    assert "audible bearing chatter" in llm.prompts[0]


@pytest.mark.asyncio
async def test_mechanical_investigator_strips_markdown_json_fence() -> None:
    document = _document()
    store = FakeStore([document])
    llm = FakeLlm(
        "```json\n"
        "[\n"
        "  {\n"
        '    "investigator_domain": "mechanical",\n'
        '    "claim": "Fenced output should still parse cleanly.",\n'
        '    "confidence": 0.6,\n'
        '    "citations": ["mech-bearing-001"]\n'
        "  }\n"
        "]\n"
        "```"
    )

    node = make_mechanical_investigator_node(store, llm, k=3)
    patch = await node(_state())

    findings = patch["findings"]
    assert len(findings) == 1
    assert findings[0].citations == ["mech-bearing-001"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            """
            [
              {
                "investigator_domain": "mechanical",
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
                "investigator_domain": "mechanical",
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
async def test_mechanical_investigator_rejects_invalid_citations(
    content: str,
    message: str,
) -> None:
    node = make_mechanical_investigator_node(FakeStore([_document()]), FakeLlm(content))

    with pytest.raises(ValueError, match=message):
        await node(_state())
