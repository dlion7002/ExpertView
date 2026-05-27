# Phase 6 Task 2 - Streamlit Demo App Plan

## Goal

Build the Streamlit single-screen demo surface on `feature/streamlit-demo-app`,
push the branch to `origin`, and provide a GitHub compare URL for PR creation
because `gh` is unavailable in this environment.

## Approved choices

- Add runtime dependencies: `streamlit>=1.41` and `streamlit-mermaid>=0.3.0`.
- Verify with a full live run: tests, lint, format check, Streamlit launch, and
  an end-to-end CNC incident run through the app.
- Use the GitHub compare URL for PR creation after pushing the branch.

## Affected files

- `ProjectDocs/decisions.md` - log the Streamlit and Mermaid dependency choice.
- `pyproject.toml` and `uv.lock` - add the two runtime dependencies via `uv add`.
- `src/expertview/ui/__init__.py` - create the UI package.
- `src/expertview/ui/app.py` - single-screen Streamlit app.
- `src/expertview/ui/render.py` - private rendering helpers for reports,
  citations, and live progress.

## Implementation sketch

- Region 1 lists `data/incidents/*.yaml`, parses the selection into `Incident`,
  and shows summary, symptoms, and affected assets.
- Region 2 compiles `make_graph()`, renders `render_topology_mermaid(...)`
  through `streamlit_mermaid.st_mermaid(...)`, and drives live progress from
  `stream_run(...)`.
- The async bridge starts with a button-triggered `asyncio.run(...)` consumer
  that writes each `ProgressEvent` into `st.empty()` placeholders. If verification
  shows batched updates, switch to a queue plus `st.fragment(run_every=...)`.
- Region 3 renders the final `CausalReport` without recomputing convergence:
  confidence bars, confidence summary, causal chain, and citations. Citation IDs
  are resolved to local `data/domains/*/*.md` paths and small snippets when
  possible.
- Keep `ui/` as a top-level surface layer. It imports only from
  `orchestration` and `evidence.models`; it does not import `agents`, `rag`, or
  `cli.py`.

## Verification

- `uv run pytest`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run streamlit run src/expertview/ui/app.py`
- In the app, run `cnc_out_of_tolerance.yaml` end-to-end and confirm the incident
  region, Mermaid topology, live status panel, spawned sub-investigator, and final
  report all render.

## Risks

- Streamlit may batch script output until the run completes. Verify mid-run
  updates during a real CNC run and switch bridge strategy if necessary.
- `streamlit-mermaid` is a third-party component, so pin to `>=0.3.0` and keep
  the decision logged.
- Full live verification uses current API/network access and can fail for
  provider or network reasons unrelated to UI code; record failures clearly if
  they occur.
