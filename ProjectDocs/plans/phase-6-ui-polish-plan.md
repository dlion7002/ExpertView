# Phase 6 — Demo UI polish (visual pass on the legibility fix)

> **Why this exists**: The Phase 6 legibility fix
> ([phase-6-demo-legibility-plan.md](phase-6-demo-legibility-plan.md)) made the demo *legible*
> (live recolor, per-agent detail, verdict-first report). This follow-up makes it *attractive*:
> clear card boundaries, stronger heading hierarchy, status badges, a prominent conclusion, and
> less wall-of-text. **Surfaces only** — no graph topology, node, convergence-math, prompt, or
> streaming-contract changes. The investigation logic is untouched.

## Resolved decisions (clarifying Q&A, 2026-05-27)

- **Styling**: heavier custom CSS accepted (richer cards, gradient hero, custom badge pills),
  knowingly trading some Streamlit-upgrade robustness for polish. The `.streamlit/config.toml`
  dark-graphite + amber theme stays the base; CSS layers on top.
- **Scope**: both surfaces — Streamlit *and* the CLI live-mode status table (Plan-B parity, as
  Phase 6 established).
- **Layout**: polished single-page flow (incident → live investigation + topology → report,
  top-to-bottom). No tabs — the whole story stays visible for a live walkthrough.
- **Investigators**: one bordered card per investigator — status badge in the header, one-line
  inline summary, full findings behind a per-card expander.

## Architecture constraints honored

- `ui/` imports `orchestration/` + `evidence/models` only — unchanged.
- `streaming.py` contract (ProgressEvent, `advance_status`, `initial_status`, status constants,
  `SpawnDecision`) is **not** touched — both surfaces still consume the same events. The
  live-recolor wiring in `app.py::_consume_run` is preserved exactly (re-render status panel +
  topology per event, topology keyed on completion count).
- No new dependencies. Custom styling is injected CSS via `st.markdown(unsafe_allow_html=True)`;
  Mermaid stays `st_mermaid`; CLI stays `rich`.
- A single status→color palette is the source of truth, kept visually aligned with the existing
  `_STATUS_MERMAID_STYLE` (topology) and the CLI `_row_style` (rich colors), so badges, card
  accents, the topology legend, and the CLI table all read as one design.

---

## Files affected

### `src/expertview/ui/render.py` (edit — the bulk of the work)

**New shared styling primitives (module-private):**
- `_STATUS_PALETTE: Mapping[str, _StatusStyle]` — per status (Waiting/Active/Complete/Skipped):
  label, hex `fg`/`bg`/`border` for HTML pills, chosen to read on the dark theme and to match the
  Mermaid node colors already in `_STATUS_MERMAID_STYLE`.
- `inject_css() -> None` — one `st.markdown(<style>…</style>, unsafe_allow_html=True)` block:
  app header band, section-header rows, badge pills, card padding/rounded corners + per-status
  left-accent (via a hidden marker span + `:has()` selector on the bordered-container wrapper),
  the report verdict "hero" block, confidence bar, and chip styling for symptoms/assets/citations.
- `_badge(status) -> str` — returns the pill HTML for a status.
- `_section_header(title, *, subtitle=None, icon=None) -> None` — styled heading row replacing the
  bare `st.subheader`, giving consistent hierarchy across all four sections.
- `_chips(items) -> str` — inline chip HTML for symptom/asset/citation lists.

**`render_app_header() -> None`** (new): replaces the bare `st.title("ExpertView")` with a styled
header band (product name + one-line tagline + accent rule).

**`render_incident`** rewritten: a bordered card (`st.container(border=True)` + accent CSS) with a
section header, the summary, an observed-at chip, and symptoms/assets rendered as labeled chip
groups in two columns (no more bare bullet `st.write` lines).

**`render_topology`** improved: section header "Investigation topology" + an explanatory subtitle
("Five domain investigators run in parallel; a sub-investigation spawns only when a bearing anomaly
is found"), the `st_mermaid` graph (height kept), and a **colored legend** built from
`_STATUS_PALETTE` (HTML pills) instead of the emoji caption. Signature unchanged (`mermaid`, `key`).

**`render_progress_panel`** rewritten (same signature — `rows`, `findings_count`,
`findings_by_node`, `spawn_decision`): 
- Section header "Live investigation" + the evidence-findings count as a styled stat.
- A slim **Dispatcher** status line (entry stage).
- The **five investigator cards**: each a bordered container whose header HTML shows the
  investigator name + a status badge pill + finding count, an inline top-claim one-liner, and a
  collapsed `st.expander("What <label> found")` with the full findings + citation chips (existing
  `_render_citation_chips` reused). Per-status left-accent via the marker-span trick.
- A **Routing & synthesis** sub-block: Spawn Decision (outcome badge + reason), Sub-Investigator
  (badge; "Skipped — not triggered" when skipped), Causal Synthesizer (badge; "Merged all
  findings…" when complete) — rendered as slim accent rows, visually subordinate to the cards.
- All branching keys off the existing node-name constants; behavior/inputs identical, only layout
  changes, so live recolor is preserved.

**`render_causal_report`** restructured for prominence (same signature):
- Section header "Causal report" + incident/generated caption.
- **Verdict hero**: an HTML block (gradient/accent background, large claim headline, big confidence
  %, an HTML confidence bar, a domain chip) + the `confidence_summary`. This is the visual anchor
  of the page.
- "Symptoms this explains" / causal chain — kept, with `_section_header`-style subheads.
- Supporting evidence / Other hypotheses / Sources — kept behind collapsed expanders exactly as
  now (sources still rendered as **plain text** to preserve the `##`-header fix). 
- Helper split-out as needed (e.g. `_render_verdict_hero`) but the existing
  `_render_symptoms_explained`, `_render_supporting_evidence`, `_render_alternatives`,
  `_render_sources` are reused with light heading tweaks.

### `src/expertview/ui/app.py` (edit — wiring only)
- Call `render_app_header()` (replacing `st.title`) and `inject_css()` once, right after
  `set_page_config`.
- No change to `_render_run_region`, `_consume_run`, the streaming loop, session-state, or the
  topology re-key logic — the live-update mechanics are untouched.

### `src/expertview/cli.py` (edit — Plan-B parity, modest)
- `_status_cell`: prefix the status text with a state glyph (● done / ◐ active / ○ waiting /
  ⊘ skipped, ASCII fallback on non-UTF stdout via the existing `_bar_glyphs` pattern) so the table
  reads at a glance, keeping the existing per-row colors from `_row_style`.
- `_status_table`: keep the title text containing "{n} findings" (test depends on it); add a
  subtitle/caption row separating the parallel investigators from the routing/synthesis stages so
  the CLI mirrors the Streamlit grouping. The existing color-coding stays.
- All detail strings (finding claim, spawn reason) preserved verbatim — the asserted substrings
  ("3 findings", node labels, "bearing chatter detected", "spawned a supply-chain
  sub-investigation") are untouched.

### `.streamlit/config.toml`
- No change expected (theme already correct). If a single token needs nudging for contrast it will
  be one value with a comment; otherwise left as-is.

### Tests
- No test-contract changes required. `tests/unit/test_cli.py` asserts substrings that this plan
  preserves; `tests/unit/test_streaming.py` is untouched (streaming contract unchanged). I will run
  the full suite + lint + format and fix anything the glyph/caption change disturbs (none expected).

### `ProjectDocs/decisions.md` (edit)
- Append one entry: "Demo UI uses heavier injected CSS (custom cards/badges/hero) layered on the
  dark-graphite+amber theme" — rationale = interview/demo legibility & polish; tradeoff = mild
  Streamlit-upgrade fragility, accepted; reversibility = easy (CSS is isolated in `inject_css`,
  removing it falls back to native components).

---

## Risks

- **`:has()` / injected-CSS fragility across Streamlit upgrades** — the per-status card accent uses
  a marker-span + `:has()` selector on Streamlit's internal container wrapper testid. Mitigation:
  all such CSS is centralized in `inject_css`; if a future Streamlit bump changes the testid the
  cards degrade to plain bordered containers (still legible), not broken. This fragility was
  explicitly accepted in the Q&A.
- **Live-recolor regression** — restructuring `render_progress_panel` could disturb the per-event
  re-render. Mitigation: signature and inputs unchanged, `app.py` loop untouched; verified by
  running the live demo.
- **CLI glyphs on legacy Windows consoles** — non-UTF stdout can't encode ●/◐/○/⊘. Mitigation:
  reuse the existing `_bar_glyphs` encoding check for an ASCII fallback (`*`/`>`/`.`/`x`).
- **HTML-in-markdown escaping** — investigator claims/summaries injected into HTML must be escaped
  to avoid layout breakage from stray `<`/`&`. Mitigation: `html.escape` on all interpolated
  user/LLM text inside HTML blocks.

## Verification

- `uv run ruff format .` && `uv run ruff check .` clean.
- `uv run pytest` green (unit + integration).
- `uv run streamlit run src/expertview/ui/app.py` — run the process-recipe-drift incident; confirm:
  styled header; incident card distinct; five investigator cards recolor live with badges; topology
  has a clear title + colored legend; report leads with the verdict hero; evidence/sources stay
  tucked in expanders; no giant raw-doc headers.
- `uv run python -m expertview.cli demo --incident <path> --live` — confirm status glyphs + grouping
  mirror the app and colors are consistent.
- `/verify` re-run of the watched-demo gate.
