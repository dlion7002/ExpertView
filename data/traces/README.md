# `data/traces/` — LangSmith trace artifacts

This directory holds JSON snapshots of successful ExpertView demo runs. The user
captures one (or two) such artifacts after a rehearsal so the demo can be
**replayed offline** if the venue network or OpenRouter is unavailable. Replay
goes through the same `_render_report` path as the live demo — same panels,
same tables, same citations — with one labeled `(replay from <path>)` line at
the bottom that replaces the live `LangSmith trace: …` URL.

## What is committed here

- This `README.md`, keeping the directory tracked on `main`.
- **No real trace artifacts.** Per Phase 7 Task 2 spec, the executing agent does
  not commit any captured run; the user captures the rehearsal artifact
  post-merge via the runbook in Phase 7 Task 3.

If a rehearsal artifact is checked in later, it MUST stay under the CLAUDE.md
1 MB hard ceiling for committed generated data. The export command warns to
stderr at 256 KB so the user notices early.

## Capturing an artifact

```powershell
uv run python -m expertview.cli trace-export --run-id <UUID> --out data/traces/<file>.json
```

`--run-id` is the UUID printed after a live demo by the `LangSmith trace:` line.
Omitting `--run-id` falls back to "most recent root run in `LANGSMITH_PROJECT`
from the last 24 hours" — fine for one-off rehearsals, but always pass an
explicit ID when the project has overlapping runs.

## Replaying an artifact

```powershell
uv run python -m expertview.cli replay --trace data/traces/<file>.json
```

The replay re-validates the captured `CausalReport` against
`expertview.evidence.models.CausalReport`, then renders it through the same
`_render_report` the live demo uses. **No graph invocation, no OpenRouter call,
no embedding load.** A malformed artifact or one whose captured `CausalReport`
fails pydantic validation exits non-zero with the validation error.

## Naming convention

```
<incident-slug>__<synth-model-slug>__<UTC-timestamp>.json
```

Example: `incident_alpha__claude-opus-4-7__20260528T143000Z.json`.

The slug pieces are user-chosen — the export command does not enforce a
filename. The convention exists so a directory listing tells you at a glance
which incident, which synthesizer model, and when each artifact was captured.

## Artifact schema (v1)

The export writes a JSON object with a `schema_version` field so a future
migration is visible. The top-level keys are an **allow-list** — nothing else
is written, no matter what the LangSmith `Run` object carries:

| Key | Type | Meaning |
|---|---|---|
| `schema_version` | int (`1`) | Pin against future format drift. |
| `exported_at` | ISO-8601 UTC | When the export ran. |
| `langsmith` | object | `{project, run_id, run_name, run_url, start_time, end_time, status, error}` for the root run. |
| `synthesizer_model` | string \| null | `EXPERTVIEW_SYNTH_MODEL` env value at export time (e.g. `anthropic/claude-opus-4.7`). |
| `incident` | object \| null | The `Incident` dict from the root run's inputs. |
| `causal_report` | object \| null | The `CausalReport` dict from the root run's outputs — the replay's source of truth. |
| `findings_by_domain` | `{domain → list[Finding]}` | Structured findings parsed from each investigator child run's outputs. |
| `child_run_summaries` | list | `{name, run_type, status, error, start_time, end_time}` per child run — metadata only. |

## Hard exclusions

The export deliberately **drops** the following, even though the LangSmith
`Run` object exposes them:

- `run.extra` — LangChain stuffs `invocation_params` here, which has historically
  carried `openai_api_key` / API base URLs. Never serialized.
- Child run `inputs` — full rendered prompts and any RAG-retrieved chunks. Only
  child `outputs["findings"]` is touched, never `inputs`.
- Any environment variable values, any API keys, any authentication headers.

A final **redactor** pass runs over the assembled artifact and raises if any
key matches `(?i)(api[_-]?key|authorization|bearer|secret|token)` — a backstop
in case the allow-list drifts in a future refactor.

## Guarantees

- **Reproduces the live render verbatim.** The replay calls the same
  `_render_report` the live demo uses; citations, confidence bars, the causal
  chain table, and the verdict-reasoning panel render identically.
- **Never re-invokes the graph or any LLM.** Replay is pure presentation.
- **Labels every replay.** A `(replay from <path>)` line at the bottom (in
  yellow) replaces the live `LangSmith trace: …` URL line — observers always
  know they are looking at a captured run, not a live one. The original run URL
  is surfaced below it in dim text so observers can still click through to the
  live trace if a network is available.
