"""Unit tests for the process investigator node contract."""

from datetime import UTC, datetime

import pytest

from expertview.agents.investigators.process import make_process_investigator_node
from expertview.evidence.models import Document, Finding, Incident
from expertview.orchestration.state import ExpertViewState

_OBSERVED_AT = datetime(2026, 5, 24, 22, 40, tzinfo=UTC)


class FakeStore:
    domain = "process"

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
        symptoms=["missing part-10 restart inspection", "dimensional drift above 0.05mm"],
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
        id="inspection-log-line-2-2026-05-24-shift-3",
        content=(
            "The part-10 restart check was not recorded before production continued to part 17."
        ),
        source="data/domains/process/inspection-log-line-2-2026-05-24-shift-3.md",
        domain="process",
        metadata={"asset": "cnc-line-2-cnc-04"},
    )


@pytest.mark.asyncio
async def test_process_investigator_returns_valid_findings_patch() -> None:
    document = _document()
    store = FakeStore([document])
    llm = FakeLlm(
        """
        [
          {
            "investigator_domain": "process",
            "claim": "The controlled restart sequence was not completed before release.",
            "confidence": 0.84,
            "citations": ["inspection-log-line-2-2026-05-24-shift-3"]
          }
        ]
        """
    )

    node = make_process_investigator_node(store, llm, k=3)
    patch = await node(_state())

    assert set(patch) == {"findings"}
    findings = patch["findings"]
    assert len(findings) == 1
    assert all(isinstance(finding, Finding) for finding in findings)
    assert findings[0].investigator_domain == "process"
    assert findings[0].citations == ["inspection-log-line-2-2026-05-24-shift-3"]
    assert store.queries == [
        (
            "CNC line 2 producing out-of-tolerance parts after hydraulic service. "
            "missing part-10 restart inspection dimensional drift above 0.05mm "
            "cnc-line-2 cnc-line-2-cnc-04",
            3,
        )
    ]
    assert "inspection-log-line-2-2026-05-24-shift-3" in llm.prompts[0]
    assert "missing part-10 restart inspection" in llm.prompts[0]


@pytest.mark.asyncio
async def test_process_investigator_strips_markdown_json_fence() -> None:
    document = _document()
    store = FakeStore([document])
    llm = FakeLlm(
        "```json\n"
        "[\n"
        "  {\n"
        '    "investigator_domain": "process",\n'
        '    "claim": "Fenced output should still parse cleanly.",\n'
        '    "confidence": 0.6,\n'
        '    "citations": ["inspection-log-line-2-2026-05-24-shift-3"]\n'
        "  }\n"
        "]\n"
        "```"
    )

    node = make_process_investigator_node(store, llm, k=3)
    patch = await node(_state())

    findings = patch["findings"]
    assert len(findings) == 1
    assert findings[0].investigator_domain == "process"
    assert findings[0].citations == ["inspection-log-line-2-2026-05-24-shift-3"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            """
            [
              {
                "investigator_domain": "process",
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
                "investigator_domain": "process",
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
async def test_process_investigator_rejects_invalid_citations(
    content: str,
    message: str,
) -> None:
    node = make_process_investigator_node(FakeStore([_document()]), FakeLlm(content))

    with pytest.raises(ValueError, match=message):
        await node(_state())
