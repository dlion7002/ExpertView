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
    # Deductive narrative written by the synthesizer's second (reasoning) pass,
    # grounded in the deterministic re-scored confidences. `verdict_reasoning`
    # explains *why* the top hypothesis is the conclusion; `alternatives_summary`
    # is the one comparative paragraph on what else was considered and why it was
    # not the originating cause. Defaulted to "" so non-synthesizer constructors
    # (tests, streaming fixtures) stay valid.
    verdict_reasoning: str = ""
    alternatives_summary: str = ""
    generated_at: datetime = Field(default_factory=_utc_now)
