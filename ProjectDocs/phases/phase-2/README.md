# Phase 2 — Vertical Slice (Planning Index)

> **Source**: [build_plan.md §Phase 2](../../build_plan.md). This folder breaks Phase 2 into agent-executable task files. Each task file tells the executing agent **what** to produce, not **how** to write it — the agent picks implementation details using its own judgment, the architecture rules in [architecture.md §5](../../architecture.md), and the standards in [CLAUDE.md](../../../CLAUDE.md).
>
> **Phase goal (verbatim from build_plan.md)**: ONE investigator (LangGraph node) + ONE domain corpus (5–10 mock docs, embedded via the local `BAAI/bge-small-en-v1.5`, cached to disk) + a synthesizer node producing a single hypothesis from a single finding. End-to-end CLI call drives the compiled graph from `Incident` → `CausalReport`. LangSmith trace visible in the dashboard.
>
> **Phase quality gate (verbatim from build_plan.md)**: the CLI command runs against the rehearsed incident, prints a coherent causal report with at least one citation back to the corpus, and a LangSmith trace appears in the project dashboard showing every node + LLM call. `/verify` confirms by actually running it.

---

## Pre-flight

Phase 1's Task 5 PR (`feature/orchestration-skeleton`) must be merged to `main` before **Task 5** of this phase starts — Task 5 here *replaces* the Phase 1 placeholder node with the real `dispatcher → mechanical → synthesizer` graph. Tasks 1–4 can begin as soon as `main` carries the Phase 1 `v0.2.0-demo` tag.

---

## Task list

| # | Task | Branch | Parallelism | Depends on |
|---|---|---|---|---|
| 1 | [Data authoring (mechanical corpus + CNC incident)](task-1-data-authoring.md) | `data/mechanical-corpus-and-incident` | Sequential (blocks 2 and 5) | Phase 1 complete |
| 2 | [Mechanical RAG loader](task-2-mechanical-rag-loader.md) | `feature/mechanical-rag-loader` | Parallelizable with 3 and 4 | Task 1 |
| 3 | [Mechanical investigator node + prompt](task-3-mechanical-investigator.md) | `feature/mechanical-investigator` | Parallelizable with 2 and 4 | Phase 1 (uses `agents/llms` + `rag/base`) |
| 4 | [Synthesizer node + prompt](task-4-synthesizer.md) | `feature/synthesizer-node` | Parallelizable with 2 and 3 | Phase 1 (uses `agents/llms` + `evidence/models`) |
| 5 | [Runner wiring + CLI + end-to-end /verify](task-5-runner-cli-wiring.md) | `feature/phase-2-wiring` | Sequential (final merge point) | Tasks 1, 2, 3, 4 |

Five tasks, one PR each, per the lightweight GitHub Flow locked in [decisions.md (2026-05-25)](../../decisions.md) and detailed in [branching_strategy.md](../../branching_strategy.md). Branch names are suggestions; the executing agent may consolidate if a task is small and the dependency graph permits.

---

## Dependency graph

```text
                ┌──────────────────────────────┐
                │  Task 1 — Data authoring     │
                │  (mechanical corpus +        │
                │  CNC incident YAML)          │
                └──────────────┬───────────────┘
                               │  unblocks the loader; the corpus content
                               │  is what makes Task 5's /verify pass
                               ▼
        ┌──────────────────────┼──────────────────────────────┐
        ▼                      ▼                              ▼
┌──────────────────┐ ┌──────────────────────┐ ┌───────────────────────┐
│ Task 2 — Mech.   │ │ Task 3 — Mechanical  │ │ Task 4 — Synthesizer  │
│ RAG loader       │ │ investigator + prompt│ │ node + prompt         │
│ (corpus → store) │ │ (KnowledgeStore →    │ │ (findings →           │
│                  │ │  Finding)            │ │  CausalReport)        │
└────────┬─────────┘ └──────────┬───────────┘ └──────────┬────────────┘
         │                      │                        │
         └──────────────────────┴────────────────────────┘
                                │  all three landed → final merge
                                ▼
                  ┌─────────────────────────────────┐
                  │ Task 5 — Runner wiring + CLI    │
                  │ (dispatcher → mech → synth) +   │
                  │ /verify end-to-end run is DoD   │
                  └────────────┬────────────────────┘
                               │
                               ▼
              Phase 2 quality gate runs → tag `v0.3.0-demo` per
              branching_strategy.md §8.
```

**Parallelism rationale.** Tasks 2, 3, and 4 import only from the Phase 1 contracts (`evidence/models`, `rag/base`, `agents/base`, `agents/llms`) and from stdlib / third-party libraries. They do not import from each other. The investigator (Task 3) takes a `KnowledgeStore` *as an argument* — Task 5 constructs and binds Task 2's store at graph-build time — so Task 3 develops and tests against a fake store without waiting for Task 2's loader. The synthesizer (Task 4) reads from state and can be developed against fixture findings without waiting for Task 3. The architecture rule in [architecture.md §5](../../architecture.md) — *"Module boundaries are walls"* — is what keeps this three-way fan-out safe even with Phase 2's heavier cross-coupling.

**Sequential pinch points.**

- **Task 1 → Task 2**: the loader is meaningless without corpus files to read. Task 2's tests reference the actual `.md` files landed in Task 1.
- **Tasks 2/3/4 → Task 5**: the wiring task replaces Phase 1's placeholder node with the real graph and runs the end-to-end `/verify`. All three upstream tasks must be merged before the final wiring lands.

---

## How to use this folder

1. Pick the next unblocked task from the table above (an unblocked task is one whose `Depends on` column is fully merged into `main`).
2. Read its file end-to-end before starting. Each task file is self-contained — it states purpose, steps, code locations, connections, and risks.
3. Follow the planning loop in [workflow.md §1](../../workflow.md): clarifying Q&A → plan file → user approval → implement → summarize. The task file is the *scope*, not the plan; the executing agent still writes a plan and gets approval.
4. Open a PR per [branching_strategy.md §5](../../branching_strategy.md). The task file's branch suggestion is a starting point.
5. When all five PRs are merged and the phase quality gate passes, tag `v0.3.0-demo` (per [branching_strategy.md §8](../../branching_strategy.md)) and proceed to Phase 3.

---

## What this folder is *not* for

- Not a substitute for [build_plan.md](../../build_plan.md) — that document remains the canonical phase definition and quality-gate source.
- Not an architecture document — see [architecture.md](../../architecture.md) for module boundaries and protocol shapes.
- Not a decision log — locked choices live in [decisions.md](../../decisions.md).
- Not implementation guidance — task files name *what* to build and *why*, never prescribed implementations. The executing agent decides the *how*.
