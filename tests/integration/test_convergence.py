"""Two-incident convergence regression test (Phase 5 Task 3).

Runs both rehearsed incidents through ``make_graph()`` with deterministic fake
stores and fake LLMs and asserts the synthesizer's post-LLM re-scoring
(``evidence/convergence.py``) produces two reports whose top hypotheses differ,
whose confidence summaries reflect the computed scores, and whose final
confidences equal ``score_hypothesis``'s output rather than the fake LLM's raw
draft values. No OpenRouter call; the fakes return hard-coded JSON, so this is
the CI regression guard for a future refactor that bypasses the re-scoring or
collapses the two scenarios to one top cause.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from expertview.evidence.convergence import score_hypothesis
from expertview.evidence.models import (
    CausalReport,
    Document,
    Finding,
    Hypothesis,
    Incident,
)
from expertview.orchestration.runner import INVESTIGATOR_NODES, make_graph
from expertview.orchestration.state import ExpertViewState

_CNC_INCIDENT_PATH = Path("data/incidents/cnc_out_of_tolerance.yaml")
_PROCESS_INCIDENT_PATH = Path("data/incidents/process_recipe_drift.yaml")


class _FakeStore:
    def __init__(self, domain: str) -> None:
        self.domain = domain
        self._document = Document(
            id=f"{domain}-doc-001",
            content=f"Fake {domain} document for convergence test.",
            source=f"data/domains/{domain}/fake.md",
            domain=domain,
            metadata={},
        )

    def search(self, query: str, k: int = 5) -> list[Document]:
        return [self._document]


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeInvestigatorLlm:
    """Returns one neutral finding per domain. No bearing anomaly, so the graph
    routes straight to the synthesizer (no sub-investigation) and the synthesizer
    re-scoring path is exercised in isolation."""

    async def ainvoke(self, input: str) -> _FakeResponse:
        domain = self._detect_domain(input)
        return _FakeResponse(
            json.dumps(
                [
                    {
                        "investigator_domain": domain,
                        "claim": f"Fake {domain} finding for convergence test.",
                        "confidence": 0.5,
                        "citations": [f"{domain}-doc-001"],
                    }
                ]
            )
        )

    @staticmethod
    def _detect_domain(prompt: str) -> str:
        for domain in INVESTIGATOR_NODES:
            if f'"{domain}"' in prompt:
                return domain
        raise AssertionError(
            "could not detect investigator domain in rendered prompt; "
            f"prompt head: {prompt[:200]!r}"
        )


class _FakeSynthesizerLlm:
    """Emits a fixed draft CausalReport verbatim, ignoring the prompt. The draft's
    raw confidences are deliberately mis-calibrated so the re-scoring's override is
    observable in the assertions."""

    def __init__(self, draft: CausalReport) -> None:
        self._payload = draft.model_dump_json()
        self.prompts: list[str] = []

    async def ainvoke(self, input: str) -> _FakeResponse:
        self.prompts.append(input)
        return _FakeResponse(self._payload)


def _load_incident(path: Path) -> Incident:
    return Incident.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _initial_state(incident: Incident) -> ExpertViewState:
    return {
        "incident": incident,
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }


def _cnc_draft(incident_id: str) -> tuple[CausalReport, Hypothesis]:
    strong = Hypothesis(
        id="hyp-bearing-fault",
        claim="Spindle bearing preload loss from the new lot drove the bore drift.",
        supporting_findings=[
            Finding(
                investigator_domain="mechanical",
                claim="Warm runout growth points to bearing preload loss on spindle-04.",
                confidence=0.86,
                citations=["mech-bearing-001", "mech-runout-014"],
            ),
            Finding(
                investigator_domain="supply_chain",
                claim="New bearing lot shows out-of-spec hardness on incoming inspection.",
                confidence=0.81,
                citations=["sc-lot-007"],
            ),
        ],
        # Deliberately low raw confidence: re-scoring must lift this above the
        # process hypothesis below despite the LLM under-rating it.
        confidence=0.40,
        domain_origin="mechanical",
    )
    weak = Hypothesis(
        id="hyp-process-drift",
        claim="Routine gauge-cadence variance contributed to the readings.",
        supporting_findings=[
            Finding(
                investigator_domain="process",
                claim="Minor in-process gauge-cadence variance noted on shift 3.",
                confidence=0.44,
                citations=["proc-001"],
            ),
        ],
        # Deliberately high raw confidence: re-scoring must demote this.
        confidence=0.90,
        domain_origin="process",
    )
    draft = CausalReport(
        incident_id=incident_id,
        # Weak hypothesis listed first to prove re-scoring re-orders top_hypotheses.
        top_hypotheses=[weak, strong],
        causal_chain=[],
        confidence_summary="LLM draft summary (overridden by re-scoring).",
    )
    return draft, strong


def _process_draft(incident_id: str) -> tuple[CausalReport, Hypothesis]:
    strong = Hypothesis(
        id="hyp-recipe-mismatch",
        claim="A recipe revision mismatch at the changeover drove the fill drift.",
        supporting_findings=[
            Finding(
                investigator_domain="process",
                claim="Loaded recipe revision did not match the press setup sheet at changeover.",
                confidence=0.88,
                citations=["proc-recipe-009", "proc-setup-002"],
            ),
            Finding(
                investigator_domain="environmental",
                claim="Ambient humidity shift widened the fill window after changeover.",
                confidence=0.76,
                citations=["env-014"],
            ),
        ],
        confidence=0.35,
        domain_origin="process",
    )
    weak = Hypothesis(
        id="hyp-mech-noise",
        claim="Press tie-bar vibration may have perturbed the shot.",
        supporting_findings=[
            Finding(
                investigator_domain="mechanical",
                claim="Low-confidence press tie-bar vibration during the run.",
                confidence=0.41,
                citations=["mech-101"],
            ),
        ],
        confidence=0.85,
        domain_origin="mechanical",
    )
    draft = CausalReport(
        incident_id=incident_id,
        top_hypotheses=[weak, strong],
        causal_chain=[],
        confidence_summary="LLM draft summary (overridden by re-scoring).",
    )
    return draft, strong


def _apply_fakes(
    monkeypatch: pytest.MonkeyPatch,
    fake_investigator: _FakeInvestigatorLlm,
    fake_synthesizer: _FakeSynthesizerLlm,
) -> None:
    monkeypatch.setattr(
        "expertview.orchestration.runner.create_embeddings",
        lambda: object(),
    )
    monkeypatch.setattr(
        "expertview.orchestration.runner.create_investigator_llm",
        lambda: fake_investigator,
    )
    monkeypatch.setattr(
        "expertview.orchestration.runner.create_synthesizer_llm",
        lambda: fake_synthesizer,
    )
    for domain in INVESTIGATOR_NODES:
        monkeypatch.setattr(
            f"expertview.orchestration.runner.load_{domain}_store",
            lambda _embeddings, _domain=domain: _FakeStore(_domain),
        )


def _citations(report: CausalReport) -> set[str]:
    return {
        citation
        for hypothesis in report.top_hypotheses
        for finding in hypothesis.supporting_findings
        for citation in finding.citations
    }


async def _run_leg(
    monkeypatch: pytest.MonkeyPatch,
    incident: Incident,
    draft: CausalReport,
) -> CausalReport:
    _apply_fakes(monkeypatch, _FakeInvestigatorLlm(), _FakeSynthesizerLlm(draft))
    final_state = await make_graph().ainvoke(_initial_state(incident))
    report = final_state["causal_report"]
    assert isinstance(report, CausalReport)
    return report


@pytest.mark.asyncio
async def test_two_incidents_produce_distinct_rescored_top_hypotheses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cnc_incident = _load_incident(_CNC_INCIDENT_PATH)
    process_incident = _load_incident(_PROCESS_INCIDENT_PATH)
    cnc_draft, cnc_strong = _cnc_draft(cnc_incident.id)
    process_draft, process_strong = _process_draft(process_incident.id)

    cnc_report = await _run_leg(monkeypatch, cnc_incident, cnc_draft)
    process_report = await _run_leg(monkeypatch, process_incident, process_draft)

    assert cnc_report.incident_id == cnc_incident.id
    assert process_report.incident_id == process_incident.id

    cnc_top = cnc_report.top_hypotheses[0]
    process_top = process_report.top_hypotheses[0]

    # The two scenarios converge on genuinely different top causes.
    assert cnc_top.claim != process_top.claim
    assert cnc_top.domain_origin != process_top.domain_origin

    # Each report's lead domain matches the incident's intended lead.
    assert cnc_top.domain_origin in {"mechanical", "supply_chain"}
    assert process_top.domain_origin == "process"

    # Re-scoring actually ran: the top hypothesis is the one re-scoring lifted to
    # the top (not the one the fake LLM listed first), and its final confidence is
    # score_hypothesis's computed value, not the raw draft confidence.
    assert cnc_top.id == cnc_strong.id
    assert cnc_top.confidence == score_hypothesis(cnc_strong).confidence
    assert cnc_top.confidence != cnc_strong.confidence
    assert process_top.id == process_strong.id
    assert process_top.confidence == score_hypothesis(process_strong).confidence
    assert process_top.confidence != process_strong.confidence

    # Confidence summaries are non-trivial: data-reflecting (name the lead domain)
    # and distinct between the two reports rather than a constant string.
    assert cnc_top.domain_origin in cnc_report.confidence_summary
    assert process_top.domain_origin in process_report.confidence_summary
    assert cnc_report.confidence_summary != process_report.confidence_summary
    assert "%" in cnc_report.confidence_summary
    assert "%" in process_report.confidence_summary

    # The causal chain was re-built from the re-scored hypotheses.
    assert cnc_report.causal_chain
    assert process_report.causal_chain

    # The citation contract survives re-scoring: every drafted citation is still
    # present in the re-scored report's supporting findings.
    assert _citations(cnc_draft) <= _citations(cnc_report)
    assert _citations(process_draft) <= _citations(process_report)
