# ExpertView

Multi-agent Root Cause Analysis system for industrial manufacturing incidents. Five domain investigators (mechanical, process, supply chain, environmental, human factors) run in parallel as LangGraph branches against domain-specific RAG stores, share evidence through the LangGraph shared state, spawn sub-investigations dynamically through conditional edges, and converge on an evidence-weighted causal report. LLMs are routed through a single OpenRouter gateway (free open-weight models during build; a paid frontier model selectable for the demo via one env var); embeddings run locally via `BAAI/bge-small-en-v1.5`. ExpertView is built as a CV/portfolio artifact for AI-platform engineering review; the shapeX 1-day hackathon is a milestone the build also targets. See [ProjectDocs/project_introduction.md](ProjectDocs/project_introduction.md) for the full framing.

## Requirements

- Python 3.11 or newer.
- [`uv`](https://docs.astral.sh/uv/) for dependency management.
- An `OPENROUTER_API_KEY` (any tier — the build defaults to free models).

`uv sync` installs every runtime dependency, including Streamlit and `streamlit-mermaid` for the demo UI. No separate `pip install` step.

## Environment variables

| Variable | Required? | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | required | Single key for OpenRouter; used for both build-phase free models and the paid frontier synthesizer. |
| `LANGSMITH_API_KEY` | recommended | Enables LangSmith tracing on every node and unlocks the offline-replay path via `expertview trace-export`. |
| `LANGSMITH_PROJECT` | optional | LangSmith project name. Defaults to `default`. |
| `EXPERTVIEW_SYNTH_MODEL` | optional | OpenRouter model ID for the synthesizer. Defaults to `deepseek/deepseek-v4-flash:free` for build runs; set to a paid frontier ID such as `anthropic/claude-opus-4.7` for demo runs. |

The CLI loads `.env` from the repo root via `python-dotenv` (dev dependency); exporting the same variables in the shell also works.

## Run it

One-time install:

```powershell
uv sync
```

End-to-end CLI demo against the canonical CNC incident:

```powershell
uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml
```

Expected: a rendered `CausalReport` (verdict reasoning, top hypotheses with confidence bars, causal chain, citations) plus a `LangSmith trace:` URL when tracing is active. Add `--live` to stream investigator status while the graph runs.

Streamlit demo surface:

```powershell
uv run streamlit run src/expertview/ui/app.py
```

Expected: a single-screen UI with investigator status, the spawn-or-skip decision, the final report, and a Topology tab rendering the LangGraph as Mermaid.

## Offline replay

If the venue network or OpenRouter is unavailable, replay a captured run:

```powershell
uv run python -m expertview.cli replay --trace data/traces/<artifact>.json
```

Replay re-renders the saved `CausalReport` through the same code path as the live demo — same panels, same tables, same citations — with one labeled `(replay from <path>)` line in place of the live trace URL. No graph invocation, no OpenRouter call, no embedding load. The artifact format and naming convention are documented in [data/traces/README.md](data/traces/README.md). Capture an artifact with `expertview trace-export --run-id <UUID> --out data/traces/<file>.json` after a successful live run.

## Pre-flight check

Before spending paid OpenRouter credit on a rehearsal, run the doctor:

```powershell
uv run python -m expertview.cli doctor
```

Verifies that the required and recommended env vars are set, the incident YAMLs parse, the Streamlit dependencies import, the local embedding model loads, the LangSmith client connects, and the `trace-export` / `replay` subcommands are registered. Exits non-zero on any failure; use `--skip-embedding` or `--skip-langsmith` to skip the two checks that need a model download or a network round-trip.

## Demo rehearsal

The full paid-synth rehearsal — warm-up runs, the synthesizer swap, three observed runs, the trace export, the replay sanity check, and the "what to do when X happens" plays — is captured as a copy-paste checklist in [ProjectDocs/runbooks/phase-7-rehearsal.md](ProjectDocs/runbooks/phase-7-rehearsal.md).

## Documentation map

- [ProjectDocs/vision.md](ProjectDocs/vision.md) — product intent, target users, success criteria, non-goals.
- [ProjectDocs/architecture.md](ProjectDocs/architecture.md) — module map, protocols, data flow, tech stack.
- [ProjectDocs/build_plan.md](ProjectDocs/build_plan.md) — phase order and quality gates.
- [ProjectDocs/decisions.md](ProjectDocs/decisions.md) — locked decisions with reasons.
- [ProjectDocs/branching_strategy.md](ProjectDocs/branching_strategy.md) and [CONTRIBUTING.md](CONTRIBUTING.md) — the lightweight GitHub Flow used in this repo.
