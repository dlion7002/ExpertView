# Phase 6 — Demo-legibility fix (post-`/verify` follow-up)

> **Why this exists**: The Phase 6 watched-demo quality gate ("a third party can watch the
> demo and describe what is happening without prompting") surfaced three legibility gaps in the
> Streamlit surface. [task-3-cli-live-mode-and-verify.md](../phases/phase-6/task-3-cli-live-mode-and-verify.md)
> explicitly anticipates this: *"if they needed prompting, that is a UI-legibility fix in Task 2's
> surface, surfaced back as a follow-up before the phase is tagged."* This is that follow-up.
> It changes **surfaces only** — no graph topology, node, convergence-math, or prompt changes.

## The three reported gaps (user feedback)

1. **Topology graph** is static, small, and never reflects run progress — you can't tell which
   agent is done or active.
2. **Per-agent transparency** is missing — the panel shows only `Complete/Waiting`; you can't see
   what each investigator *found*, why the **Spawn Decision** went the way it did (the
   Sub-Investigator just shows `Waiting` forever when not triggered), or what the **Causal
   Synthesizer** did.
3. **Report reads as a fact dump**, not a flow to a decision — the same root cause is repeated
   verbatim across three causal-chain links, raw document excerpts render as giant `##` headers
   (because `st.caption` interprets markdown), and citations + excerpts repeat several times.

## Resolved decisions (from clarifying Q&A, 2026-05-27)

- **Scope**: Streamlit **and** mirror the same detail to the CLI live mode (Plan B parity).
- **Topology**: live recolor (waiting → active → done) + enlarge + legend. Mermaid via
  `st_mermaid` stays the engine (locked 2026-05-25).
- **Report**: verdict-first narrative — plain-language root cause + confidence first, then
  "symptoms this explains" (collapsing the repeated-cause links), then evidence/excerpts behind
  expanders.
- **Per-agent detail**: summary inline per agent, full findings/citations behind a per-agent
  expander; Spawn Decision shows outcome + reason; synthesizer row states it merged all findings.

## Architecture constraints honored

- `ui/` imports `orchestration/` + `evidence/models` only — never `agents/` or `rag/` internals.
- The progress-event contract lives in `orchestration/streaming.py` and stays **surface-agnostic**:
  both the Streamlit app and the CLI consume the same enriched events and the same flow helper.
- The spawn predicate stays single-sourced (`agents.spawning.is_bearing_anomaly`); `streaming.py`
  reuses it to label the decision (orchestration already imports agents in `runner.py`).
- No new dependencies. `streamlit_mermaid` is already used; topology recolor uses Mermaid `style`
  directives appended to the existing diagram string.

---

## Files affected

### `src/expertview/orchestration/streaming.py` (edit — shared core)
- **Add `SpawnDecision`** (frozen pydantic): `spawned: bool`, `reason: str`.
- **Enrich `ProgressEvent`** additively (existing fields unchanged):
  - `findings: list[Finding]` — the findings *this* node contributed (from its state patch).
    Default `[]`.
  - `spawn_decision: SpawnDecision | None` — set only on the `SPAWNING_JOIN_NODE` event.
- **`stream_run`**: accumulate findings as they stream; on the join event evaluate
  `is_bearing_anomaly` over the accumulated findings (mirrors `runner._should_spawn`) and attach a
  `SpawnDecision` with a human-readable reason. Attach each node's own `findings` to its event.
- **Add status constants + flow helpers** (surface-agnostic, used by both UIs):
  - `WAITING / ACTIVE / COMPLETE / SKIPPED` string constants.
  - `initial_status() -> dict[str, str]` (all nodes `Waiting`).
  - `advance_status(status, event) -> dict[str, str]`: marks the completed node `Complete` and
    proactively flips known successors to `Active` (dispatcher → 5 investigators; join → sub-investigator
    if spawned else synthesizer + mark sub-investigator `Skipped`; sub-investigator → synthesizer).
    Reads `event.spawn_decision`. This is the single source of the live-flow transitions.

### `src/expertview/ui/render.py` (edit — Streamlit presentation)
- **`render_progress_panel`** rewritten to accept `findings_by_node` + `spawn_decision` and render,
  per row: status chip (Waiting/Active/Complete/Skipped), inline finding count + top-claim snippet,
  and a per-agent expander with full findings + citation chips. Spawn Decision row shows the
  outcome + reason. Synthesizer row notes it merged all findings and converged.
- **Add `style_topology_mermaid(mermaid, status_by_node) -> str`**: appends Mermaid `style <node>`
  directives per node color from status. `render_topology` enlarged (height bump) + a small colored
  legend rendered beneath it.
- **`render_causal_report`** restructured into the verdict-first narrative:
  1. **Verdict** — top hypothesis claim as the headline, confidence metric + domain, the
     `confidence_summary` line.
  2. **"Symptoms this explains"** — collapse causal-chain links that share one cause into a single
     cause → bulleted symptom list (with per-link strength); render genuine multi-hop
     hypothesis→hypothesis chains as ordered steps when present.
  3. **Supporting evidence** — per-hypothesis findings + citation chips inside a collapsed expander.
  4. **Other hypotheses considered** — collapsed also-ran list (only if >1), so the viewer sees
     alternatives were weighed.
  5. **Sources** — one deduped `id → path` list; raw excerpts rendered as **plain text**
     (kills the `##`-as-header bug), hard-truncated, inside an expander.

### `src/expertview/ui/app.py` (edit — wiring)
- `_consume_run` accumulates `findings_by_node` + `spawn_decision`, calls `advance_status` per
  event, and re-renders **both** the status panel and the (restyled) topology each event so the
  graph recolors live.
- Session-state additions: `findings_by_node`, `spawn_decision`; `_reset_run_state` clears them.
- Topology re-render keyed on completion count so `st_mermaid` reliably repaints.

### `src/expertview/cli.py` (edit — Plan-B parity)
- `_stream_demo_live` uses `advance_status` (active/done/skipped) and tracks per-node findings +
  spawn decision.
- `_status_table` gains a **Detail** column (finding count + top claim; spawn reason on the Spawn
  Decision row; "Skipped — <reason>" on Sub-Investigator when not triggered) and color-codes rows
  by status (done=green, active=yellow, waiting=dim, skipped=dim/strike). Signature extended with
  defaulted params so it stays call-compatible.

### Tests
- `tests/unit/test_streaming.py`: extend to assert per-event `findings` and the `SpawnDecision` on
  the join event; add a no-spawn case (`spawned=False`). Existing assertions stay valid (additive).
- `tests/unit/test_cli.py`: update `_status_table` call for the new optional params; add a check
  that the Detail column renders a finding claim and the spawn reason.

### `ProjectDocs/decisions.md` (edit)
- Append one entry: ProgressEvent enriched with per-node `findings` + `SpawnDecision`, and the
  surface-agnostic `advance_status` flow helper added — both surfaces consume them; rationale =
  demo legibility; reversibility = easy (additive fields).

---

## Risks
- **Mermaid live recolor flicker**: re-rendering `st_mermaid` each event may flicker as the 5
  parallel branches finish near-simultaneously. Accepted per Q&A; `style` directives + a
  completion-keyed component avoid stale paints.
- **`advance_status` drift from the real graph**: the active-state transitions encode the runner's
  topology by hand. Mitigation: keep it minimal and centralized in `streaming.py` next to
  `NODE_LABELS`; it is presentation-only (never affects routing).
- **CLI test coupling**: `_status_table` signature change — mitigated with defaulted params and an
  updated test.
- **Report excerpt rendering**: switching excerpts to plain text changes the look; this is the fix
  (removes the giant-header artifact), not a regression.

## Verification
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` clean.
- `uv run streamlit run src/expertview/ui/app.py` — run the process-recipe-drift incident; confirm:
  topology recolors live; each agent shows what it found; Spawn Decision shows its reason and the
  Sub-Investigator reads "Skipped"; report leads with a plain verdict and no giant raw-doc headers.
- `uv run python -m expertview.cli demo --incident <path> --live` — confirm the Detail column and
  status colors mirror the app.
- `/verify` re-run of the watched-demo gate.
