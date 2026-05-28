"""ExpertView Streamlit demo app.

Launch with:

    uv run streamlit run src/expertview/ui/app.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Final

import streamlit as st
import yaml
from pydantic import ValidationError

from expertview.evidence.models import CausalReport, Incident
from expertview.orchestration.runner import make_graph
from expertview.orchestration.state import ExpertViewState
from expertview.orchestration.streaming import (
    COMPLETE,
    NODE_LABELS,
    WAITING,
    ProgressEvent,
    advance_status,
    initial_status,
    render_topology_mermaid,
    stream_run,
)
from expertview.ui.render import (
    build_citation_index,
    inject_css,
    render_app_header,
    render_causal_report,
    render_incident,
    render_progress_panel,
    render_topology,
    render_topology_placeholder,
    style_topology_mermaid,
)

_PROJECT_ROOT: Final = Path(__file__).resolve().parents[3]
_INCIDENTS_DIR: Final = _PROJECT_ROOT / "data" / "incidents"
_DOMAINS_DIR: Final = _PROJECT_ROOT / "data" / "domains"


def main() -> None:
    _maybe_load_env_file()
    st.set_page_config(page_title="ExpertView Demo", page_icon="EV", layout="wide")
    inject_css()
    render_app_header()

    incident_paths = _incident_paths()
    if not incident_paths:
        st.error(f"No incidents found under {_INCIDENTS_DIR.as_posix()}.")
        return

    selected_path = st.selectbox(
        "Incident",
        incident_paths,
        format_func=lambda path: path.stem.replace("_", " "),
    )

    try:
        incident = _load_incident(selected_path)
    except (FileNotFoundError, ValidationError, yaml.YAMLError) as exc:
        st.error(f"Failed to load incident: {exc}")
        return

    render_incident(incident)
    status_slot, topology_slot = _render_run_region()
    report_slot = st.empty()

    if st.button("Run investigation", type="primary"):
        _reset_run_state()
        with report_slot.container():
            st.empty()
        _run_investigation(incident, status_slot, topology_slot, report_slot)
    elif st.session_state.get("last_report") is not None:
        report = st.session_state["last_report"]
        if isinstance(report, CausalReport):
            with report_slot.container():
                render_causal_report(report, build_citation_index(_DOMAINS_DIR))


def _render_run_region() -> tuple[
    st.delta_generator.DeltaGenerator,
    st.delta_generator.DeltaGenerator,
]:
    left, right = st.columns([0.9, 1.1], gap="large")
    with left:
        status_slot = st.empty()
        _render_current_progress(status_slot)
    with right:
        topology_slot = st.empty()
        mermaid = st.session_state.get("last_topology_mermaid")
        if isinstance(mermaid, str) and mermaid.strip():
            _render_current_topology(topology_slot, key="topology-current")
        else:
            with topology_slot.container():
                render_topology_placeholder()
    return status_slot, topology_slot


def _run_investigation(
    incident: Incident,
    status_slot: st.delta_generator.DeltaGenerator,
    topology_slot: st.delta_generator.DeltaGenerator,
    report_slot: st.delta_generator.DeltaGenerator,
) -> None:
    try:
        compiled_graph = make_graph()
    except Exception as exc:
        st.error(f"Failed to compile the LangGraph runner: {exc}")
        st.exception(exc)
        return

    mermaid = render_topology_mermaid(compiled_graph)
    st.session_state["last_topology_mermaid"] = mermaid
    _render_current_topology(topology_slot, key=f"topology-{incident.id}")

    initial_state: ExpertViewState = {
        "incident": incident,
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }

    try:
        report = asyncio.run(
            _consume_run(compiled_graph, initial_state, status_slot, topology_slot, report_slot)
        )
    except Exception as exc:
        st.error(f"Graph invocation failed: {exc}")
        st.exception(exc)
        return

    if report is None:
        st.error("Graph completed without producing a CausalReport.")
        return

    st.session_state["last_report"] = report


async def _consume_run(
    compiled_graph: object,
    initial_state: ExpertViewState,
    status_slot: st.delta_generator.DeltaGenerator,
    topology_slot: st.delta_generator.DeltaGenerator,
    report_slot: st.delta_generator.DeltaGenerator,
) -> CausalReport | None:
    report: CausalReport | None = None
    citation_index = build_citation_index(_DOMAINS_DIR)

    async for event in stream_run(compiled_graph, initial_state):  # type: ignore[arg-type]
        _record_event(event)
        _render_current_progress(status_slot)
        # Re-key the topology component on the completion count so st_mermaid
        # reliably repaints as nodes recolor (waiting → active → done/skipped).
        _render_current_topology(topology_slot, key=f"topology-live-{_completion_count()}")
        if event.causal_report is not None:
            report = event.causal_report
            with report_slot.container():
                render_causal_report(report, citation_index)

    return report


def _record_event(event: ProgressEvent) -> None:
    status_by_node = advance_status(st.session_state.get("status_by_node", initial_status()), event)
    st.session_state["status_by_node"] = status_by_node
    st.session_state["findings_count"] = event.findings_count

    if event.findings:
        findings_by_node = dict(st.session_state.get("findings_by_node", {}))
        findings_by_node[event.node_name] = list(event.findings)
        st.session_state["findings_by_node"] = findings_by_node

    if event.spawn_decision is not None:
        st.session_state["spawn_decision"] = event.spawn_decision


def _render_current_progress(status_slot: st.delta_generator.DeltaGenerator) -> None:
    status_by_node = st.session_state.get("status_by_node", initial_status())
    findings_count = int(st.session_state.get("findings_count", 0))
    rows = [
        (node_name, label, status_by_node.get(node_name, WAITING))
        for node_name, label in NODE_LABELS.items()
    ]
    with status_slot.container():
        render_progress_panel(
            rows,
            findings_count=findings_count,
            findings_by_node=st.session_state.get("findings_by_node", {}),
            spawn_decision=st.session_state.get("spawn_decision"),
        )


def _render_current_topology(topology_slot: st.delta_generator.DeltaGenerator, *, key: str) -> None:
    mermaid = st.session_state.get("last_topology_mermaid")
    if not (isinstance(mermaid, str) and mermaid.strip()):
        return
    status_by_node = st.session_state.get("status_by_node", initial_status())
    with topology_slot.container():
        render_topology(style_topology_mermaid(mermaid, status_by_node), key=key)


def _completion_count() -> int:
    status_by_node = st.session_state.get("status_by_node", {})
    return sum(1 for status in status_by_node.values() if status == COMPLETE)


def _reset_run_state() -> None:
    st.session_state["status_by_node"] = initial_status()
    st.session_state["findings_count"] = 0
    st.session_state["findings_by_node"] = {}
    st.session_state["spawn_decision"] = None
    st.session_state["last_report"] = None


def _incident_paths() -> list[Path]:
    return sorted(_INCIDENTS_DIR.glob("*.yaml"))


def _load_incident(path: Path) -> Incident:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Incident.model_validate(raw)


def _maybe_load_env_file() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_PROJECT_ROOT / ".env", override=False)


if __name__ == "__main__":
    main()
