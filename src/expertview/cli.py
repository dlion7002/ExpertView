"""ExpertView command-line entry point.

Exposes ``python -m expertview.cli demo --incident PATH`` (and the equivalent
``uv run expertview demo --incident PATH`` via the ``[project.scripts]``
entry in ``pyproject.toml``). The ``demo`` command loads an incident YAML,
compiles the LangGraph runner, invokes the graph end-to-end, and renders
the resulting :class:`CausalReport` to stdout with rich formatting plus a
LangSmith trace pointer when tracing is active.

The CLI is the sole reader of the final state snapshot per the architecture
rule that the synthesizer is the only writer of ``causal_report``.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final
from uuid import UUID

import yaml
from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.run_collector import RunCollectorCallbackHandler
from langsmith import Client as LangSmithClient
from pydantic import ValidationError
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from expertview.evidence.models import CausalReport, Finding, Hypothesis, Incident
from expertview.orchestration.runner import (
    DISPATCHER_NODE,
    HUMAN_FACTORS_NODE,
    LANGSMITH_API_KEY_ENV,
    LANGSMITH_PROJECT_ENV,
    LANGSMITH_TRACING_ENV,
    SPAWNING_JOIN_NODE,
    SUB_INVESTIGATOR_NODE,
    SYNTHESIZER_NODE,
    make_graph,
)
from expertview.orchestration.state import ExpertViewState
from expertview.orchestration.streaming import (
    ACTIVE,
    COMPLETE,
    NODE_LABELS,
    SKIPPED,
    WAITING,
    SpawnDecision,
    advance_status,
    initial_status,
    stream_run,
)

_CONFIDENCE_BAR_WIDTH: Final = 24


def main(argv: Sequence[str] | None = None) -> int:
    _maybe_load_env_file()
    _force_utf8_streams()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "demo":
        return asyncio.run(_run_demo(args.incident, live=args.live))

    parser.print_help(sys.stderr)
    return 2


def _force_utf8_streams() -> None:
    # LLM output regularly contains Unicode (curly quotes, NBSP hyphens, em
    # dashes) that cp1252 cannot encode. Reconfiguring stdout/stderr to UTF-8
    # with `errors="replace"` keeps the demo printable on legacy Windows shells
    # without crashing on stray glyphs.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            continue


def _maybe_load_env_file() -> None:
    # The factory in agents/llms.py refuses to load .env itself per the
    # 2026-05-26 python-dotenv decision. The CLI is the legitimate user-facing
    # boundary for env loading. python-dotenv is a dev dependency, so this is
    # a no-op outside the dev group; production callers export env vars or use
    # `uv run --env-file .env`.
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expertview",
        description="ExpertView — multi-agent RCA over industrial manufacturing incidents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser(
        "demo",
        help="Run the rehearsed demo end-to-end against a single incident YAML.",
    )
    demo.add_argument(
        "--incident",
        type=Path,
        required=True,
        help="Path to an incident YAML file (see data/incidents/).",
    )
    demo.add_argument(
        "--live",
        action="store_true",
        help=(
            "Stream investigator progress live in the terminal as each LangGraph "
            "node completes, then render the final report (mirrors the Streamlit surface)."
        ),
    )

    return parser


async def _run_demo(incident_path: Path, *, live: bool = False) -> int:
    console = Console(legacy_windows=False)
    try:
        incident = _load_incident(incident_path)
    except (FileNotFoundError, ValidationError, yaml.YAMLError) as exc:
        console.print(f"[bold red]Failed to load incident:[/bold red] {exc}")
        return 1

    try:
        compiled_graph = make_graph()
    except Exception:
        console.print("[bold red]Failed to compile the LangGraph runner:[/bold red]")
        console.print_exception()
        return 1

    initial_state: ExpertViewState = {
        "incident": incident,
        "findings": [],
        "hypotheses": [],
        "spawned_subinvestigations": [],
        "causal_report": None,
    }

    collector = RunCollectorCallbackHandler()
    config: RunnableConfig = {"callbacks": [collector]}
    try:
        if live:
            report = await _stream_demo_live(compiled_graph, initial_state, config, console)
        else:
            final_state = await compiled_graph.ainvoke(initial_state, config=config)
            report = final_state.get("causal_report") if isinstance(final_state, dict) else None
    except Exception:
        console.print("[bold red]Graph invocation failed:[/bold red]")
        console.print_exception()
        return 1

    if not isinstance(report, CausalReport):
        console.print("[bold red]Graph completed without producing a CausalReport.[/bold red]")
        return 1

    _render_report(report, console)
    _render_trace_notice(collector, console)
    return 0


async def _stream_demo_live(
    compiled_graph: object,
    initial_state: ExpertViewState,
    config: RunnableConfig,
    console: Console,
) -> CausalReport | None:
    # The live view mirrors the Streamlit surface: one row per NODE_LABELS entry,
    # flipping Waiting -> Active -> Complete (or Skipped) via the shared
    # `advance_status` flow helper as each node's ProgressEvent arrives. rich.live
    # is synchronous; stream_run is async — so the `async for` is driven inside this
    # already-async coroutine (run once via asyncio.run in main), never a nested loop.
    status_by_node = initial_status()
    findings_by_node: dict[str, list[Finding]] = {}
    findings_count = 0
    spawn_decision: SpawnDecision | None = None
    report: CausalReport | None = None

    with Live(
        _status_table(status_by_node, findings_count),
        console=console,
        refresh_per_second=8,
    ) as live:
        async for event in stream_run(compiled_graph, initial_state, config=config):  # type: ignore[arg-type]
            status_by_node = advance_status(status_by_node, event)
            findings_count = event.findings_count
            if event.findings:
                findings_by_node[event.node_name] = list(event.findings)
            if event.spawn_decision is not None:
                spawn_decision = event.spawn_decision
            live.update(
                _status_table(status_by_node, findings_count, findings_by_node, spawn_decision)
            )
            if event.causal_report is not None:
                report = event.causal_report

    return report


def _status_table(
    status_by_node: dict[str, str],
    findings_count: int,
    findings_by_node: dict[str, list[Finding]] | None = None,
    spawn_decision: SpawnDecision | None = None,
) -> Table:
    findings_by_node = findings_by_node or {}
    table = Table(
        title=f"Investigation progress — {findings_count} findings so far",
        show_lines=False,
        expand=True,
    )
    table.add_column("Stage", overflow="fold")
    table.add_column("Status", no_wrap=True)
    table.add_column("Detail", overflow="fold")
    for node_name, label in NODE_LABELS.items():
        status = status_by_node.get(node_name, WAITING)
        stage = Text(label, style="strike" if status == SKIPPED else "")
        detail = _status_detail(
            node_name, status, findings_by_node.get(node_name, []), spawn_decision
        )
        table.add_row(stage, _status_cell(status), detail, style=_row_style(status))
        # Divider lines mirror the Streamlit grouping: entry stage, the five
        # parallel investigators, then the routing + synthesis stages.
        if node_name in (DISPATCHER_NODE, HUMAN_FACTORS_NODE):
            table.add_section()
    return table


def _status_detail(
    node_name: str,
    status: str,
    node_findings: list[Finding],
    spawn_decision: SpawnDecision | None,
) -> Text:
    if node_name == SPAWNING_JOIN_NODE and spawn_decision is not None:
        return Text(spawn_decision.reason)
    if node_name == SUB_INVESTIGATOR_NODE and status == SKIPPED:
        return Text("Skipped — not triggered for this incident.")
    if node_name == SYNTHESIZER_NODE and status == COMPLETE:
        return Text("Merged all findings; converged on the causal report.")
    if node_findings:
        top = node_findings[0]
        return Text(f"{len(node_findings)} finding(s): {top.claim}")
    return Text("")


def _status_cell(status: str) -> Text:
    return Text(f"{_status_glyph(status)} {status}", style=_row_style(status))


def _status_glyph(status: str) -> str:
    done, active, waiting, skipped = _status_glyphs()
    return {
        COMPLETE: done,
        ACTIVE: active,
        WAITING: waiting,
        SKIPPED: skipped,
    }.get(status, waiting)


def _status_glyphs() -> tuple[str, str, str, str]:
    # Mirror the _bar_glyphs fallback: legacy cp1252 consoles cannot encode the
    # filled/half/ring/cross glyphs, so degrade to ASCII when stdout is not UTF.
    encoding = (sys.stdout.encoding or "").lower()
    if encoding.startswith("utf"):
        return ("●", "◐", "○", "⊘")
    return ("*", ">", ".", "x")


def _row_style(status: str) -> str:
    return {
        COMPLETE: "green",
        ACTIVE: "yellow",
        WAITING: "dim",
        SKIPPED: "dim",
    }.get(status, "dim")


def _load_incident(path: Path) -> Incident:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Incident.model_validate(raw)


def _render_report(report: CausalReport, console: Console) -> None:
    console.print(
        Panel.fit(
            Text(f"Incident: {report.incident_id}\nGenerated: {report.generated_at.isoformat()}"),
            title="ExpertView Causal Report",
            border_style="cyan",
        )
    )

    console.print(
        Panel(
            Text(report.confidence_summary, justify="left"),
            title="Confidence summary",
            border_style="magenta",
        )
    )

    if report.verdict_reasoning.strip():
        console.print(
            Panel(
                Text(report.verdict_reasoning, justify="left"),
                title="Why this is the root cause",
                border_style="cyan",
            )
        )

    console.print(_top_hypotheses_table(report.top_hypotheses))

    if report.alternatives_summary.strip():
        console.print(
            Panel(
                Text(report.alternatives_summary, justify="left"),
                title="What else was considered",
                border_style="yellow",
            )
        )

    if report.causal_chain:
        console.print(_causal_chain_table(report))

    console.print(_citations_panel(report))


def _top_hypotheses_table(hypotheses: list[Hypothesis]) -> Table:
    table = Table(title="Top hypotheses", show_lines=True, expand=True)
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("Confidence", no_wrap=True)
    table.add_column("Domain", no_wrap=True)
    table.add_column("Claim", overflow="fold")
    for index, hypothesis in enumerate(hypotheses, start=1):
        table.add_row(
            str(index),
            f"{_confidence_bar(hypothesis.confidence)} {hypothesis.confidence:.2f}",
            hypothesis.domain_origin,
            hypothesis.claim,
        )
    return table


def _causal_chain_table(report: CausalReport) -> Table:
    table = Table(title="Causal chain", show_lines=True, expand=True)
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("Cause", overflow="fold")
    table.add_column("Effect", overflow="fold")
    table.add_column("Strength", no_wrap=True)
    table.add_column("Rationale", overflow="fold")

    for index, link in enumerate(report.causal_chain, start=1):
        effect = link.effect
        effect_text = effect.claim if isinstance(effect, Hypothesis) else effect.description
        table.add_row(
            str(index),
            link.cause.claim,
            effect_text,
            f"{link.strength:.2f}",
            link.rationale,
        )
    return table


def _citations_panel(report: CausalReport) -> Panel:
    citations: list[str] = []
    seen: set[str] = set()
    for hypothesis in report.top_hypotheses:
        for finding in hypothesis.supporting_findings:
            for citation in finding.citations:
                if citation not in seen:
                    seen.add(citation)
                    citations.append(citation)

    body = (
        "\n".join(f"{i}. {citation}" for i, citation in enumerate(citations, start=1))
        if citations
        else "(no citations on the synthesized report)"
    )
    return Panel(Text(body), title="Citations", border_style="green")


def _confidence_bar(value: float, width: int = _CONFIDENCE_BAR_WIDTH) -> str:
    clamped = max(0.0, min(1.0, value))
    filled = round(clamped * width)
    fill_char, empty_char = _bar_glyphs()
    return fill_char * filled + empty_char * (width - filled)


def _bar_glyphs() -> tuple[str, str]:
    # Windows legacy consoles default to cp1252 and cannot encode U+2588/U+2591.
    # Fall back to ASCII glyphs when stdout encoding is not a UTF flavor.
    encoding = (sys.stdout.encoding or "").lower()
    if encoding.startswith("utf"):
        return ("█", "░")
    return ("#", "-")


def _render_trace_notice(collector: RunCollectorCallbackHandler, console: Console) -> None:
    tracing_active = (
        os.environ.get(LANGSMITH_TRACING_ENV, "").strip().lower() == "true"
        and os.environ.get(LANGSMITH_API_KEY_ENV, "").strip() != ""
    )
    if not tracing_active:
        console.print(
            "[yellow]LangSmith tracing disabled.[/yellow] Set LANGSMITH_API_KEY "
            "(and optionally LANGSMITH_PROJECT) to capture traces."
        )
        return

    project = os.environ.get(LANGSMITH_PROJECT_ENV, "default").strip() or "default"
    run_id = _first_run_id(collector)
    if run_id is None:
        console.print(
            f"[green]LangSmith tracing active[/green] (project '{project}'), "
            "but no run was captured by the collector."
        )
        return

    url = _safe_run_url(run_id)
    if url is None:
        console.print(
            f"[green]LangSmith trace captured[/green] (project '{project}', run id {run_id}). "
            "Open https://smith.langchain.com to view the trace."
        )
        return

    console.print(f"[green]LangSmith trace:[/green] {url}")


def _first_run_id(collector: RunCollectorCallbackHandler) -> UUID | None:
    runs = getattr(collector, "traced_runs", []) or []
    if not runs:
        return None
    first = runs[0]
    return getattr(first, "id", None)


def _safe_run_url(run_id: UUID) -> str | None:
    try:
        return LangSmithClient().read_run(run_id).url
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
