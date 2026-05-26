# Evidence Models And Shared State

## Purpose

This guide explains the Phase 1 data contract. The evidence models define every payload that can cross agent boundaries, and `ExpertViewState` defines the LangGraph shared state that later nodes read and patch.

## Flow Summary

1. An incident or future graph run starts with an `Incident` model.
2. Domain investigators will later produce `Finding` and `Hypothesis` models.
3. The synthesizer will later produce a `CausalReport` containing `CausalLink` objects.
4. `ExpertViewState` carries those models through LangGraph.
5. Reducers on list fields make future parallel branch merges additive instead of last-writer-wins.
6. Unit tests verify JSON round trips, validation rules, and reducer annotations.

## Relevant Files

- `src/expertview/evidence/models.py`: pydantic v2 cross-agent data models.
- `src/expertview/orchestration/state.py`: LangGraph shared state schema.
- `tests/unit/test_schemas.py`: serialization and validation tests for evidence models.
- `tests/unit/test_state.py`: state smoke tests and reducer checks.
- `src/expertview/rag/base.py`: imports `Document`.
- `src/expertview/agents/base.py`: imports `Incident`, `Finding`, `Hypothesis`, and `CausalReport`.
- `src/expertview/orchestration/runner.py`: compiles a graph over `ExpertViewState`.

## Step 1 - Cross-Agent Payload Models

### Location

`src/expertview/evidence/models.py`

### Code

```python
"""Cross-agent payload schemas.

Architecture rule: every value crossing an agent boundary or living on the
LangGraph shared state is one of these models — never a raw dict. See
`ProjectDocs/architecture.md` §3 and §5.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

# frozen=True on every model: cross-agent payloads are immutable post-creation.
# Concurrent investigator branches merge by list concatenation via the
# `operator.add` reducer in `orchestration/state.py`, which builds new lists
# rather than mutating fields. See ProjectDocs/architecture.md sections 5-6.
_CROSS_AGENT_CONFIG = ConfigDict(frozen=True)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Document(BaseModel):
    model_config = _CROSS_AGENT_CONFIG

    id: str
    content: str
    source: str
    domain: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    model_config = _CROSS_AGENT_CONFIG

    id: str
    summary: str
    observed_at: datetime
    symptoms: list[str] = Field(default_factory=list)
    affected_assets: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    model_config = _CROSS_AGENT_CONFIG

    investigator_domain: str
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[str] = Field(default_factory=list)
    raised_at: datetime = Field(default_factory=_utc_now)


class Hypothesis(BaseModel):
    model_config = _CROSS_AGENT_CONFIG

    # Stable id so CausalLink.cause / effect can reference hypotheses across
    # the synthesizer's output without relying on object identity.
    id: str = Field(default_factory=lambda: str(uuid4()))
    claim: str
    supporting_findings: list[Finding] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    domain_origin: str


class Symptom(BaseModel):
    model_config = _CROSS_AGENT_CONFIG

    description: str
    observed_at: datetime | None = None


class CausalLink(BaseModel):
    model_config = _CROSS_AGENT_CONFIG

    cause: Hypothesis
    # Effect can be another Hypothesis (cause-of-cause chain) or a raw Symptom
    # (terminal observable). Per architecture.md §3.
    effect: Hypothesis | Symptom
    strength: float = Field(ge=0.0, le=1.0)
    rationale: str


class CausalReport(BaseModel):
    model_config = _CROSS_AGENT_CONFIG

    incident_id: str
    top_hypotheses: list[Hypothesis] = Field(default_factory=list)
    causal_chain: list[CausalLink] = Field(default_factory=list)
    confidence_summary: str
    generated_at: datetime = Field(default_factory=_utc_now)
```

### What it does

The file defines the data vocabulary for the project.

- `Document`: the project's RAG document shape, not LangChain's native document type.
- `Incident`: the input scenario shape.
- `Finding`: a claim from an investigator, with citations and confidence.
- `Hypothesis`: a possible cause, linked to supporting findings.
- `Symptom`: an observable effect.
- `CausalLink`: a cause-effect connection between hypotheses or symptoms.
- `CausalReport`: the final synthesizer output.

All models use `ConfigDict(frozen=True)`, so payloads are immutable after creation. This supports the later LangGraph merge model where branches return new state patches instead of mutating shared objects.

### What it receives or depends on

- `pydantic.BaseModel`, `ConfigDict`, and `Field`.
- `datetime` for timestamps.
- `uuid4` for default hypothesis IDs.

### What it produces or changes

It produces immutable pydantic objects that are passed through protocols, RAG stores, tests, and graph state.

### What it connects to

- `orchestration/state.py`: imports these models into `ExpertViewState`.
- `rag/base.py` and `rag/inmemory.py`: use `Document`.
- `agents/base.py`: uses `Incident`, `Finding`, `Hypothesis`, and `CausalReport`.
- `tests/unit/test_schemas.py`: verifies serialization and validation.

### Why it matters

This is the core boundary contract. If these shapes drift, every investigator, RAG loader, synthesizer, and graph state patch can break.

## Step 2 - LangGraph Shared State

### Location

`src/expertview/orchestration/state.py`

### Code

```python
"""LangGraph shared-state schema.

`ExpertViewState` is the one allowed non-pydantic cross-node type in the
codebase (per CLAUDE.md). The list-typed fields use the `operator.add`
reducer so concurrent investigator branches merge by list concatenation
when they emit state patches simultaneously via the LangGraph Send API.
"""

import operator
from typing import Annotated, TypedDict

from expertview.evidence.models import (
    CausalReport,
    Finding,
    Hypothesis,
    Incident,
)


class ExpertViewState(TypedDict):
    incident: Incident
    # operator.add reducer = list concatenation across parallel branches.
    # Without it, the 5-way investigator fan-out would silently last-writer-win.
    findings: Annotated[list[Finding], operator.add]
    hypotheses: Annotated[list[Hypothesis], operator.add]
    spawned_subinvestigations: Annotated[list[str], operator.add]
    # Single-writer (synthesizer); no reducer.
    causal_report: CausalReport | None
```

### What it does

`ExpertViewState` is the state schema passed to LangGraph's `StateGraph`. It is the only non-pydantic cross-node type because LangGraph expects a state mapping.

The list fields are annotated with `operator.add`. LangGraph reads those reducer annotations when merging state patches from concurrent branches. That means later investigator branches can all return `{"findings": [...]}` and LangGraph will concatenate the lists.

`causal_report` has no reducer because the synthesizer should be the only writer.

### What it receives or depends on

- Evidence models from `src/expertview/evidence/models.py`.
- `typing.Annotated` for reducer metadata.
- `operator.add` as the reducer.

### What it produces or changes

It produces the shared state contract consumed by `StateGraph(ExpertViewState)` in `runner.py`.

### What it connects to

- `orchestration/runner.py`: builds the graph over this state.
- Future investigator nodes: will return patches for `findings`, `hypotheses`, or `spawned_subinvestigations`.
- Future synthesizer node: will return a patch for `causal_report`.
- `tests/unit/test_state.py`: verifies reducer metadata and basic state shape.

### Why it matters

This file is the bridge between pydantic payloads and LangGraph execution. It controls how parallel work merges.

## Step 3 - Schema Round-Trip And Validation Tests

### Location

`tests/unit/test_schemas.py`

### Code

```python
"""JSON round-trip + boundary-validation tests for the cross-agent schemas.

The round-trip pattern (build → model_dump_json → model_validate_json →
equality) is the anti-drift mechanism behind the architecture rule that
forbids raw dicts across agent boundaries. If a future schema change breaks
serialization, these tests fail immediately rather than at the next demo
rehearsal.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from expertview.evidence.models import (
    CausalLink,
    CausalReport,
    Document,
    Finding,
    Hypothesis,
    Incident,
    Symptom,
)

_FIXED_TS = datetime(2026, 5, 25, 14, 30, 0, tzinfo=UTC)


def _roundtrip[T](instance: T) -> T:
    return type(instance).model_validate_json(instance.model_dump_json())


def test_document_roundtrip() -> None:
    doc = Document(
        id="mech-hydraulic-001",
        content="Hydraulic cylinder service log: replaced seal kit on 2026-05-20.",
        source="data/domains/mechanical/hydraulic_service_log.md",
        domain="mechanical",
        metadata={"author": "shift-3-tech", "tags": ["hydraulic", "maintenance"]},
    )
    assert _roundtrip(doc) == doc


def test_incident_roundtrip() -> None:
    incident = Incident(
        id="cnc-out-of-tolerance-2026-05-24",
        summary="CNC line 2 producing out-of-tolerance parts on shift 3.",
        observed_at=_FIXED_TS,
        symptoms=["dimensional drift > 0.05mm", "audible bearing chatter"],
        affected_assets=["cnc-line-2", "spindle-04"],
    )
    assert _roundtrip(incident) == incident


def test_finding_roundtrip() -> None:
    finding = Finding(
        investigator_domain="mechanical",
        claim="Bearing wear pattern consistent with batch-level lubrication shortfall.",
        confidence=0.78,
        citations=["mech-hydraulic-001", "mech-bearing-batch-2026-05"],
        raised_at=_FIXED_TS,
    )
    assert _roundtrip(finding) == finding


def test_hypothesis_roundtrip() -> None:
    finding = Finding(
        investigator_domain="supply_chain",
        claim="New supplier bearing batch arrived 2026-05-18.",
        confidence=0.91,
        citations=["supply-po-44213"],
        raised_at=_FIXED_TS,
    )
    hypothesis = Hypothesis(
        id="hyp-bearing-batch",
        claim="Out-of-spec bearings from new supplier batch are the proximate cause.",
        supporting_findings=[finding],
        confidence=0.74,
        domain_origin="supply_chain",
    )
    assert _roundtrip(hypothesis) == hypothesis


def test_symptom_roundtrip_with_observed_at() -> None:
    symptom = Symptom(
        description="Out-of-tolerance dimension on part X-104.",
        observed_at=_FIXED_TS,
    )
    assert _roundtrip(symptom) == symptom


def test_symptom_roundtrip_without_observed_at() -> None:
    symptom = Symptom(description="Operator reports unusual spindle noise.")
    assert _roundtrip(symptom) == symptom


def _make_hypothesis(claim: str, domain: str, conf: float = 0.7) -> Hypothesis:
    return Hypothesis(
        id=f"hyp-{abs(hash(claim)) % 10_000}",
        claim=claim,
        supporting_findings=[],
        confidence=conf,
        domain_origin=domain,
    )


def test_causal_link_roundtrip_hypothesis_effect() -> None:
    link = CausalLink(
        cause=_make_hypothesis("New supplier batch is out of spec.", "supply_chain", 0.8),
        effect=_make_hypothesis("Spindle bearings degrade prematurely.", "mechanical", 0.7),
        strength=0.65,
        rationale="Out-of-spec bearings reduce service life by an order of magnitude.",
    )
    assert _roundtrip(link) == link


def test_causal_link_roundtrip_symptom_effect() -> None:
    link = CausalLink(
        cause=_make_hypothesis("Spindle bearings degrade prematurely.", "mechanical", 0.7),
        effect=Symptom(description="Dimensional drift > 0.05mm.", observed_at=_FIXED_TS),
        strength=0.82,
        rationale="Worn bearings introduce runout that propagates to part dimensions.",
    )
    assert _roundtrip(link) == link


def test_causal_report_roundtrip() -> None:
    top_hyp = _make_hypothesis("Supplier batch root cause.", "supply_chain", 0.74)
    link = CausalLink(
        cause=top_hyp,
        effect=Symptom(description="Out-of-tolerance parts."),
        strength=0.7,
        rationale="See chain.",
    )
    report = CausalReport(
        incident_id="cnc-out-of-tolerance-2026-05-24",
        top_hypotheses=[top_hyp],
        causal_chain=[link],
        confidence_summary=(
            "Primary cause: supplier-batch bearings (0.74). Secondary: shift handover gap."
        ),
        generated_at=_FIXED_TS,
    )
    assert _roundtrip(report) == report


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, -1.0, 2.0])
def test_finding_rejects_out_of_range_confidence(bad_confidence: float) -> None:
    with pytest.raises(ValidationError):
        Finding(
            investigator_domain="mechanical",
            claim="x",
            confidence=bad_confidence,
            citations=[],
        )


@pytest.mark.parametrize("bad_confidence", [-0.5, 1.5])
def test_hypothesis_rejects_out_of_range_confidence(bad_confidence: float) -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            claim="x",
            supporting_findings=[],
            confidence=bad_confidence,
            domain_origin="mechanical",
        )


@pytest.mark.parametrize("bad_strength", [-0.1, 1.1])
def test_causal_link_rejects_out_of_range_strength(bad_strength: float) -> None:
    cause = _make_hypothesis("a", "mechanical", 0.5)
    effect = _make_hypothesis("b", "process", 0.5)
    with pytest.raises(ValidationError):
        CausalLink(cause=cause, effect=effect, strength=bad_strength, rationale="x")
```

### What it does

These tests prove that each pydantic model can be serialized to JSON and validated back into the same model. They also prove confidence and strength constraints reject invalid values.

### What it connects to

- `models.py`: every class is imported and exercised.
- Future LLM response parsing: when an LLM output is parsed into these models, the same validation constraints apply.

### Why it matters

The models are cross-module contracts. Round-trip tests catch schema drift before it reaches LangGraph or provider code.

## Step 4 - State Shape And Reducer Tests

### Location

`tests/unit/test_state.py`

### Code

```python
"""ExpertViewState smoke + reducer behavior tests.

The reducer assertions guard against the silent-overwrite failure mode the
architecture's `operator.add` annotation is meant to prevent: if a future
edit drops the reducer, the 5-way Phase 3 investigator fan-out would
last-writer-win instead of merging. These tests fail immediately if that
annotation goes missing.
"""

import operator
from datetime import UTC, datetime
from typing import get_type_hints

from expertview.evidence.models import CausalReport, Finding, Incident
from expertview.orchestration.state import ExpertViewState

_FIXED_TS = datetime(2026, 5, 25, 14, 30, 0, tzinfo=UTC)


def _make_incident() -> Incident:
    return Incident(
        id="test-incident",
        summary="Test incident for state smoke.",
        observed_at=_FIXED_TS,
        symptoms=["s1"],
        affected_assets=["asset-1"],
    )


def _make_finding(claim: str, conf: float) -> Finding:
    return Finding(
        investigator_domain="mechanical",
        claim=claim,
        confidence=conf,
        citations=[],
        raised_at=_FIXED_TS,
    )


def test_expertviewstate_accepts_minimal_dict() -> None:
    state: ExpertViewState = {
        "incident": _make_incident(),
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }
    assert state["incident"].id == "test-incident"
    assert state["causal_report"] is None
    assert state["findings"] == []


def test_expertviewstate_accepts_populated_dict() -> None:
    finding = _make_finding("test claim", 0.5)
    state: ExpertViewState = {
        "incident": _make_incident(),
        "findings": [finding],
        "hypotheses": [],
        "spawned_subinvestigations": ["supply-history-sub-001"],
        "causal_report": None,
    }
    assert state["findings"][0].claim == "test claim"
    assert state["spawned_subinvestigations"] == ["supply-history-sub-001"]


def test_findings_reducer_is_operator_add() -> None:
    """The list-typed fields must carry operator.add as Annotated metadata."""
    hints = get_type_hints(ExpertViewState, include_extras=True)
    for field in ("findings", "hypotheses", "spawned_subinvestigations"):
        annotation = hints[field]
        assert hasattr(annotation, "__metadata__"), (
            f"{field} must be Annotated[list, reducer] — found bare {annotation!r}"
        )
        assert operator.add in annotation.__metadata__, (
            f"{field} reducer must be operator.add — found {annotation.__metadata__!r}"
        )


def test_causal_report_field_has_no_reducer() -> None:
    """causal_report is single-writer (synthesizer); accidental reducer would be wrong."""
    hints = get_type_hints(ExpertViewState, include_extras=True)
    annotation = hints["causal_report"]
    assert not hasattr(annotation, "__metadata__"), (
        "causal_report must not carry a reducer — synthesizer is the sole writer."
    )


def test_reducer_merges_concurrent_finding_patches() -> None:
    """Simulate two concurrent investigator branches emitting findings.

    LangGraph applies the Annotated reducer to merge patches. We exercise
    operator.add directly so this test is independent of the LangGraph
    runtime — if the annotation in state.py drops the reducer, the
    sibling test above fails; if operator.add semantics change (impossible,
    but), this test fails.
    """
    branch_a_patch = {"findings": [_make_finding("mechanical bearing anomaly", 0.7)]}
    branch_b_patch = {"findings": [_make_finding("supply-chain batch anomaly", 0.8)]}

    merged = operator.add(branch_a_patch["findings"], branch_b_patch["findings"])

    assert len(merged) == 2
    assert merged[0].claim == "mechanical bearing anomaly"
    assert merged[1].claim == "supply-chain batch anomaly"


def test_causal_report_typed_as_optional() -> None:
    """A pre-synthesis state must validly carry causal_report=None."""
    state: ExpertViewState = {
        "incident": _make_incident(),
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }
    assert state["causal_report"] is None

    report = CausalReport(
        incident_id="test-incident",
        top_hypotheses=[],
        causal_chain=[],
        confidence_summary="empty",
        generated_at=_FIXED_TS,
    )
    state["causal_report"] = report
    assert state["causal_report"].incident_id == "test-incident"
```

### What it does

These tests verify that `ExpertViewState` can carry a minimal pre-synthesis state, a populated state, and an optional final report. They also inspect the type annotations to make sure the reducer metadata is present where needed and absent from `causal_report`.

### What it connects to

- `state.py`: the reducer metadata being inspected.
- `models.py`: `Incident`, `Finding`, and `CausalReport` values used in state.
- Future LangGraph fan-out: the reducer behavior is designed for concurrent branch patches.

### Why it matters

The reducer checks protect the future parallel investigator flow. If someone removes `operator.add`, this test catches it before branch results begin overwriting one another.

## Where To Look Next

After the data contract, the next flow is how domain knowledge enters and leaves the RAG boundary:

- `03-rag-knowledge-store.md`
- `src/expertview/rag/base.py`
- `src/expertview/rag/inmemory.py`
