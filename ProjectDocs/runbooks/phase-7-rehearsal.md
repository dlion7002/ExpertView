# Phase 7 Rehearsal Runbook — Paid-Synth Swap, Three Runs, Trace Export

> **Read end-to-end before firing the first paid run.** This runbook assumes a single linear pass; the paid-synth section spends OpenRouter credit.
>
> **When to use this**: post-merge of [Phase 7 Task 3](../phases/phase-7/task-3-paid-synth-rehearsal-and-readme.md), with `main` at the `v0.8.0-demo` tag, on a demo-capable laptop. The runbook covers the four human steps the executing agent could not perform: the paid-synth swap, three observed demo runs, the live trace capture, and the watched observation.
>
> **Time budget**: ~30 minutes of active screen time once env is configured. Most of that is waiting for the LangGraph runs to finish.
>
> **OpenRouter credit at risk**: ≤$0.50 per paid run on `anthropic/claude-opus-4.7` at current pricing (synthesizer call only; investigators stay on the free build-phase models). Three paid runs ≈ ≤$1.50.

---

## Section 1 — Pre-flight (≤5 minutes)

Set the four env vars in PowerShell. Leave `EXPERTVIEW_SYNTH_MODEL` **unset** for the warm-up runs in Section 2; the build-phase default (`deepseek/deepseek-v4-flash:free`) is the right thing for warm-up.

```powershell
$env:OPENROUTER_API_KEY = "<your OpenRouter key>"
$env:LANGSMITH_API_KEY  = "<your LangSmith key>"
$env:LANGSMITH_PROJECT  = "expertview-rehearsal"
$env:LANGSMITH_TRACING  = "true"
Remove-Item Env:EXPERTVIEW_SYNTH_MODEL -ErrorAction SilentlyContinue
```

Confirm OpenRouter dashboard shows budget headroom: <https://openrouter.ai/settings/credits>

Confirm clean tree on `main` at the phase tag:

```powershell
git switch main
git pull --ff-only
git status                  # expect "nothing to commit, working tree clean"
git describe --tags --exact-match HEAD   # expect: v0.8.0-demo
```

Run the doctor:

```powershell
uv run python -m expertview.cli doctor
```

Expected: every non-info row passes. If the embedding row fails because the local cache is empty, the first `demo` run will populate it (~30s one-time download).

---

## Section 2 — Warm-up runs on the free build synth

Fire one CLI demo per incident on the free build-phase synthesizer. The `--live` flag exercises the same streaming surface the Streamlit demo uses, so a problem there shows up here too.

```powershell
uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml --live
```

```powershell
uv run python -m expertview.cli demo --incident data/incidents/process_recipe_drift.yaml --live
```

Expected from each:

- All five investigator rows turn Complete; the sub-investigator row either Completes (spawned) or is Skipped with a one-line reason.
- A `CausalReport` renders: verdict reasoning panel, top hypotheses table with confidence bars, causal chain table, citations panel.
- A green `LangSmith trace: <url>` line. Open one trace in the browser — confirm the parallel fan-out is visible across the five investigator child runs.

If either warm-up run hangs, errors, or produces no report, **stop** and fix before spending paid credit. The most likely cause is a stale `.cache/rag/` directory — delete it and re-run; see [agents/llms.py `create_embeddings` docstring](../../src/expertview/agents/llms.py) for the cache-invalidation rule.

---

## Section 3 — Paid-synth swap (three observed runs)

Pick the current paid frontier model ID from the OpenRouter catalog at rehearsal time (<https://openrouter.ai/models?supported_parameters=tools>). The example below uses `anthropic/claude-opus-4.7`, which is illustrative — substitute the actual ID OpenRouter lists when you are firing the rehearsal.

```powershell
$env:EXPERTVIEW_SYNTH_MODEL = "anthropic/claude-opus-4.7"
```

Three runs total, matching the "three consecutive clean runs" verbiage in [build_plan.md §Phase 7](../build_plan.md). The two CLI runs prove the demo holds up surface-independently; the Streamlit run is the watched-demo gate.

### Run 3a — CLI, CNC incident

```powershell
uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml --live
```

### Run 3b — CLI, process-recipe-drift incident

```powershell
uv run python -m expertview.cli demo --incident data/incidents/process_recipe_drift.yaml --live
```

### Run 3c — Streamlit, CNC incident (the watched-demo surface)

In a second PowerShell window with the same env vars exported, fire:

```powershell
uv run streamlit run src/expertview/ui/app.py
```

Open the local Streamlit URL it prints. Select the `cnc_out_of_tolerance.yaml` incident in the sidebar; click **Run investigation**. Note the LangSmith run ID (or the LangSmith trace URL) the UI shows after the run completes — that ID is the input to Section 4.

**Expected from each of the three runs**: top-cause domain identified, confidence bars rendered, citations panel populated, LangSmith trace URL available. The paid synth's verdict reasoning prose should be visibly richer than the build-phase free-synth output from Section 2; that improvement is the rehearsal's reason for existing.

**Record each run's outputs in the Section 7 log table as you go.**

---

## Section 4 — Trace export

Capture the third (Streamlit) run as an artifact under `data/traces/`. Use the naming convention from [data/traces/README.md](../../data/traces/README.md):

```text
<incident-slug>__<synth-model-slug>__<UTC-timestamp>.json
```

Substitute `<RUN_ID>` with the LangSmith run UUID from Run 3c and a timestamp of your choice:

```powershell
uv run python -m expertview.cli trace-export `
  --run-id <RUN_ID> `
  --out data/traces/cnc_out_of_tolerance__claude-opus-4-7__20260528T143000Z.json
```

Expected: a `Exported trace <UUID> -> <path>` line. If the artifact exceeds 256 KB, the export prints a stderr warning; 512 KB is the working ceiling for a committed artifact, 1 MB is the hard ceiling from [CLAUDE.md](../../CLAUDE.md).

Committing the artifact is your call:

- **Commit it** if you want the offline-replay fallback to work directly from a fresh checkout (Plan B for venue network outage during the hackathon).
- **Skip the commit** if you would rather keep the repo small and re-capture later.

If committing, stage and commit on a separate `chore/` branch — not on `main`:

```powershell
git switch -c chore/vendor-rehearsal-trace
git add data/traces/cnc_out_of_tolerance__*.json
git commit -m "chore: vendor phase-7 rehearsal trace artifact"
git push -u origin chore/vendor-rehearsal-trace
gh pr create --fill
```

---

## Section 5 — Replay sanity check

Replay the artifact and confirm the rendered output matches Run 3c's live render:

```powershell
uv run python -m expertview.cli replay --trace data/traces/cnc_out_of_tolerance__claude-opus-4-7__20260528T143000Z.json
```

Expected: identical verdict reasoning, identical top hypotheses, identical citations. The trace-URL line at the bottom is replaced by a yellow `(replay from <path>)` line followed by the original LangSmith trace URL in dim text. **No OpenRouter call.** Confirm by watching the OpenRouter dashboard credit counter — it should not move during the replay.

If the replay output differs from the live render, the artifact is corrupted; re-export from the same LangSmith run ID and try again.

---

## Section 6 — Watched observation

Pull in a colleague (or anyone unfamiliar with ExpertView) and run the Streamlit surface against the CNC incident one more time. **Do not narrate.** Ask them, after the run completes:

1. What did the system do? (Expected: "five investigators ran in parallel".)
2. Did anything dynamic happen? (Expected: they describe the sub-investigator spawn-or-skip, including the reason text the UI shows.)
3. What is the top cause and how confident is the system? (Expected: they read the top hypothesis claim and confidence bar without help.)
4. Where would you click to see what the model actually did? (Expected: they click the LangSmith trace link.)

If they need prompting on any of these four, **that is feedback for a follow-up UI fix** — capture the gap in the Section 7 log table's observer-note column. The fix is not part of Phase 7; it is candidate scope for the next phase.

---

## Section 7 — What to do when X happens

### X = OpenRouter 429 mid-run

The `RetryingLlm` wrapper in [src/expertview/agents/llms.py](../../src/expertview/agents/llms.py) (introduced in Phase 7 Task 1) retries `429` and `5xx` up to 3 attempts with bounded backoff + full jitter, honoring `Retry-After`. If a run still fails after the retry cap is exhausted, drop the investigator concurrency from 5 to 3 by editing the `INVESTIGATOR_CONCURRENCY` constant in that file (line near the top) and re-run. Do not commit the change — it is a transient mitigation.

### X = Venue network outage / OpenRouter unreachable

Switch to replay mode against the most recent committed artifact under `data/traces/`:

```powershell
uv run python -m expertview.cli replay --trace data/traces/<most-recent>.json
```

Replay is pure presentation — no OpenRouter call, no LangSmith call (the trace URL is read from the artifact), no embedding load. The yellow `(replay from <path>)` line is the honest signal to observers that this is a captured run.

### X = Judge asks an off-script question about the topology

In Streamlit, click the **Topology** tab — it renders the LangGraph as a Mermaid diagram via `streamlit-mermaid`. For deeper architectural questions, open [ProjectDocs/architecture.md §4](../architecture.md) (the module-map section) in a separate window.

### X = Embedding-model download stalls

The first `demo` run after a fresh checkout downloads `BAAI/bge-small-en-v1.5` (~30 MB). If it stalls, run `uv run python -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='BAAI/bge-small-en-v1.5').embed_query('ping')"` in a separate window to force the cache fill explicitly, then re-run the demo.

---

## Section 8 — Rehearsal log

Fill in one row per run. Empty rows pre-populated for the three paid runs from Section 3.

| Date (UTC) | Incident | Synth model | Top cause | Runtime (s) | Observer note |
|---|---|---|---|---|---|
|  | `cnc_out_of_tolerance.yaml` | (paid) |  |  |  |
|  | `process_recipe_drift.yaml` | (paid) |  |  |  |
|  | `cnc_out_of_tolerance.yaml` (Streamlit) | (paid) |  |  |  |

After the rehearsal:

- Note in `decisions.md` (or the merge commit message for `v0.8.0-demo`) the actual paid frontier model ID used and whether the trace artifact was committed.
- If any Section 6 observer note flagged a UI gap, surface it in `open_questions.md` as a Phase 8 candidate.
