# Phase 3 — Parallel Fan-Out (Planning Index)

> **Source**: [build_plan.md §Phase 3](../../build_plan.md). This folder breaks Phase 3 into agent-executable task files. Each task file tells the executing agent **what** to produce, not **how** to write it — the agent picks implementation details using its own judgment, the architecture rules in [architecture.md §5](../../architecture.md), and the standards in [CLAUDE.md](../../../CLAUDE.md).
>
> **Phase goal (verbatim from build_plan.md)**: all 5 domain investigators run *concurrently* against 5 mock corpora, dispatched from a `dispatcher` LangGraph node via the `Send` API. Findings merge into shared state via the reducer on `ExpertViewState.findings`.
>
> **Phase quality gate (verbatim from build_plan.md)**: timing of `python -m expertview.cli demo` proves true parallelism — total wall time ≈ slowest investigator, not the sum of all five. LangSmith trace shows the 5 investigator spans overlapping in time. structlog log shows interleaved start times.

---

## Pre-flight

Phase 2 must be merged and tagged `v0.3.0-demo` before any task in this phase starts. That tag carries:

- The mechanical corpus and CNC incident YAML (Phase 2 Task 1).
- `rag/domains/mechanical.py` (Phase 2 Task 2).
- `agents/investigators/mechanical.py` + `prompts/investigator/mechanical.md` (Phase 2 Task 3).
- `agents/synthesizer.py` + `prompts/synthesizer/default.md` (Phase 2 Task 4).
- The real `dispatcher → mechanical → synthesizer` graph and the working `python -m expertview.cli demo` (Phase 2 Task 5).

Tasks 1–4 in this phase mirror the mechanical bundle's shape; Task 5 rewrites the dispatcher body so the single-investigator chain becomes a 5-way fan-out.

---

## Task list

| # | Task | Branch | Parallelism | Depends on |
|---|---|---|---|---|
| 1 | [Process domain bundle (corpus + loader + investigator + prompt)](task-1-process-domain.md) | `feature/process-domain` | Parallelizable with 2, 3, 4 | Phase 2 complete |
| 2 | [Supply chain domain bundle (corpus + loader + investigator + prompt)](task-2-supply-chain-domain.md) | `feature/supply-chain-domain` | Parallelizable with 1, 3, 4 | Phase 2 complete |
| 3 | [Environmental domain bundle (corpus + loader + investigator + prompt)](task-3-environmental-domain.md) | `feature/environmental-domain` | Parallelizable with 1, 2, 4 | Phase 2 complete |
| 4 | [Human factors domain bundle (corpus + loader + investigator + prompt)](task-4-human-factors-domain.md) | `feature/human-factors-domain` | Parallelizable with 1, 2, 3 | Phase 2 complete |
| 5 | [Dispatcher rewrite (`Send` API) + wiring + structlog timing + throttle + parallel `/verify`](task-5-dispatcher-wiring-verify.md) | `feature/phase-3-wiring` | Sequential (final merge point) | Tasks 1, 2, 3, 4 |

Five tasks, one PR each, per the lightweight GitHub Flow locked in [decisions.md (2026-05-25)](../../decisions.md) and detailed in [branching_strategy.md](../../branching_strategy.md). Branch names are suggestions; the executing agent may consolidate if a task is small and the dependency graph permits.

---

## Dependency graph

```text
                ┌──────────────────────────────────────────────┐
                │  Phase 2 merged + tagged v0.3.0-demo         │
                │  (mechanical bundle + working demo CLI)      │
                └──────────────────────┬───────────────────────┘
                                       │
        ┌───────────────┬──────────────┼──────────────┬───────────────┐
        ▼               ▼              ▼              ▼               ▼
┌───────────────┐ ┌─────────────┐ ┌──────────────┐ ┌─────────────┐
│ Task 1 —      │ │ Task 2 —    │ │ Task 3 —     │ │ Task 4 —    │
│ process       │ │ supply_chain│ │ environmental│ │ human_      │
│ bundle        │ │ bundle      │ │ bundle       │ │ factors     │
│               │ │             │ │              │ │ bundle      │
└───────┬───────┘ └──────┬──────┘ └──────┬───────┘ └──────┬──────┘
        │                │                │                │
        └────────────────┴────────────────┴────────────────┘
                                │  all four landed → final merge
                                ▼
                  ┌─────────────────────────────────────────┐
                  │ Task 5 — Dispatcher rewrite (Send API)  │
                  │ + register 4 new nodes + structlog      │
                  │ timing + Semaphore throttle +           │
                  │ parallel /verify (DoD)                  │
                  └────────────────┬────────────────────────┘
                                   │
                                   ▼
              Phase 3 quality gate runs → tag `v0.4.0-demo` per
              branching_strategy.md §8.
```

**Parallelism rationale.** Tasks 1–4 are four copies of the same vertical slice, each in its own domain. Each task touches only its domain's subtree (`data/domains/<domain>/`, `src/expertview/rag/domains/<domain>.py`, `src/expertview/agents/investigators/<domain>.py`, `src/expertview/prompts/investigator/<domain>.md`, and the matching unit-test file). There is no shared editing surface across the four bundles. The architecture rule from [architecture.md §5](../../architecture.md) — *"Module boundaries are walls"* — is what makes this safe: a process-domain bundle has no reason to import from supply_chain, environmental, or human_factors, and vice versa. The four PRs can be opened, reviewed, and merged in any order.

**Why per-domain bundles instead of layer-by-layer.** Phase 2's pattern (data → loader → investigator → synthesizer → wiring) cut horizontally because the phase had a single domain. Phase 3 has four; cutting horizontally would create four data PRs, four loader PRs, four investigator PRs, etc. — sixteen tiny PRs that all conflict in `data/domains/` or under `agents/investigators/`. Bundling vertically gives four independent PRs whose blast radius is one subdirectory each.

**Sequential pinch point.**

- **Tasks 1/2/3/4 → Task 5**: Task 5 imports each new investigator factory in `make_graph()` and references each new loader. All four bundles must be merged into `main` before the wiring task's final PR.

---

## How to use this folder

1. Pick any unblocked task from the table above (an unblocked task is one whose `Depends on` column is fully merged into `main`). For Phase 3, Tasks 1–4 are all simultaneously unblocked once `v0.3.0-demo` is tagged.
2. Read its file end-to-end before starting. Each task file is self-contained — it states purpose, steps, code locations, connections, and risks.
3. Follow the planning loop in [workflow.md §1](../../workflow.md): clarifying Q&A → plan file → user approval → implement → summarize. The task file is the *scope*, not the plan; the executing agent still writes a plan and gets approval.
4. Open a PR per [branching_strategy.md §5](../../branching_strategy.md). The task file's branch suggestion is a starting point.
5. When all five PRs are merged and the phase quality gate passes, tag `v0.4.0-demo` (per [branching_strategy.md §8](../../branching_strategy.md)) and proceed to Phase 4.

---

## Shared shape across the four domain bundles (Tasks 1–4)

All four bundle tasks share the same skeleton — they differ only in domain content, the clue subset they plant, and the prompt's role framing. The executing agent should treat the mechanical bundle from Phase 2 as the reference implementation. Each bundle produces:

- `data/domains/<domain>/*.md` — 5–10 short, on-topic mock documents.
- `src/expertview/rag/domains/<domain>.py` — loader mirroring [`rag/domains/mechanical.py`](../../../src/expertview/rag/domains/mechanical.py) (separate disk-cache key per domain).
- `src/expertview/prompts/investigator/<domain>.md` — versioned prompt mirroring [`prompts/investigator/mechanical.md`](../../../src/expertview/prompts/investigator/mechanical.md), with the citation requirement preserved verbatim and role framing swapped to the domain.
- `src/expertview/agents/investigators/<domain>.py` — node factory `make_<domain>_investigator_node(store, llm)` mirroring [`agents/investigators/mechanical.py`](../../../src/expertview/agents/investigators/mechanical.py).
- `tests/unit/test_<domain>_investigator.py` — fake-store + fake-LLM unit test asserting `{"findings": [...]}` shape and non-empty citations.

What changes per domain:

- **The corpus content** — each domain plants a different clue subset toward the locked CNC out-of-tolerance scenario. The four corpora must be complementary, not redundant; the per-domain task files specify which clues belong where so the four investigators converge on a coherent multi-domain causal chain.
- **The prompt's role framing** — one line: "You are a process / supply-chain / environmental / human-factors domain RCA investigator." Citation discipline, JSON contract, and Finding-output rules stay identical.
- **The `investigator_domain` field** on emitted `Finding`s — `"process" | "supply_chain" | "environmental" | "human_factors"` respectively.

What does **not** change per domain:

- The node signature, factory shape, and patch return value (`{"findings": [...]}`).
- The `KnowledgeStore` protocol use.
- The `create_investigator_llm()` source (all four investigators share the same `openrouter/owl-alpha` client during build; the synthesizer remains the only model swap point).
- The unit-test shape (fake store, fake LLM, JSON parse → `Finding` list → assert patch).

---

## What this folder is *not* for

- Not a substitute for [build_plan.md](../../build_plan.md) — that document remains the canonical phase definition and quality-gate source.
- Not an architecture document — see [architecture.md](../../architecture.md) for module boundaries and protocol shapes.
- Not a decision log — locked choices live in [decisions.md](../../decisions.md).
- Not implementation guidance — task files name *what* to build and *why*, never prescribed implementations. The executing agent decides the *how*.
