"""Unit tests for the spawned sub-investigator node contract."""

from datetime import UTC, datetime

import pytest

from expertview.agents.investigators.sub_investigator import make_sub_investigator_node
from expertview.evidence.models import Document, Finding, Incident
from expertview.orchestration.state import ExpertViewState

_OBSERVED_AT = datetime(2026, 5, 24, 22, 40, tzinfo=UTC)
_PARENT_CLAIM = "Warm runout growth points to bearing preload loss on spindle-04."


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


def _parent_finding() -> Finding:
    return Finding(
        investigator_domain="mechanical",
        claim=_PARENT_CLAIM,
        confidence=0.82,
        citations=["mech-service-note-spindle-bearing-preload"],
    )


def _state() -> ExpertViewState:
    return {
        "incident": _incident(),
        "findings": [
            Finding(
                investigator_domain="process",
                claim="Bore diameter drift exceeded the reaction rule.",
                confidence=0.74,
                citations=["process-control-plan"],
            ),
            _parent_finding(),
        ],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }


def _document() -> Document:
    return Document(
        id="supplier-audit-log-bearing-supplier-north-2026-q1",
        content="The audit kept grease-film comparison under monitored status.",
        source=("data/domains/supply_chain/supplier-audit-log-bearing-supplier-north-2026-q1.md"),
        domain="supply_chain",
        metadata={"supplier": "Bearing Supplier - North"},
    )


@pytest.mark.asyncio
async def test_sub_investigator_returns_valid_findings_patch() -> None:
    document = _document()
    store = FakeStore([document])
    llm = FakeLlm(
        """
        [
          {
            "investigator_domain": "supply_chain",
            "claim": "Bearing Supplier - North retained monitored grease-film controls.",
            "confidence": 0.78,
            "citations": ["supplier-audit-log-bearing-supplier-north-2026-q1"]
          }
        ]
        """
    )

    node = make_sub_investigator_node("supply_chain", store, llm, k=2)
    patch = await node(_state())

    assert set(patch) == {"findings"}
    findings = patch["findings"]
    assert len(findings) == 1
    assert all(isinstance(finding, Finding) for finding in findings)
    assert findings[0].investigator_domain == "supply_chain"
    assert findings[0].citations == ["supplier-audit-log-bearing-supplier-north-2026-q1"]
    assert store.queries == [
        (
            _PARENT_CLAIM
            + " CNC line 2 producing out-of-tolerance parts after bearing batch change."
            + " audible bearing chatter dimensional drift above 0.05mm"
            + " cnc-line-2 spindle-04 supplier qualification audit prior batch bearing history",
            2,
        )
    ]
    assert _PARENT_CLAIM in llm.prompts[0]
    assert "supplier-audit-log-bearing-supplier-north-2026-q1" in llm.prompts[0]


@pytest.mark.asyncio
async def test_sub_investigator_strips_markdown_json_fence() -> None:
    node = make_sub_investigator_node(
        "supply_chain",
        FakeStore([_document()]),
        FakeLlm(
            "```json\n"
            "[\n"
            "  {\n"
            '    "investigator_domain": "supply_chain",\n'
            '    "claim": "Fenced output should still parse cleanly.",\n'
            '    "confidence": 0.6,\n'
            '    "citations": ["supplier-audit-log-bearing-supplier-north-2026-q1"]\n'
            "  }\n"
            "]\n"
            "```"
        ),
    )

    patch = await node(_state())

    findings = patch["findings"]
    assert len(findings) == 1
    assert findings[0].citations == ["supplier-audit-log-bearing-supplier-north-2026-q1"]


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
                "investigator_domain": "sub_investigator",
                "claim": "The spawned node must still emit supply-chain findings.",
                "confidence": 0.5,
                "citations": ["supplier-audit-log-bearing-supplier-north-2026-q1"]
              }
            ]
            """,
            "domain",
        ),
    ],
)
async def test_sub_investigator_rejects_invalid_findings(
    content: str,
    message: str,
) -> None:
    node = make_sub_investigator_node(
        "supply_chain",
        FakeStore([_document()]),
        FakeLlm(content),
    )

    with pytest.raises(ValueError, match=message):
        await node(_state())
