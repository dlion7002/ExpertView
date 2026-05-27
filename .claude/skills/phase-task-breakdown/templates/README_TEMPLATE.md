<!--
README skeleton for ProjectDocs/phases/phase-N/README.md.
Fill the {{PLACEHOLDERS}} and STRIP all <!-- ... --> comments from the rendered output.
Reference precedent: ProjectDocs/phases/phase-2/README.md and phase-3/README.md.
-->

# Phase {{N}} — {{PHASE_TITLE}} (Planning Index)

> **Source**: [build_plan.md §Phase {{N}}](../../build_plan.md). This folder breaks Phase {{N}} into agent-executable task files. Each task file tells the executing agent **what** to produce, not **how** to write it — the agent picks implementation details using its own judgment, the architecture rules in [architecture.md §5](../../architecture.md), and the standards in [CLAUDE.md](../../../CLAUDE.md).
>
> **Phase goal (verbatim from build_plan.md)**: {{PHASE_GOAL_VERBATIM}}
>
> **Phase quality gate (verbatim from build_plan.md)**: {{QUALITY_GATE_VERBATIM}}

---

## Pre-flight

{{PRE_FLIGHT_NARRATIVE}}
<!--
1-3 sentences. State what must be true before any task here starts:
- which prior-phase PRs must be merged
- which tag (e.g., v0.X.0-demo) must exist on main
- any external prerequisite (corpus authored, env var set)
If a final wiring task here depends on additional siblings landing first, name it.
-->

---

## Task list

| # | Task | Branch | Parallelism | Depends on |
|---|---|---|---|---|
{{TASK_LIST_TABLE_ROWS}}
<!--
One row per task. Example row:
| 1 | [Task title](task-1-slug.md) | `feature/slug` | Parallelizable with 2, 3 | Phase N-1 complete |
The Parallelism column uses one of:
- "Sequential (blocks K, L)"
- "Sequential (final merge point)"
- "Parallelizable with K, L, M"
-->

{{N_TASKS}} tasks, one PR each, per the lightweight GitHub Flow locked in [decisions.md (2026-05-25)](../../decisions.md) and detailed in [branching_strategy.md](../../branching_strategy.md). Branch names are suggestions; the executing agent may consolidate if a task is small and the dependency graph permits.

---

## Dependency graph

```text
{{ASCII_DEPENDENCY_GRAPH}}
```
<!--
ASCII boxes + arrows. See phase-2/README.md and phase-3/README.md for shape.
Last box should reference the phase quality gate and the next tag, e.g.:
  Phase {{N}} quality gate runs -> tag `v0.{{N+1}}.0-demo` per
  branching_strategy.md section 8.
-->

**Parallelism rationale.** {{PARALLELISM_RATIONALE}}
<!--
2-4 sentences. Reference architecture.md section 5's "module boundaries are walls" rule.
Name which paths each task touches and why they do not overlap.
-->

**Sequential pinch points.**

{{SEQUENTIAL_PINCH_POINTS}}
<!--
Bulleted list. Each bullet names a dependency that forces sequential order, e.g.:
- **Task 1 -> Task 2**: the loader is meaningless without corpus files to read.
-->

---

## How to use this folder

1. Pick the next unblocked task from the table above (an unblocked task is one whose `Depends on` column is fully merged into `main`).
2. Read its file end-to-end before starting. Each task file is self-contained — it states purpose, steps, code locations, connections, and risks.
3. Follow the planning loop in [workflow.md §1](../../workflow.md): clarifying Q&A → plan file → user approval → implement → summarize. The task file is the *scope*, not the plan; the executing agent still writes a plan and gets approval.
4. Open a PR per [branching_strategy.md §5](../../branching_strategy.md). The task file's branch suggestion is a starting point.
5. When all {{N_TASKS}} PRs are merged and the phase quality gate passes, tag `v0.{{NEXT_TAG_MINOR}}.0-demo` (per [branching_strategy.md §8](../../branching_strategy.md)) and proceed to Phase {{N_PLUS_ONE}}.

{{OPTIONAL_SHARED_SHAPE_SECTION}}
<!--
Include a "## Shared shape across the N bundles" section only when multiple tasks share a near-identical skeleton (phase-3's four per-domain bundles is the reference). Otherwise delete this placeholder line entirely.

The shared-shape section lists:
- what each bundle produces (paths + file roles)
- what changes per bundle (the differentiator field, the role-framing line)
- what does NOT change per bundle (the node signature, the factory shape)
See phase-3/README.md for the canonical example.
-->

---

## What this folder is *not* for

- Not a substitute for [build_plan.md](../../build_plan.md) — that document remains the canonical phase definition and quality-gate source.
- Not an architecture document — see [architecture.md](../../architecture.md) for module boundaries and protocol shapes.
- Not a decision log — locked choices live in [decisions.md](../../decisions.md).
- Not implementation guidance — task files name *what* to build and *why*, never prescribed implementations. The executing agent decides the *how*.
