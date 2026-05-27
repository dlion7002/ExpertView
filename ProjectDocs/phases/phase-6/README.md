# Phase 6 — Demo Surface (Planning Index)

> **Source**: [build_plan.md §Phase 6](../../build_plan.md). This folder breaks Phase 6 into agent-executable task files. Each task file tells the executing agent **what** to produce, not **how** to write it — the agent picks implementation details using its own judgment, the architecture rules in [architecture.md §5](../../architecture.md), and the standards in [CLAUDE.md](../../../CLAUDE.md).
>
> **Phase goal (verbatim from build_plan.md)**: a UI showing parallel execution live + the final causal report + the LangGraph topology diagram. A non-technical viewer can follow it.
>
> **Phase quality gate (verbatim from build_plan.md)**: a third party can watch the demo and describe what is happening without prompting; the Mermaid topology diagram is visible and labels match the actual code.

---

## Pre-flight

Phase 5 must be merged and tagged `v0.6.0-demo` before any task in this phase starts. That tag carries the post-LLM convergence re-scoring in `agents/synthesizer.py`, the blended `score_hypothesis` / `link_causes` functions in `evidence/convergence.py`, the second (process-led) rehearsed incident in `data/incidents/`, and a working `python -m expertview.cli demo --incident <path>` that prints a re-scored, evidence-weighted `CausalReport` for either incident. Phase 6 adds a demo *surface* on top of that working pipeline — a Streamlit app, a live-progress streaming layer, and a live CLI mode. It does **not** alter the graph topology, the five investigators, the dispatcher, the conditional edge, the synthesizer, or the convergence math; every node and model identifier is consumed as-is.

One choice is locked for this phase (2026-05-27 planning Q&A, to be logged in [decisions.md](../../decisions.md) when Task 1 lands):

- **Live progress streams in-process from `graph.astream(...)`, fed through a surface-agnostic adapter in `orchestration/streaming.py`.** The current entry point uses blocking `graph.ainvoke(...)`; the adapter wraps the compiled graph's async stream and yields typed progress events that both the Streamlit app (Task 2) and the live CLI mode (Task 3) render. No LangSmith polling, no second network dependency for the progress feed — the venue-network risk then touches only the LLM calls, not the live view. The Streamlit UI framework and the Mermaid-via-`st.mermaid` topology rendering were already locked 2026-05-25 in [decisions.md](../../decisions.md).

Two prerequisites are gated on a decision the executing agent must obtain before code lands:

- **`streamlit` is not yet a dependency.** It is absent from the Phase 1 `pyproject.toml` set. Adding it requires explicit user approval **and** a [decisions.md](../../decisions.md) entry per [CLAUDE.md](../../../CLAUDE.md)'s hard rule on dependency changes. Task 2 cannot silently add it.
- **`ui/` is a new top-of-stack package.** [architecture.md §5](../../architecture.md)'s "module boundaries are walls" list does not yet name `ui/`. This phase establishes the convention that `ui/` is an entry-point layer alongside `cli.py` — it may import `orchestration/` (runner + streaming + state) and `evidence/models`, and nothing from `agents/` or `rag/` internals. Whether to record that wall in [architecture.md §5](../../architecture.md) is surfaced for the user at phase close.

---

## Task list

| # | Task | Branch | Parallelism | Depends on |
|---|---|---|---|---|
| 1 | [Run-progress streaming core + topology helper + unit tests](task-1-run-progress-streaming-core.md) | `feature/run-progress-streaming-core` | Sequential (blocks Tasks 2 and 3) | Phase 5 complete (`v0.6.0-demo` tagged) |
| 2 | [Streamlit single-screen demo app](task-2-streamlit-demo-app.md) | `feature/streamlit-demo-app` | Parallelizable with Task 3's CLI build | Task 1 |
| 3 | [Live CLI mode + cross-surface `/verify`](task-3-cli-live-mode-and-verify.md) | `feature/phase-6-cli-live-and-verify` | Sequential (final merge point) | Task 1 and Task 2 |

Three tasks, one PR each, per the lightweight GitHub Flow locked in [decisions.md (2026-05-25)](../../decisions.md) and detailed in [branching_strategy.md](../../branching_strategy.md). Branch names are suggestions; the executing agent may consolidate if a task is small and the dependency graph permits.

---

## Dependency graph

```text
                ┌──────────────────────────────────────────────┐
                │  Phase 5 merged + tagged v0.6.0-demo         │
                │  (post-LLM convergence re-scoring + second   │
                │   process-led incident; working demo CLI     │
                │   prints an evidence-weighted CausalReport)  │
                └───────────────────────┬──────────────────────┘
                                        │
                                        ▼
                  ┌───────────────────────────────────────────┐
                  │ Task 1 — Run-progress streaming core      │
                  │   - orchestration/streaming.py            │
                  │     (typed progress events, astream       │
                  │      driver, draw_mermaid topology helper)│
                  │   - tests/unit/test_streaming.py          │
                  └───────────────┬───────────────────────────┘
                                  │  surface-agnostic progress feed landed
                  ┌───────────────┴──────────────────┐
                  ▼                                   ▼
    ┌───────────────────────────┐     ┌───────────────────────────────┐
    │ Task 2 — Streamlit app    │     │ Task 3 (CLI build) — live      │
    │   - src/expertview/ui/    │     │ rich-tables mode in cli.py     │
    │     (input, live status   │     │ consuming the streaming core   │
    │      + Mermaid topology,  │     │   - cli.py (edit)              │
    │      final report render) │     │                                │
    └─────────────┬─────────────┘     └───────────────┬───────────────┘
                  │   app on main                      │
                  └───────────────┬────────────────────┘
                                  ▼
                  ┌───────────────────────────────────────────┐
                  │ Task 3 (verify) — cross-surface /verify    │
                  │ is the phase quality gate:                 │
                  │   - Streamlit demo watched by a third      │
                  │     party; Mermaid labels match the code   │
                  │   - live CLI run as Plan B                 │
                  └───────────────┬────────────────────────────┘
                                  │
                                  ▼
              Phase 6 quality gate runs → tag `v0.7.0-demo` per
              branching_strategy.md §8.
```

**Parallelism rationale.** Task 1 touches only `src/expertview/orchestration/streaming.py` (new) and `tests/unit/test_streaming.py` (new); per [architecture.md §5](../../architecture.md)'s *"module boundaries are walls"* rule it stays inside `orchestration/` and imports only the compiled-graph type, `orchestration/state.py`, and `evidence/models.py` — so it is written and unit-tested with no UI and no CLI in play. Once Task 1 is on `main`, Task 2 (which touches only the new `src/expertview/ui/` package) and the CLI-build portion of Task 3 (which touches only `cli.py`) edit disjoint files and can proceed concurrently. They converge at Task 3's `/verify`: the phase quality gate is watched on the Streamlit demo, so Task 3 cannot *close* until Task 2's app is merged — which is why Task 3 is the final merge point even though its CLI code does not import from `ui/`.

**Sequential pinch points.**

- **Task 1 → Task 2**: the Streamlit live-status panel and topology tab are rendered from the progress events and the Mermaid string the streaming core produces. Without the core there is nothing for the app to consume.
- **Task 1 → Task 3**: the live CLI mode renders the same progress events through `rich.live`. It imports the streaming core directly.
- **Task 2 → Task 3 (verify only)**: the phase quality gate ("a third party can watch the demo … the Mermaid topology diagram is visible and labels match the actual code") is satisfied against the Streamlit app, so the cross-surface `/verify` that closes Task 3 requires Task 2 merged. The CLI code in Task 3 does **not** depend on Task 2 — only the gate does.

---

## How to use this folder

1. Pick the next unblocked task from the table above (an unblocked task is one whose `Depends on` column is fully merged into `main`). For Phase 6, Task 1 is the only unblocked task at the start; Tasks 2 and 3's CLI build unblock once Task 1 merges; Task 3's `/verify` closes only after Task 2 merges.
2. Read its file end-to-end before starting. Each task file is self-contained — it states purpose, steps, code locations, connections, and risks.
3. Follow the planning loop in [workflow.md §1](../../workflow.md): clarifying Q&A → plan file → user approval → implement → summarize. The task file is the *scope*, not the plan; the executing agent still writes a plan and gets approval.
4. Open a PR per [branching_strategy.md §5](../../branching_strategy.md). The task file's branch suggestion is a starting point.
5. When all three PRs are merged and the phase quality gate passes, tag `v0.7.0-demo` (per [branching_strategy.md §8](../../branching_strategy.md)) and proceed to Phase 7.

---

## Skill-candidacy flag (carried forward from Phase 4 and Phase 5)

Phase 6 adds no new investigator-shaped node, so the `rca-investigator-prompt`, `domain-rag-seed`, and `agent-trace-replay` candidates tracked in [open_questions.md §Skill candidates](../../open_questions.md) remain open and deferred — no skill is drafted here. Per CLAUDE.md's "propose, do not apply" rule, surface them for a user decision at phase close or in a follow-up session.

One pattern reaches its **second** occurrence in this phase: report rendering (confidence bars + citations) exists in `cli.py` from Phase 2 and is added to `ui/` in Task 2. That is below CLAUDE.md's ≥3 threshold for a skill *and* for an extracted shared render module — note it, do not extract it. If a third rendering surface appears (e.g., an HTML export in Phase 7), the duplication crosses the threshold and a shared render helper becomes the right move at that point.

---

## What this folder is *not* for

- Not a substitute for [build_plan.md](../../build_plan.md) — that document remains the canonical phase definition and quality-gate source.
- Not an architecture document — see [architecture.md](../../architecture.md) for module boundaries and protocol shapes.
- Not a decision log — locked choices live in [decisions.md](../../decisions.md).
- Not implementation guidance — task files name *what* to build and *why*, never prescribed implementations. The executing agent decides the *how*.
