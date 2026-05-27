# Phase 6 Task 1 — Run-Progress Streaming Core Plan

## Affected files

- `src/expertview/orchestration/streaming.py` (new)
- `tests/unit/test_streaming.py` (new)
- `ProjectDocs/decisions.md` (append locked Phase 6 streaming decision)
- `ProjectDocs/phases/phase-6/` (include existing phase task docs in the PR)

## New files

- `ProjectDocs/plans/phase-6-task-1-run-progress-streaming-core-plan.md`
- `src/expertview/orchestration/streaming.py`
- `tests/unit/test_streaming.py`

## Change sketch

Add a surface-agnostic streaming adapter in `orchestration/streaming.py` that wraps
`compiled_graph.astream(..., stream_mode="updates")` and converts LangGraph update chunks
into frozen Pydantic `ProgressEvent` objects. The event model stays local to orchestration
because it describes run progress for demo surfaces, not cross-agent evidence on the shared
state. The module also exposes a single node-name to demo-label mapping keyed from
`orchestration.runner` constants, plus an ordered investigator-node tuple for the Streamlit
and CLI surfaces to reuse.

Add a Mermaid helper that calls `compiled_graph.get_graph().draw_mermaid()`, validates that
all non-start/end graph nodes have labels, and replaces displayed raw node labels with
human-readable demo labels while preserving Mermaid-safe node IDs. Unit tests use a fake
compiled graph, so no OpenRouter, embeddings, LangSmith, or real graph run is required.

Append a decision entry recording the locked in-process `graph.astream(...)` live-feed choice
and the streaming-local progress event model.

## Risks

- LangGraph update chunks must be treated as `{node_name: state_patch}` dicts; tests pin this
  contract and verification will run against the installed dependency version.
- Mermaid output shape comes from LangChain's renderer. The helper only rewrites node labels
  in known node declaration forms and validates unmapped nodes before rewriting.
- The terminal `CausalReport` is expected in the synthesizer update patch. The stream event
  surfaces it on that event; downstream surfaces do not need a second graph pass.
