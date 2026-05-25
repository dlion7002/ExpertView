# Phase 1 — Skeleton + Contracts (Planning Index)

> **Source**: [build_plan.md §Phase 1](../../build_plan.md). This folder breaks Phase 1 into agent-executable task files. Each task file tells the executing agent **what** to produce, not **how** to write it — the agent picks implementation details using its own judgment, the architecture rules in [architecture.md §5](../../architecture.md), and the standards in [CLAUDE.md](../../../CLAUDE.md).
>
> **Phase goal (verbatim from build_plan.md)**: project layout, pydantic schemas, `KnowledgeStore` stub wrapping LangChain `InMemoryVectorStore`, LangGraph `StateGraph` skeleton with `ExpertViewState` TypedDict, provider-key round-trip tests. No real investigator runs yet.
>
> **Phase quality gate (verbatim from build_plan.md)**: `uv run pytest` green on schema round-trips and provider round-trips. `uv run ruff check .` and `uv run ruff format --check .` clean. `python -c "from expertview.orchestration.runner import make_graph; make_graph()"` compiles a `StateGraph` without error.

---

## Task list

| # | Task | Branch | Parallelism | Depends on |
|---|---|---|---|---|
| 1 | [Project bootstrap](task-1-project-bootstrap.md) | `chore/project-bootstrap` | Sequential (blocks all) | — |
| 2 | [Evidence models + shared state](task-2-evidence-models-and-state.md) | `feature/evidence-state-schemas` | Sequential | Task 1 |
| 3 | [RAG skeleton](task-3-rag-skeleton.md) | `feature/rag-skeleton` | Parallelizable | Task 2 |
| 4 | [Agents skeleton + LLM factory](task-4-agents-skeleton-and-llms.md) | `feature/agents-llms` | Parallelizable | Task 2 |
| 5 | [Orchestration runner skeleton](task-5-orchestration-runner-skeleton.md) | `feature/orchestration-skeleton` | Parallelizable | Task 2 |

Five tasks, one PR each, per the lightweight GitHub Flow locked in [decisions.md (2026-05-25)](../../decisions.md) and detailed in [branching_strategy.md](../../branching_strategy.md). Branch names are suggestions; the executing agent may consolidate if a task is small and the dependency graph permits.

---

## Dependency graph

```text
                 ┌───────────────────────────┐
                 │  Task 1 — Bootstrap       │
                 │  (pyproject + skeleton)   │
                 └─────────────┬─────────────┘
                               │  unblocks everything
                               ▼
                 ┌───────────────────────────┐
                 │  Task 2 — Evidence models │
                 │  + ExpertViewState        │
                 │  (the shared contract)    │
                 └─────────────┬─────────────┘
                               │  once schemas land, the three skeleton tasks fan out
            ┌──────────────────┼───────────────────┐
            ▼                  ▼                   ▼
  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
  │ Task 3 — RAG     │ │ Task 4 — Agents  │ │ Task 5 — Orchestration│
  │ skeleton         │ │ skeleton + LLMs  │ │ runner skeleton       │
  │ (KnowledgeStore) │ │ (protocols +     │ │ (make_graph compiles) │
  │                  │ │ provider factory)│ │                       │
  └──────────────────┘ └──────────────────┘ └──────────────────────┘
            │                  │                   │
            └──────────────────┴───────────────────┘
                               │
                               ▼
            All three merged → Phase 1 quality gate runs → tag `v0.2.0-demo` per
            branching_strategy.md §8.
```

**Parallelism rationale.** Tasks 3, 4, and 5 each import only from `evidence/` and stdlib. They do not import from each other. Once Task 2's models and `ExpertViewState` are merged into `main`, three agents can take them in parallel on separate `feature/*` branches without merge conflicts. The architecture rule in [architecture.md §5](../../architecture.md) — *"Module boundaries are walls"* — is exactly what makes the fan-out safe.

**Sequential pinch points.**

- **Task 1 → Task 2**: nothing else can be imported until the package skeleton exists.
- **Task 2 → Tasks 3/4/5**: the shared pydantic models and `ExpertViewState` are referenced by every downstream module's public surface. Landing them first prevents three branches from independently inventing slightly different `Finding` shapes.

---

## How to use this folder

1. Pick the next unblocked task from the table above (an unblocked task is one whose `Depends on` column is fully merged into `main`).
2. Read its file end-to-end before starting. Each task file is self-contained — it states purpose, steps, code locations, connections, and risks.
3. Follow the planning loop in [workflow.md §1](../../workflow.md): clarifying Q&A → plan file → user approval → implement → summarize. The task file is the *scope*, not the plan; the executing agent still writes a plan and gets approval.
4. Open a PR per [branching_strategy.md §5](../../branching_strategy.md). The task file's branch suggestion is a starting point.
5. When all five PRs are merged and the phase quality gate passes, tag `v0.2.0-demo` (per [branching_strategy.md §8](../../branching_strategy.md)) and proceed to Phase 2.

---

## What this folder is *not* for

- Not a substitute for [build_plan.md](../../build_plan.md) — that document remains the canonical phase definition and quality-gate source.
- Not an architecture document — see [architecture.md](../../architecture.md) for module boundaries and protocol shapes.
- Not a decision log — locked choices live in [decisions.md](../../decisions.md).
- Not implementation guidance — task files name *what* to build and *why*, never prescribed implementations. The executing agent decides the *how*.
