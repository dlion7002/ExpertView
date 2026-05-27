# Phase 4 — Dynamic Sub-Investigation (Planning Index)

> **Source**: [build_plan.md §Phase 4](../../build_plan.md). This folder breaks Phase 4 into agent-executable task files. Each task file tells the executing agent **what** to produce, not **how** to write it — the agent picks implementation details using its own judgment, the architecture rules in [architecture.md §5](../../architecture.md), and the standards in [CLAUDE.md](../../../CLAUDE.md).
>
> **Phase goal (verbatim from build_plan.md)**: at least one spawning trigger fires reliably on the rehearsed scenario (e.g., mechanical investigator finds a bearing anomaly → conditional edge routes to a supplier-history sub-investigator node under `supply_chain`).
>
> **Phase quality gate (verbatim from build_plan.md)**: a single demo run produces a LangSmith trace containing both the 5 parallel investigator spans and the dynamically spawned sub-investigator span, with the sub-investigator's finding cited in the final CausalReport.

---

## Pre-flight

Phase 3 must be merged and tagged `v0.4.0-demo` before any task in this phase starts. That tag carries the dispatcher rewrite (`Send`-API fan-out), the five investigator nodes (mechanical + the four Phase-3 domains), the `asyncio.Semaphore(5)` throttle in `agents/llms.py`, and a working `python -m expertview.cli demo` that prints a multi-domain CausalReport. Phase 4 extends the wiring with a conditional edge after the fan-out merges; it does not alter any of the five investigator nodes or the synthesizer.

The v1 spawning scope is locked to **one trigger** — a mechanical bearing-anomaly `Finding` routes to a supplier-history sub-investigator that queries the existing `supply_chain` `KnowledgeStore`. Additional triggers are explicitly deferred (see [build_plan.md §Phase 5](../../build_plan.md)).

---

## Task list

| # | Task | Branch | Parallelism | Depends on |
|---|---|---|---|---|
| 1 | [Spawning predicates + parameterized sub-investigator bundle (supplier-history corpus extension + predicate + node + prompt)](task-1-spawning-predicates-and-sub-investigator.md) | `feature/spawning-and-sub-investigator` | Sequential (blocks Task 2) | Phase 3 complete (`v0.4.0-demo` tagged) |
| 2 | [Conditional-edge wiring + structlog timing + integration test + parallel `/verify`](task-2-conditional-edge-wiring-verify.md) | `feature/phase-4-wiring` | Sequential (final merge point) | Task 1 |

Two tasks, one PR each, per the lightweight GitHub Flow locked in [decisions.md (2026-05-25)](../../decisions.md) and detailed in [branching_strategy.md](../../branching_strategy.md). Branch names are suggestions; the executing agent may consolidate if a task is small and the dependency graph permits.

---

## Dependency graph

```text
                ┌──────────────────────────────────────────────┐
                │  Phase 3 merged + tagged v0.4.0-demo         │
                │  (Send-API fan-out + 5 investigator nodes +  │
                │   semaphore + working multi-domain demo)     │
                └──────────────────────┬───────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │ Task 1 — Spawning predicates +          │
                  │ parameterized sub-investigator bundle:  │
                  │   - agents/spawning.py (predicate)      │
                  │   - 2-3 supplier-history docs in        │
                  │     data/domains/supply_chain/          │
                  │   - agents/investigators/               │
                  │       sub_investigator.py (factory)     │
                  │   - prompts/investigator/               │
                  │       sub_investigator.md               │
                  │   - unit tests (predicate + node patch) │
                  └────────────────┬────────────────────────┘
                                   │  factory + predicate landed → wiring
                                   ▼
                  ┌─────────────────────────────────────────┐
                  │ Task 2 — Conditional-edge wiring        │
                  │ + structlog timing + integration test   │
                  │ + parallel /verify (DoD)                │
                  │   - _should_spawn(state) -> str         │
                  │   - sub_investigator node registered    │
                  │   - tests/integration/                  │
                  │       test_dynamic_spawning.py          │
                  │   - /verify against CNC incident        │
                  └────────────────┬────────────────────────┘
                                   │
                                   ▼
              Phase 4 quality gate runs → tag `v0.5.0-demo` per
              branching_strategy.md §8.
```

**Parallelism rationale.** Phase 4 has only two tasks because the spawning surface is small and the wiring is the integration point. Task 1 touches `src/expertview/agents/spawning.py` (new), `src/expertview/agents/investigators/sub_investigator.py` (new), `src/expertview/prompts/investigator/sub_investigator.md` (new), `data/domains/supply_chain/` (corpus addition), and two new unit-test files. Task 2 edits `src/expertview/orchestration/runner.py` and adds a new integration-test file. Task 2 imports the predicate from `agents/spawning.py` and the factory from `agents/investigators/sub_investigator.py` — both of which Task 1 produces — so Task 2 is sequential by necessity. There is no third task that could parallelize because the only standalone unit (the predicate module) is small enough that splitting it from its node bundle would create a PR that imports nothing and is consumed by nothing. The architecture rule from [architecture.md §5](../../architecture.md) — *"Module boundaries are walls"* — is what keeps Task 1's predicate module pure (no LangGraph imports, no orchestration knowledge) so Task 2's wiring can compose it without churn.

**Sequential pinch points.**

- **Task 1 → Task 2**: Task 2 imports `is_bearing_anomaly` from `agents/spawning.py` and `make_sub_investigator_node` from `agents/investigators/sub_investigator.py`. Both must exist on `main` before the wiring PR opens. Task 2's `/verify` quality gate cannot run without the prompt file and the supplier-history corpus additions from Task 1.

---

## How to use this folder

1. Pick the next unblocked task from the table above (an unblocked task is one whose `Depends on` column is fully merged into `main`). For Phase 4, only Task 1 is unblocked at the start.
2. Read its file end-to-end before starting. Each task file is self-contained — it states purpose, steps, code locations, connections, and risks.
3. Follow the planning loop in [workflow.md §1](../../workflow.md): clarifying Q&A → plan file → user approval → implement → summarize. The task file is the *scope*, not the plan; the executing agent still writes a plan and gets approval.
4. Open a PR per [branching_strategy.md §5](../../branching_strategy.md). The task file's branch suggestion is a starting point.
5. When both PRs are merged and the phase quality gate passes, tag `v0.5.0-demo` (per [branching_strategy.md §8](../../branching_strategy.md)) and proceed to Phase 5.

---

## Skill-candidacy flag (carried forward from Phase 3)

The investigator-shaped node pattern (read a `KnowledgeStore`, call the investigator LLM with a versioned prompt, return `{"findings": [...]}`) has now repeated across:

- Phase 2 — mechanical investigator (the reference implementation).
- Phase 3 — process, supply_chain, environmental, human_factors investigators (four parallel copies of the pattern).
- Phase 4 — the parameterized sub-investigator node (Task 1).

That is six repetitions, well past the ≥3 threshold for skill candidacy in [CLAUDE.md "Built-in skills" §Recommended additions](../../../CLAUDE.md). The `rca-investigator-prompt` skill named there is therefore a real candidate for a future session — it would template the prompt file, the node factory, and the unit test together. **This is a flag, not a task.** Per CLAUDE.md's "propose, do not apply" rule for additions outside the immediate work, the skill is not drafted as part of Phase 4. Surface it for user decision at phase close or in a follow-up planning session.

---

## What this folder is *not* for

- Not a substitute for [build_plan.md](../../build_plan.md) — that document remains the canonical phase definition and quality-gate source.
- Not an architecture document — see [architecture.md](../../architecture.md) for module boundaries and protocol shapes.
- Not a decision log — locked choices live in [decisions.md](../../decisions.md).
- Not implementation guidance — task files name *what* to build and *why*, never prescribed implementations. The executing agent decides the *how*.
