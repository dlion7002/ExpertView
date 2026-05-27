"""Private Streamlit render helpers for the ExpertView demo app."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import streamlit as st
import streamlit_mermaid as stmd

from expertview.evidence.models import CausalReport, Hypothesis, Incident

_CONFIDENCE_BAR_WIDTH: Final = 100
_SNIPPET_CHARS: Final = 280


@dataclass(frozen=True)
class CitationSource:
    citation_id: str
    source_path: str
    snippet: str


def build_citation_index(corpus_root: Path) -> dict[str, list[CitationSource]]:
    index: dict[str, list[CitationSource]] = {}
    if not corpus_root.exists():
        return index

    for path in sorted(corpus_root.glob("*/*.md")):
        content = path.read_text(encoding="utf-8")
        citation = CitationSource(
            citation_id=path.stem,
            source_path=path.as_posix(),
            snippet=_snippet(content),
        )
        index.setdefault(path.stem, []).append(citation)
    return index


def render_incident(incident: Incident) -> None:
    st.subheader("Incident")
    st.write(incident.summary)
    st.caption(f"Observed: {incident.observed_at.isoformat()}")

    left, right = st.columns(2)
    with left:
        st.markdown("**Symptoms**")
        for symptom in incident.symptoms:
            st.write(f"- {symptom}")
    with right:
        st.markdown("**Affected assets**")
        for asset in incident.affected_assets:
            st.write(f"- {asset}")


def render_topology(mermaid: str, *, key: str) -> None:
    st.subheader("Topology")
    stmd.st_mermaid(
        mermaid,
        height="520px",
        pan=True,
        zoom=True,
        show_controls=True,
        key=key,
    )


def render_progress_panel(
    rows: Sequence[tuple[str, str]],
    *,
    findings_count: int,
) -> None:
    st.subheader("Live investigation")
    st.metric("Evidence findings", findings_count)

    for label, status in rows:
        st.write(f"**{label}**")
        if status == "Complete":
            st.progress(1.0, text=status)
        elif status == "Running":
            st.progress(0.5, text=status)
        else:
            st.progress(0.0, text=status)


def render_causal_report(
    report: CausalReport,
    citation_index: Mapping[str, Sequence[CitationSource]],
) -> None:
    st.subheader("Causal report")
    st.caption(f"Incident: {report.incident_id} | Generated: {report.generated_at.isoformat()}")
    st.info(report.confidence_summary)

    st.markdown("**Top hypotheses**")
    for index, hypothesis in enumerate(report.top_hypotheses, start=1):
        _render_hypothesis(index, hypothesis, citation_index)

    if report.causal_chain:
        st.markdown("**Causal chain**")
        for index, link in enumerate(report.causal_chain, start=1):
            effect = link.effect
            effect_text = effect.claim if isinstance(effect, Hypothesis) else effect.description
            with st.container(border=True):
                st.caption(f"Link {index} | Strength {link.strength:.2f}")
                st.write(f"**Cause:** {link.cause.claim}")
                st.write(f"**Effect:** {effect_text}")
                st.write(link.rationale)

    _render_citations(_unique_citations(report), citation_index)


def _render_hypothesis(
    index: int,
    hypothesis: Hypothesis,
    citation_index: Mapping[str, Sequence[CitationSource]],
) -> None:
    with st.container(border=True):
        st.caption(f"#{index} | {hypothesis.domain_origin}")
        st.progress(
            round(hypothesis.confidence * _CONFIDENCE_BAR_WIDTH) / _CONFIDENCE_BAR_WIDTH,
            text=f"Confidence {hypothesis.confidence:.2f}",
        )
        st.write(hypothesis.claim)
        if hypothesis.supporting_findings:
            with st.expander("Supporting findings", expanded=False):
                for finding in hypothesis.supporting_findings:
                    st.write(
                        f"- **{finding.investigator_domain}** "
                        f"({finding.confidence:.2f}): {finding.claim}"
                    )
                    _render_citations(finding.citations, citation_index)


def _render_citations(
    citations: Iterable[str],
    citation_index: Mapping[str, Sequence[CitationSource]],
) -> None:
    unique = list(dict.fromkeys(citations))
    if not unique:
        return

    st.markdown("**Citations**")
    for citation_id in unique:
        matches = citation_index.get(citation_id, [])
        if not matches:
            st.write(f"- `{citation_id}`")
            continue
        for source in matches:
            st.write(f"- `{source.citation_id}` -> `{source.source_path}`")
            st.caption(source.snippet)


def _unique_citations(report: CausalReport) -> list[str]:
    citations: list[str] = []
    for hypothesis in report.top_hypotheses:
        for finding in hypothesis.supporting_findings:
            citations.extend(finding.citations)
    return list(dict.fromkeys(citations))


def _snippet(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    snippet = " ".join(lines)
    if len(snippet) <= _SNIPPET_CHARS:
        return snippet
    return f"{snippet[: _SNIPPET_CHARS - 3].rstrip()}..."
