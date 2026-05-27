# Phase 5 — Evidence-Weighted Convergence (Planning Index)

> **Source**: [build_plan.md §Phase 5](../../build_plan.md). This folder breaks Phase 5 into agent-executable task files. Each task file tells the executing agent **what** to produce, not **how** to write it — the agent picks implementation details using its own judgment, the architecture rules in [architecture.md §5](../../architecture.md), and the standards in [CLAUDE.md](../../../CLAUDE.md).
>
> **Phase goal (verbatim from build_plan.md)**: the synthesizer applies confidence scoring + causal linking across findings; two distinct incidents produce two distinct causal reports with different top causes.
>
> **Phase quality gate (verbatim from build_plan.md)**: both incidents produce reports where the top hypothesis differs and the confidence summary is non-trivial.

---

## Pre-flight

Phase 4 must be merged and tagged `v0.5.0-demo` before any task in this phase starts. That tag carries the conditional-edge wiring (`spawning_join → _should_spawn → sub_investigator | synthesizer`), the bearing-anomaly predicate in `agents/spawning.py`, the parameterized sub-investigator node, and a working `python -m expertview.cli demo` that prints a multi-domain CausalReport with a sub-investigator citation. Phase 5 adds a deterministic re-scoring layer between the synthesizer's LLM call and its returned report, and a second rehearsed incident; it does not alter the graph topology, the five investigator nodes, the dispatcher, or the conditional edge.

Two structural choices are locked for this phase (2026-05-27 planning Q&A, to be logged in [decisions.md](../../decisions.md) when Task 3 lands):

- **Convergence applies post-LLM.** The synthesizer LLM drafts hypotheses and causal links; `evidence/convergence.py` then deterministically re-weights finding confidence by source, re-scores hypotheses, and orders the causal chain. The report's numbers become reproducible Python rather than LLM whim — this is what makes "evidence-weighted" a testable contract rather than a prompt instruction.
- **The second incident is process-led.** Its root cause lives in the `process` domain (in contrast to the mechanical / supply-chain-led CNC scenario), so the two incidents produce genuinely different top hypotheses rather than two re-skins of the same causal chain.

The reranker reintroduction that [architecture.md §7](../../architecture.md) flags as a Phase 5 decision point is **deferred**. It is reconsidered only if Task 3's `/verify` shows retrieval quality — not convergence — is the bottleneck; in that case it is a separate follow-up with its own [decisions.md](../../decisions.md) entry, not a Phase 5 task.

---

## Task list

| # | Task | Branch | Parallelism | Depends on |
|---|---|---|---|---|
| 1 | [Convergence functions + unit tests](task-1-convergence-functions.md) | `feature/convergence-functions` | Parallelizable with Task 2 | Phase 4 complete (`v0.5.0-demo` tagged) |
| 2 | [Second rehearsed incident (process-led) + corpus clues](task-2-second-incident.md) | `feature/second-incident` | Parallelizable with Task 1 | Phase 4 complete (`v0.5.0-demo` tagged) |
| 3 | [Wire convergence into the synthesizer + two-incident integration test + parallel `/verify`](task-3-wiring-and-verify.md) | `feature/phase-5-convergence-wiring` | Sequential (final merge point) | Task 1 and Task 2 |

Three tasks, one PR each, per the lightweight GitHub Flow locked in [decisions.md (2026-05-25)](../../decisions.md) and detailed in [branching_strategy.md](../../branching_strategy.md). Branch names are suggestions; the executing agent may consolidate if a task is small and the dependency graph permits.

---

## Dependency graph

```text
                ┌──────────────────────────────────────────────┐
                │  Phase 4 merged + tagged v0.5.0-demo         │
                │  (conditional-edge spawning + working        │
                │   multi-domain demo with sub-investigator    │
                │   citation)                                  │
                └───────────────┬──────────────────┬───────────┘
                                │                  │
                                ▼                  ▼
          ┌───────────────────────────┐  ┌──────────────────────────────┐
          │ Task 1 — Convergence      │  │ Task 2 — Second incident      │
          │ functions:                │  │ (process-led):                │
          │   - evidence/             │  │   - data/incidents/<slug>.yaml│
          │       convergence.py      │  │   - planted clue docs in      │
          │     (weight findings,     │  │       data/domains/process/   │
          │      link causes,         │  │       (+ light cross-domain)  │
          │      score hypotheses)    │  │   - curator-attention notes   │
          │   - tests/unit/           │  │                               │
          │       test_convergence.py │  │                               │
          └─────────────┬─────────────┘  └────────────────┬─────────────┘
                        │                                  │
                        │  pure functions landed           │  second incident + clues landed
                        └─────────────────┬────────────────┘
                                          ▼
                  ┌─────────────────────────────────────────┐
                  │ Task 3 — Wire convergence into the      │
                  │ synthesizer + two-incident integration  │
                  │ test + parallel /verify (DoD):          │
                  │   - agents/synthesizer.py re-scores via │
                  │     evidence/convergence.py (post-LLM)  │
                  │   - prompts/synthesizer/default.md      │
                  │     iteration (LLM proposes, convergence│
                  │     owns final scoring) if needed       │
                  │   - tests/integration/                  │
                  │       test_convergence.py               │
                  │   - /verify both incidents              │
                  └────────────────┬────────────────────────┘
                                   │
                                   ▼
              Phase 5 quality gate runs → tag `v0.6.0-demo` per
              branching_strategy.md §8.
```

**Parallelism rationale.** Tasks 1 and 2 share no editing surface and can run concurrently. Task 1 touches only `src/expertview/evidence/convergence.py` (new) and `tests/unit/test_convergence.py` (new); per [architecture.md §5](../../architecture.md)'s *"module boundaries are walls"* rule, `evidence/` imports neither `agents/` nor `orchestration/`, so the convergence functions are pure transforms over the `evidence/models.py` types and can be written and unit-tested with no knowledge of the graph. Task 2 touches only `data/incidents/` and `data/domains/process/` (plus optional light additions in other `data/domains/*` folders) — pure data authoring, no Python. Task 3 is the sole task that edits `src/expertview/agents/synthesizer.py` and adds the integration test, and it imports both Task 1's functions and Task 2's incident — so it is sequential by necessity.

**Sequential pinch points.**

- **Task 1 → Task 3**: Task 3 imports the re-scoring functions from `evidence/convergence.py`. They must be on `main` before the wiring PR opens.
- **Task 2 → Task 3**: Task 3's two-incident `/verify` and the integration test's distinctness assertion both require the second incident YAML and its planted corpus clues to exist on `main`. Without them, there is no second report to compare against the CNC report.
- **Task 1 ∥ Task 2**: explicitly *not* a pinch point — they are independent and the executing agent may take them in either order or in parallel.

---

## How to use this folder

1. Pick the next unblocked task from the table above (an unblocked task is one whose `Depends on` column is fully merged into `main`). For Phase 5, Tasks 1 and 2 are both unblocked at the start; Task 3 unblocks once both are merged.
2. Read its file end-to-end before starting. Each task file is self-contained — it states purpose, steps, code locations, connections, and risks.
3. Follow the planning loop in [workflow.md §1](../../workflow.md): clarifying Q&A → plan file → user approval → implement → summarize. The task file is the *scope*, not the plan; the executing agent still writes a plan and gets approval.
4. Open a PR per [branching_strategy.md §5](../../branching_strategy.md). The task file's branch suggestion is a starting point.
5. When all three PRs are merged and the phase quality gate passes, tag `v0.6.0-demo` (per [branching_strategy.md §8](../../branching_strategy.md)) and proceed to Phase 6.

---

## Skill-candidacy flag (carried forward from Phase 4)

Phase 5 adds no new repetition of the investigator-shaped node pattern — it ships a convergence layer and a second incident, neither of which is a new investigator. The `rca-investigator-prompt`, `domain-rag-seed`, and `agent-trace-replay` candidates tracked in [open_questions.md §Skill candidates](../../open_questions.md) and flagged at Phase 4 close remain open and deferred. No skill is drafted as part of Phase 5; per CLAUDE.md's "propose, do not apply" rule, surface them for a user decision at phase close or in a follow-up planning session.

One new pattern *begins* in this phase: pure evidence-math functions in `evidence/convergence.py` with mirrored unit tests. This is its first occurrence — not yet a skill candidate. Note it for the ≥3 threshold if later phases add more pure-math evidence modules.

---

## What this folder is *not* for

- Not a substitute for [build_plan.md](../../build_plan.md) — that document remains the canonical phase definition and quality-gate source.
- Not an architecture document — see [architecture.md](../../architecture.md) for module boundaries and protocol shapes.
- Not a decision log — locked choices live in [decisions.md](../../decisions.md).
- Not implementation guidance — task files name *what* to build and *why*, never prescribed implementations. The executing agent decides the *how*.
