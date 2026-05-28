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
import json
import os
import re
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final
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
    INVESTIGATOR_NODES,
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

TRACE_ARTIFACT_SCHEMA_VERSION: Final = 1
EXPERTVIEW_SYNTH_MODEL_ENV: Final = "EXPERTVIEW_SYNTH_MODEL"
_TRACE_SIZE_WARN_BYTES: Final = 256 * 1024
_TRACE_LIST_LOOKBACK_HOURS: Final = 24
_TRACE_CHILD_NAMES: Final = (*INVESTIGATOR_NODES, SUB_INVESTIGATOR_NODE)
# Allow-list assembly never grabs run.extra or child inputs; this regex is the
# second line of defense that fails an export loudly if any allow-listed value
# happens to nest a key that smells like a credential.
_SECRET_KEY_PATTERN: Final = re.compile(r"(?i)(api[_-]?key|authorization|bearer|secret|token)")


def main(argv: Sequence[str] | None = None) -> int:
    _maybe_load_env_file()
    _force_utf8_streams()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "demo":
        return asyncio.run(_run_demo(args.incident, live=args.live))
    if args.command == "trace-export":
        return _run_trace_export(run_id=args.run_id, out_path=args.out)
    if args.command == "replay":
        return _run_replay(args.trace)

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

    export = subparsers.add_parser(
        "trace-export",
        help=(
            "Snapshot a LangSmith run to a JSON artifact under data/traces/ so the "
            "demo can be replayed offline if the venue network or OpenRouter fails."
        ),
    )
    export.add_argument(
        "--run-id",
        type=str,
        default=None,
        help=(
            "LangSmith run ID (UUID) to export. If omitted, the most recent root run "
            f"in LANGSMITH_PROJECT from the last {_TRACE_LIST_LOOKBACK_HOURS}h is used."
        ),
    )
    export.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON path (typically data/traces/<incident>__<model>__<UTC>.json).",
    )

    replay = subparsers.add_parser(
        "replay",
        help=(
            "Re-render a captured CausalReport from a saved LangSmith trace artifact. "
            "Pure presentation — no graph invocation, no OpenRouter call, no embedding load."
        ),
    )
    replay.add_argument(
        "--trace",
        type=Path,
        required=True,
        help="Path to a JSON artifact produced by `expertview trace-export`.",
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


def _run_trace_export(*, run_id: str | None, out_path: Path) -> int:
    console = Console(legacy_windows=False)

    api_key = os.environ.get(LANGSMITH_API_KEY_ENV, "").strip()
    if not api_key:
        console.print(
            f"[bold red]{LANGSMITH_API_KEY_ENV} is not set; cannot read a LangSmith "
            "run. Set it (and LANGSMITH_PROJECT) and try again.[/bold red]"
        )
        return 1

    project = (os.environ.get(LANGSMITH_PROJECT_ENV, "") or "default").strip() or "default"

    try:
        client = LangSmithClient()
    except Exception as exc:
        console.print(f"[bold red]Failed to construct LangSmithClient:[/bold red] {exc}")
        return 1

    if run_id is None:
        resolved = _resolve_latest_run_id(client, project, console)
        if resolved is None:
            return 1
        run_uuid = resolved
    else:
        try:
            run_uuid = UUID(run_id)
        except ValueError:
            console.print(f"[bold red]--run-id is not a valid UUID: {run_id!r}[/bold red]")
            return 1

    try:
        run = client.read_run(run_uuid, load_child_runs=True)
    except Exception as exc:
        console.print(f"[bold red]Failed to read run {run_uuid}:[/bold red] {exc}")
        return 1

    try:
        artifact = _build_artifact(run, project=project)
        _redact_or_raise(artifact)
        payload = json.dumps(artifact, indent=2, default=str)
    except RuntimeError as exc:
        console.print(f"[bold red]Refusing to write artifact:[/bold red] {exc}")
        return 1
    except Exception as exc:
        console.print(f"[bold red]Failed to assemble artifact:[/bold red] {exc}")
        return 1

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    except OSError as exc:
        console.print(f"[bold red]Failed to write artifact to {out_path}:[/bold red] {exc}")
        return 1

    size_bytes = len(payload.encode("utf-8"))
    if size_bytes > _TRACE_SIZE_WARN_BYTES:
        print(
            f"Warning: trace artifact is {size_bytes // 1024} KB. "
            "CLAUDE.md hard rules forbid committing generated data >1 MB; keep "
            "data/traces/ small (one or two artifacts at a time).",
            file=sys.stderr,
        )

    console.print(f"[green]Exported trace[/green] {run_uuid} -> {out_path}")
    return 0


def _resolve_latest_run_id(client: LangSmithClient, project: str, console: Console) -> UUID | None:
    since = datetime.now(UTC) - timedelta(hours=_TRACE_LIST_LOOKBACK_HOURS)
    list_kwargs: dict[str, Any] = {
        "project_name": project,
        "is_root": True,
        "filter": f'gte(start_time, "{since.isoformat()}")',
    }
    try:
        candidates = list(client.list_runs(**list_kwargs))
    except Exception as exc:
        console.print(f"[bold red]Failed to list runs in project '{project}':[/bold red] {exc}")
        return None

    if not candidates:
        console.print(
            f"[bold red]No root runs found in project '{project}' in the last "
            f"{_TRACE_LIST_LOOKBACK_HOURS}h. Pass --run-id explicitly.[/bold red]"
        )
        return None

    candidates.sort(key=lambda r: getattr(r, "start_time", datetime.min), reverse=True)
    latest = candidates[0]
    latest_id = getattr(latest, "id", None)
    latest_start = getattr(latest, "start_time", None)
    if latest_id is None:
        console.print(
            f"[bold red]Latest run in '{project}' has no id attribute; cannot "
            "auto-resolve. Pass --run-id explicitly.[/bold red]"
        )
        return None

    print(
        f"No --run-id provided; using latest root run {latest_id} "
        f"(start_time={latest_start}). Re-run with --run-id <uuid> to pin a different one.",
        file=sys.stderr,
    )
    return latest_id if isinstance(latest_id, UUID) else UUID(str(latest_id))


def _build_artifact(run: object, *, project: str) -> dict[str, Any]:
    outputs = getattr(run, "outputs", None) or {}
    inputs = getattr(run, "inputs", None) or {}
    child_runs = getattr(run, "child_runs", None) or []

    return {
        "schema_version": TRACE_ARTIFACT_SCHEMA_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "langsmith": {
            "project": project,
            "run_id": str(getattr(run, "id", "")),
            "run_name": getattr(run, "name", None),
            "run_url": getattr(run, "url", None),
            "start_time": _iso_or_none(getattr(run, "start_time", None)),
            "end_time": _iso_or_none(getattr(run, "end_time", None)),
            "status": getattr(run, "status", None),
            "error": getattr(run, "error", None),
        },
        "synthesizer_model": os.environ.get(EXPERTVIEW_SYNTH_MODEL_ENV),
        "incident": inputs.get("incident"),
        "causal_report": _extract_causal_report(outputs),
        "findings_by_domain": _extract_findings_by_domain(child_runs),
        "child_run_summaries": _extract_child_summaries(child_runs),
    }


def _iso_or_none(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _extract_causal_report(outputs: dict[str, Any] | None) -> dict[str, Any] | None:
    # LangGraph typically emits {"causal_report": {...}} as the run's outputs;
    # in some compile paths the bare report dict has surfaced at the root. Handle
    # both shapes so a small library bump does not silently break replay.
    if not outputs:
        return None
    nested = outputs.get("causal_report")
    if isinstance(nested, dict):
        return nested
    if "incident_id" in outputs and "top_hypotheses" in outputs:
        return dict(outputs)
    return None


def _extract_findings_by_domain(child_runs: Iterable[object]) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {}
    for child in child_runs:
        name = getattr(child, "name", None)
        if name not in _TRACE_CHILD_NAMES:
            continue
        outputs = getattr(child, "outputs", None) or {}
        findings = outputs.get("findings")
        if findings:
            result[name] = list(findings)
    return result


def _extract_child_summaries(child_runs: Iterable[object]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for child in child_runs:
        summaries.append(
            {
                "name": getattr(child, "name", None),
                "run_type": getattr(child, "run_type", None),
                "status": getattr(child, "status", None),
                "error": getattr(child, "error", None),
                "start_time": _iso_or_none(getattr(child, "start_time", None)),
                "end_time": _iso_or_none(getattr(child, "end_time", None)),
            }
        )
    return summaries


def _redact_or_raise(node: object) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and _SECRET_KEY_PATTERN.search(key):
                raise RuntimeError(
                    f"artifact contains a key that looks like a secret: {key!r}. "
                    "Allow-list the field explicitly or drop it before export."
                )
            _redact_or_raise(value)
    elif isinstance(node, list):
        for item in node:
            _redact_or_raise(item)


def _run_replay(trace_path: Path) -> int:
    console = Console(legacy_windows=False)

    try:
        text = trace_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        console.print(f"[bold red]Trace artifact not found: {trace_path}[/bold red]")
        return 1
    except OSError as exc:
        console.print(f"[bold red]Failed to read {trace_path}:[/bold red] {exc}")
        return 1

    try:
        artifact = json.loads(text)
    except json.JSONDecodeError as exc:
        console.print(f"[bold red]Invalid JSON in {trace_path}:[/bold red] {exc}")
        return 1

    if not isinstance(artifact, dict):
        console.print(f"[bold red]Trace artifact at {trace_path} is not a JSON object.[/bold red]")
        return 1

    causal_report_raw = artifact.get("causal_report")
    if causal_report_raw is None:
        console.print(
            f"[bold red]Trace artifact at {trace_path} has no captured causal_report; "
            "nothing to replay.[/bold red]"
        )
        return 1

    try:
        report = CausalReport.model_validate(causal_report_raw)
    except ValidationError as exc:
        console.print(f"[bold red]Captured CausalReport failed validation:[/bold red]\n{exc}")
        return 1

    _render_report(report, console)
    _render_replay_notice(trace_path, artifact, console)
    return 0


def _render_replay_notice(trace_path: Path, artifact: dict[str, Any], console: Console) -> None:
    langsmith = artifact.get("langsmith") if isinstance(artifact, dict) else None
    langsmith = langsmith if isinstance(langsmith, dict) else {}
    run_id = langsmith.get("run_id")
    project = langsmith.get("project")
    run_url = langsmith.get("run_url")
    exported_at = artifact.get("exported_at") if isinstance(artifact, dict) else None

    detail_bits: list[str] = []
    if run_id:
        detail_bits.append(f"captured run {run_id}")
    if project:
        detail_bits.append(f"project '{project}'")
    if exported_at:
        detail_bits.append(f"exported {exported_at}")
    detail = "; ".join(detail_bits) if detail_bits else "captured run"

    console.print(
        f"[yellow](replay from {trace_path})[/yellow] {detail}. "
        "No live OpenRouter or LangSmith calls."
    )
    if run_url:
        console.print(f"[dim]Original LangSmith trace: {run_url}[/dim]")


if __name__ == "__main__":
    raise SystemExit(main())
