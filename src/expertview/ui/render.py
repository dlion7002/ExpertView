"""Private Streamlit render helpers for the ExpertView demo app.

The look is a polished investigation dashboard: a styled header band, bordered
cards per stage, status-badge pills, a colored topology legend, and a
verdict-first report hero. All custom styling is injected once via
:func:`inject_css`; the per-status colors there are kept visually aligned with
``_STATUS_MERMAID_STYLE`` (topology recolor) so badges, card accents, the legend,
and the graph all read as one design.
"""

from __future__ import annotations

import html
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import streamlit as st
import streamlit_mermaid as stmd

from expertview.evidence.convergence import corroborating_domains, mean_evidence_weight
from expertview.evidence.models import CausalReport, Finding, Hypothesis, Incident, Symptom
from expertview.orchestration.runner import (
    DISPATCHER_NODE,
    INVESTIGATOR_NODES,
    SPAWNING_JOIN_NODE,
    SUB_INVESTIGATOR_NODE,
    SYNTHESIZER_NODE,
)
from expertview.orchestration.streaming import (
    ACTIVE,
    COMPLETE,
    SKIPPED,
    WAITING,
    SpawnDecision,
)

_SNIPPET_CHARS: Final = 280

# status → CSS class suffix; drives the badge pills and the per-card left accent.
_STATUS_CLASS: Final[Mapping[str, str]] = {
    WAITING: "waiting",
    ACTIVE: "active",
    COMPLETE: "complete",
    SKIPPED: "skipped",
}

# Mermaid node recolor — the topology's single source of color. The HTML palette
# in `inject_css` mirrors these hues so the surface reads as one piece.
_STATUS_MERMAID_STYLE: Final[Mapping[str, str]] = {
    WAITING: "fill:#eeeeee,stroke:#bdbdbd,color:#9e9e9e",
    ACTIVE: "fill:#fff3c4,stroke:#f0a500,color:#5f4b00,stroke-width:3px",
    COMPLETE: "fill:#c8e6c9,stroke:#43a047,color:#1b5e20",
    SKIPPED: "fill:#f5f5f5,stroke:#bdbdbd,color:#9e9e9e,stroke-dasharray:4 4",
}

# The stylesheet lives in a sibling .css file (syntax-highlightable, no Python
# line-length friction) and is read once at import. Centralizing every custom
# rule there keeps the "heavier CSS" tradeoff isolated: if a future Streamlit
# bump changes the bordered-container testid, the cards lose their left accent
# but stay bordered and legible (no broken layout).
_DEMO_CSS: Final = (Path(__file__).with_name("demo.css")).read_text(encoding="utf-8")


@dataclass(frozen=True)
class CitationSource:
    citation_id: str
    source_path: str
    snippet: str


def inject_css() -> None:
    """Inject the demo stylesheet once per rerun (idempotent)."""

    st.markdown(f"<style>{_DEMO_CSS}</style>", unsafe_allow_html=True)


def render_app_header() -> None:
    """Render the styled product header band (replaces a bare ``st.title``)."""

    st.markdown(
        '<div class="ev-header">'
        '<div class="ev-header-title">ExpertView</div>'
        '<div class="ev-tagline">Multi-agent root-cause analysis for industrial incidents</div>'
        "</div>",
        unsafe_allow_html=True,
    )


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
    with st.container(border=True):
        st.markdown(
            '<span class="ev-card-marker ev-card-marker--incident"></span>', unsafe_allow_html=True
        )
        _section_header("Incident", subtitle=f"Observed {incident.observed_at.isoformat()}")
        st.markdown(
            f'<div class="ev-incident-summary">{html.escape(incident.summary)}</div>',
            unsafe_allow_html=True,
        )
        left, right = st.columns(2)
        with left:
            st.markdown(_chip_group("Symptoms", incident.symptoms), unsafe_allow_html=True)
        with right:
            st.markdown(
                _chip_group("Affected assets", incident.affected_assets), unsafe_allow_html=True
            )


def style_topology_mermaid(mermaid: str, status_by_node: Mapping[str, str]) -> str:
    """Append per-node Mermaid ``style`` directives colored by live status."""

    lines = [mermaid.rstrip()]
    for node_name, status in status_by_node.items():
        style = _STATUS_MERMAID_STYLE.get(status)
        if style is not None:
            lines.append(f"style {node_name} {style}")
    return "\n".join(lines)


def render_topology_placeholder() -> None:
    """Render the topology section header before a run has started."""

    _section_header(
        "Investigation topology",
        subtitle="The compiled LangGraph topology appears when the run starts.",
    )


def render_topology(mermaid: str, *, key: str) -> None:
    _section_header(
        "Investigation topology",
        subtitle=(
            "Five domain investigators run in parallel; a sub-investigation spawns "
            "only when a bearing anomaly is found."
        ),
    )
    stmd.st_mermaid(
        mermaid,
        height="640px",
        pan=True,
        zoom=True,
        show_controls=True,
        key=key,
    )
    st.markdown(_legend_html(), unsafe_allow_html=True)


def render_progress_panel(
    rows: Sequence[tuple[str, str, str]],
    *,
    findings_count: int,
    findings_by_node: Mapping[str, Sequence[Finding]],
    spawn_decision: SpawnDecision | None,
) -> None:
    label_map = {node_name: label for node_name, label, _ in rows}
    status_map = {node_name: status for node_name, _, status in rows}

    _section_header(
        "Live investigation",
        subtitle="Five domain investigators run in parallel against domain-specific evidence.",
    )
    st.markdown(_stat_html("evidence findings", findings_count), unsafe_allow_html=True)

    # Entry stage.
    st.markdown(
        _status_row_html(
            label_map[DISPATCHER_NODE],
            status_map[DISPATCHER_NODE],
            _dispatcher_detail(status_map[DISPATCHER_NODE]),
        ),
        unsafe_allow_html=True,
    )

    # The five parallel investigators — the heart of the panel, one card each.
    for node_name in INVESTIGATOR_NODES:
        _render_investigator_card(
            label_map[node_name],
            status_map[node_name],
            findings_by_node.get(node_name, ()),
        )

    # Routing + synthesis, visually subordinate to the investigator cards.
    _subhead("Routing & synthesis")
    st.markdown(
        _status_row_html(
            label_map[SPAWNING_JOIN_NODE],
            status_map[SPAWNING_JOIN_NODE],
            _spawn_detail(status_map[SPAWNING_JOIN_NODE], spawn_decision),
        ),
        unsafe_allow_html=True,
    )
    _render_subinvestigator(
        label_map[SUB_INVESTIGATOR_NODE],
        status_map[SUB_INVESTIGATOR_NODE],
        findings_by_node.get(SUB_INVESTIGATOR_NODE, ()),
    )
    st.markdown(
        _status_row_html(
            label_map[SYNTHESIZER_NODE],
            status_map[SYNTHESIZER_NODE],
            _synth_detail(status_map[SYNTHESIZER_NODE]),
        ),
        unsafe_allow_html=True,
    )


def _render_investigator_card(
    label: str,
    status: str,
    node_findings: Sequence[Finding],
) -> None:
    with st.container(border=True):
        st.markdown(_card_header_html(label, status, node_findings), unsafe_allow_html=True)
        if node_findings:
            with st.expander(f"What {label} found", expanded=False):
                for finding in node_findings:
                    st.markdown(f"- **({finding.confidence:.2f})** {finding.claim}")
                    _render_citation_chips(finding.citations)


def _render_subinvestigator(
    label: str,
    status: str,
    node_findings: Sequence[Finding],
) -> None:
    if node_findings:
        _render_investigator_card(label, status, node_findings)
        return
    if status == SKIPPED:
        detail = "Not triggered for this incident."
    elif status == ACTIVE:
        detail = "Running the spawned sub-investigation…"
    else:
        detail = "Spawned only when a bearing anomaly is found."
    st.markdown(_status_row_html(label, status, detail), unsafe_allow_html=True)


def _card_header_html(label: str, status: str, node_findings: Sequence[Finding]) -> str:
    cls = _STATUS_CLASS.get(status, "waiting")
    marker = f'<span class="ev-card-marker ev-card-marker--{cls}"></span>'
    head = (
        f'<div class="ev-card-head"><span class="ev-card-title">{html.escape(label)}</span>'
        f"{_badge(status)}</div>"
    )
    if node_findings:
        top = node_findings[0]
        sub = f"{len(node_findings)} finding(s) · {_snippet_text(top.claim)}"
    else:
        sub = _idle_detail(status)
    return f'{marker}{head}<div class="ev-card-sub">{html.escape(sub)}</div>'


def _idle_detail(status: str) -> str:
    return {
        ACTIVE: "Investigating…",
        COMPLETE: "Completed — no findings raised.",
        SKIPPED: "Skipped for this incident.",
    }.get(status, "Waiting to start.")


def _dispatcher_detail(status: str) -> str:
    if status == COMPLETE:
        return "Fanned out to five parallel investigators."
    if status == ACTIVE:
        return "Dispatching parallel investigators…"
    return "Waiting to start."


def _spawn_detail(status: str, spawn_decision: SpawnDecision | None) -> str:
    if spawn_decision is not None:
        return spawn_decision.reason
    if status == ACTIVE:
        return "Evaluating whether to spawn a sub-investigation…"
    return "Decides whether a sub-investigation is needed."


def _synth_detail(status: str) -> str:
    if status == COMPLETE:
        return "Merged all investigator findings and converged on the causal report."
    if status == ACTIVE:
        return "Synthesizing the evidence-weighted causal report…"
    return "Waiting for all investigators to report."


def render_causal_report(
    report: CausalReport,
    citation_index: Mapping[str, Sequence[CitationSource]],
) -> None:
    _section_header(
        "Causal report",
        subtitle=f"Incident {report.incident_id} · generated {report.generated_at.isoformat()}",
    )

    hypotheses = report.top_hypotheses
    if not hypotheses:
        st.info(report.confidence_summary)
        _render_sources(report, citation_index)
        return

    _render_verdict_hero(hypotheses[0], report.confidence_summary)
    _render_reasoning(report, hypotheses[0])
    _render_symptoms_explained(report.causal_chain)
    _render_supporting_evidence(hypotheses)
    _render_considered(report, hypotheses[1:])
    _render_sources(report, citation_index)


def _render_verdict_hero(top: Hypothesis, confidence_summary: str) -> None:
    bar = (
        '<div class="ev-conf-bar">'
        f'<div class="ev-conf-bar-fill" style="width:{top.confidence:.0%}"></div></div>'
    )
    st.markdown(
        '<div class="ev-hero">'
        '<div class="ev-hero-label">Most likely root cause</div>'
        f'<div class="ev-hero-claim">{html.escape(top.claim)}</div>'
        '<div class="ev-hero-meta">'
        f'<span class="ev-hero-conf">{top.confidence:.0%}</span>'
        '<span class="ev-hero-conf-label">confidence</span>'
        f'<span class="ev-chip ev-chip--domain">{html.escape(top.domain_origin)}</span>'
        "</div>"
        f"{bar}"
        f'<div class="ev-hero-summary">{html.escape(confidence_summary)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _render_symptoms_explained(causal_chain: Sequence) -> None:
    if not causal_chain:
        return

    symptom_links = [link for link in causal_chain if isinstance(link.effect, Symptom)]
    hop_links = [link for link in causal_chain if isinstance(link.effect, Hypothesis)]

    if symptom_links:
        _subhead("Symptoms this explains")
        for cause_claim, links in _group_by_cause(symptom_links):
            st.markdown(f"_{cause_claim}_ explains:")
            for link in links:
                st.markdown(f"- {link.effect.description}  ·  strength {link.strength:.2f}")

    if hop_links:
        _subhead("Causal chain")
        for index, link in enumerate(hop_links, start=1):
            st.markdown(
                f"{index}. **{link.cause.claim}** → **{link.effect.claim}**  "
                f"·  strength {link.strength:.2f}"
            )
            st.caption(link.rationale)


def _group_by_cause(links: Sequence) -> list[tuple[str, list]]:
    grouped: dict[str, list] = {}
    claims: dict[str, str] = {}
    for link in links:
        key = link.cause.id
        grouped.setdefault(key, []).append(link)
        claims[key] = link.cause.claim
    return [(claims[key], grouped[key]) for key in grouped]


def _render_supporting_evidence(hypotheses: Sequence[Hypothesis]) -> None:
    with st.expander("Supporting evidence", expanded=False):
        for hypothesis in hypotheses:
            st.markdown(
                f"**{hypothesis.claim}**  ·  {hypothesis.domain_origin}  "
                f"·  {hypothesis.confidence:.0%}"
            )
            if not hypothesis.supporting_findings:
                st.caption("No findings attached.")
                continue
            for finding in hypothesis.supporting_findings:
                st.markdown(
                    f"- **{finding.investigator_domain}** "
                    f"({finding.confidence:.2f}): {finding.claim}"
                )
                _render_citation_chips(finding.citations)


def _render_reasoning(report: CausalReport, top: Hypothesis) -> None:
    # The deductive "why" the live panel never explains, plus the deterministic
    # basis behind the headline score (breadth/depth) so the prose is checkable.
    _subhead("Why this is the root cause")
    if report.verdict_reasoning.strip():
        st.markdown(report.verdict_reasoning)
    st.caption(_ranking_basis_caption(top))


def _ranking_basis_caption(top: Hypothesis) -> str:
    domains = corroborating_domains(top)
    return (
        f"Backed by {len(top.supporting_findings)} finding(s) across {len(domains)} "
        f"domain(s) ({', '.join(domains)}) · mean evidence {mean_evidence_weight(top):.2f}"
    )


def _render_considered(report: CausalReport, others: Sequence[Hypothesis]) -> None:
    summary = report.alternatives_summary.strip()
    if not summary and not others:
        return

    _subhead("What else was considered")
    if summary:
        st.markdown(summary)
    if others:
        with st.expander(f"Other hypotheses considered ({len(others)})", expanded=False):
            for index, hypothesis in enumerate(others, start=2):
                st.markdown(
                    f"{index}. **{hypothesis.claim}**  ·  {hypothesis.domain_origin}  "
                    f"·  {hypothesis.confidence:.0%}"
                )


def _render_sources(
    report: CausalReport,
    citation_index: Mapping[str, Sequence[CitationSource]],
) -> None:
    citation_ids = _unique_citations(report)
    if not citation_ids:
        return

    with st.expander("Sources & excerpts", expanded=False):
        for citation_id in citation_ids:
            matches = citation_index.get(citation_id, [])
            if not matches:
                st.markdown(f"- `{citation_id}`")
                continue
            for source in matches:
                st.markdown(f"- `{source.citation_id}` → `{source.source_path}`")
                # Plain text, not markdown: raw `##` lines in corpus excerpts
                # would otherwise render as giant headers via st.caption/markdown.
                st.text(source.snippet)


def _section_header(title: str, *, subtitle: str | None = None) -> None:
    sub = f'<div class="ev-section-sub">{html.escape(subtitle)}</div>' if subtitle else ""
    title_html = f'<div class="ev-section-title">{html.escape(title)}</div>'
    st.markdown(f'<div class="ev-section">{title_html}{sub}</div>', unsafe_allow_html=True)


def _subhead(text: str) -> None:
    st.markdown(f'<div class="ev-subhead">{html.escape(text)}</div>', unsafe_allow_html=True)


def _badge(status: str) -> str:
    cls = _STATUS_CLASS.get(status, "waiting")
    return f'<span class="ev-badge ev-badge--{cls}">{html.escape(status)}</span>'


def _legend_html() -> str:
    items = "".join(_badge(status) for status in (COMPLETE, ACTIVE, WAITING, SKIPPED))
    return f'<div class="ev-legend">{items}</div>'


def _stat_html(label: str, value: int) -> str:
    return (
        f'<div class="ev-stat"><span class="ev-stat-value">{value}</span>'
        f'<span class="ev-stat-label">{html.escape(label)}</span></div>'
    )


def _status_row_html(label: str, status: str, detail: str | None) -> str:
    cls = _STATUS_CLASS.get(status, "waiting")
    detail_html = f'<span class="ev-row-detail">{html.escape(detail)}</span>' if detail else ""
    return (
        f'<div class="ev-row ev-row--{cls}">{_badge(status)}'
        f'<span class="ev-row-label">{html.escape(label)}</span>{detail_html}</div>'
    )


def _chip_group(label: str, items: Iterable[str]) -> str:
    chips = "".join(f'<span class="ev-chip">{html.escape(item)}</span>' for item in items)
    return (
        f'<div class="ev-chip-label">{html.escape(label)}</div>'
        f'<div class="ev-chip-group">{chips}</div>'
    )


def _render_citation_chips(citations: Iterable[str]) -> None:
    unique = list(dict.fromkeys(citations))
    if not unique:
        return
    st.caption("Sources: " + "  ".join(f"`{citation_id}`" for citation_id in unique))


def _unique_citations(report: CausalReport) -> list[str]:
    citations: list[str] = []
    for hypothesis in report.top_hypotheses:
        for finding in hypothesis.supporting_findings:
            citations.extend(finding.citations)
    return list(dict.fromkeys(citations))


def _snippet_text(claim: str) -> str:
    claim = claim.strip()
    if len(claim) <= _SNIPPET_CHARS:
        return claim
    return f"{claim[: _SNIPPET_CHARS - 1].rstrip()}…"


def _snippet(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    snippet = " ".join(lines)
    if len(snippet) <= _SNIPPET_CHARS:
        return snippet
    return f"{snippet[: _SNIPPET_CHARS - 3].rstrip()}..."
