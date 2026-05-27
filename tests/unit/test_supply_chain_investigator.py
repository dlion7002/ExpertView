"""Unit tests for the supply-chain investigator node contract."""

from datetime import UTC, datetime

import pytest

from expertview.agents.investigators.supply_chain import (
    make_supply_chain_investigator_node,
)
from expertview.evidence.models import Document, Finding, Incident
from expertview.orchestration.state import ExpertViewState

_OBSERVED_AT = datetime(2026, 5, 24, 22, 40, tzinfo=UTC)


class FakeStore:
    domain = "supply_chain"

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
        summary="CNC line 2 producing out-of-tolerance parts after bearing batch change.",
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
        id="receiving-qa-bearing-batch-b-227",
        content="Batch B-227 was released for controlled use with asset traceability.",
        source="data/domains/supply_chain/receiving-qa-bearing-batch-b-227.md",
        domain="supply_chain",
        metadata={"batch": "B-227"},
    )


@pytest.mark.asyncio
async def test_supply_chain_investigator_returns_valid_findings_patch() -> None:
    document = _document()
    store = FakeStore([document])
    llm = FakeLlm(
        """
        [
          {
            "investigator_domain": "supply_chain",
            "claim": "Batch B-227 was released under controlled-use traceability.",
            "confidence": 0.84,
            "citations": ["receiving-qa-bearing-batch-b-227"]
          }
        ]
        """
    )

    node = make_supply_chain_investigator_node(store, llm, k=3)
    patch = await node(_state())

    assert set(patch) == {"findings"}
    findings = patch["findings"]
    assert len(findings) == 1
    assert all(isinstance(finding, Finding) for finding in findings)
    assert findings[0].investigator_domain == "supply_chain"
    assert findings[0].citations == ["receiving-qa-bearing-batch-b-227"]
    assert store.queries == [
        (
            "CNC line 2 producing out-of-tolerance parts after bearing batch change. "
            "audible bearing chatter dimensional drift above 0.05mm cnc-line-2 spindle-04",
            3,
        )
    ]
    assert "receiving-qa-bearing-batch-b-227" in llm.prompts[0]
    assert "audible bearing chatter" in llm.prompts[0]


@pytest.mark.asyncio
async def test_supply_chain_investigator_strips_markdown_json_fence() -> None:
    document = _document()
    store = FakeStore([document])
    llm = FakeLlm(
        "```json\n"
        "[\n"
        "  {\n"
        '    "investigator_domain": "supply_chain",\n'
        '    "claim": "Fenced output should still parse cleanly.",\n'
        '    "confidence": 0.6,\n'
        '    "citations": ["receiving-qa-bearing-batch-b-227"]\n'
        "  }\n"
        "]\n"
        "```"
    )

    node = make_supply_chain_investigator_node(store, llm, k=3)
    patch = await node(_state())

    findings = patch["findings"]
    assert len(findings) == 1
    assert findings[0].citations == ["receiving-qa-bearing-batch-b-227"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            """
            [
              {
                "investigator_domain": "supply_chain",
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
                "investigator_domain": "supply_chain",
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
                "investigator_domain": "mechanical",
                "claim": "A finding from another domain is invalid.",
                "confidence": 0.5,
                "citations": ["receiving-qa-bearing-batch-b-227"]
              }
            ]
            """,
            "domain",
        ),
    ],
)
async def test_supply_chain_investigator_rejects_invalid_findings(
    content: str,
    message: str,
) -> None:
    node = make_supply_chain_investigator_node(FakeStore([_document()]), FakeLlm(content))

    with pytest.raises(ValueError, match=message):
        await node(_state())
