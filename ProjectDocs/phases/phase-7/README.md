# Phase 7 — Polish + Rehearsal (Planning Index)

> **Source**: [build_plan.md §Phase 7](../../build_plan.md). This folder breaks Phase 7 into agent-executable task files. Each task file tells the executing agent **what** to produce, not **how** to write it — the agent picks implementation details using its own judgment, the architecture rules in [architecture.md §5](../../architecture.md), and the standards in [CLAUDE.md](../../../CLAUDE.md).
>
> **Phase goal (verbatim from build_plan.md)**: one fully scripted scenario, retries on transient OpenRouter failures, deterministic mock data for reproducible demos, the synthesizer swap to the paid frontier model exercised on the demo laptop, a LangSmith trace replay path as the final fallback.
>
> **Phase quality gate (verbatim from build_plan.md)**: three consecutive clean runs of the demo scenario on the actual demo laptop — at least one of them with `EXPERTVIEW_SYNTH_MODEL` set to a paid frontier ID to confirm the demo-path. A successful LangSmith trace is exported.

---

## Pre-flight

Phase 6 must be merged and tagged `v0.7.0-demo` before any task in this phase starts. That tag carries the in-process `orchestration/streaming.py` adapter (typed `ProgressEvent` + `SpawnDecision` + `WAITING/ACTIVE/COMPLETE/SKIPPED` flow helper + `render_topology_mermaid`), the Streamlit single-screen demo app under `src/expertview/ui/`, the live CLI `--live` mode in `cli.py`, and the cross-surface watched `/verify` that closed Phase 6. Phase 7 adds resilience and rehearsal *around* that working surface — it does not modify the graph topology, the five investigators, the dispatcher, the conditional edge, the synthesizer body, the two-pass reasoning pipeline, the convergence math, or the prompts. Every node, model identifier, and prompt is consumed as-is.

Two scope edges are locked for this phase (2026-05-27 planning Q&A, to be logged in [decisions.md](../../decisions.md) when Task 3 lands):

- **Tasks 1–3 land only automatable work; the human rehearsal is a separate post-merge checklist.** Per user direction 2026-05-27, the executing agent does *not* perform the paid-synth swap, the three rehearsal runs, the trace export from a live run, or any watched observation — those require the user at the keyboard, deciding when to spend $5-credit budget, and observing behavior the agent cannot evaluate. Tasks 1–3 ship the code, tooling, runbook, helper scripts, and top-level `README.md` that the user needs to fire the rehearsal in one short sitting. The "three consecutive clean runs on the actual demo laptop" portion of the quality gate is deferred for this round (no demo laptop is in use yet); when a demo laptop is procured, the user runs the rehearsal checklist that Task 3 produced. The effective close condition for *this round* is: Tasks 1–3 merged with all automatable contents on `main` — the human rehearsal is downstream, not blocking the merge or the phase tag. The deferral and the human-checklist hand-off are recorded in [decisions.md](../../decisions.md) at phase close.
- **Reranker reintroduction (local `CrossEncoder` per [architecture.md §7](../../architecture.md)) stays deferred.** Phase 5 explicitly deferred it unless retrieval — not convergence or surface — was the bottleneck; the Phase 6 watched `/verify` did not surface a retrieval gap. If a follow-up rehearsal later shows one, that is a separate task with its own [decisions.md](../../decisions.md) entry, not a Phase 7 edit.

One small documentation rule is folded into Task 1 (per the planning Q&A): the **embedding cache invalidation rule** is formalized as a docstring/comment block in `agents/llms.py` near `create_embeddings()`, alongside the deterministic-seed work. It does not get a standalone doc file.

Out of scope for Phase 7, called out so the executing agent does not pick them up: further `structlog` polish (the Phase 3 timing logs are sufficient), any new investigator or domain, any prompt iteration (prompts are in their post-Phase-5 form), any change to convergence weights or scoring, any new UI surface, and any draft of the `agent-trace-replay` / `rca-investigator-prompt` / `domain-rag-seed` skill candidates ([open_questions.md §Skill candidates](../../open_questions.md)).

---

## Task list

| # | Task | Branch | Parallelism | Depends on |
|---|---|---|---|---|
| 1 | [LLM hardening: retry/backoff + determinism + cache-invalidation docstring](task-1-llm-hardening.md) | `feature/phase-7-llm-hardening` | Parallelizable with Task 2 | Phase 6 complete (`v0.7.0-demo` tagged) |
| 2 | [LangSmith trace export artifact + documented replay path](task-2-trace-export-and-replay.md) | `feature/phase-7-trace-export-and-replay` | Parallelizable with Task 1 | Phase 6 complete (`v0.7.0-demo` tagged) |
| 3 | [Rehearsal materials + top-level README + human-checklist hand-off](task-3-paid-synth-rehearsal-and-readme.md) | `feature/phase-7-rehearsal-and-readme` | Sequential (final merge point) | Task 1 and Task 2 |

Three tasks, one PR each, per the lightweight GitHub Flow locked in [decisions.md (2026-05-25)](../../decisions.md) and detailed in [branching_strategy.md](../../branching_strategy.md). Branch names are suggestions; the executing agent may consolidate if a task is small and the dependency graph permits.

---

## Dependency graph

```text
                ┌──────────────────────────────────────────────┐
                │  Phase 6 merged + tagged v0.7.0-demo         │
                │  (streaming core + Streamlit app + live CLI  │
                │   mirror; watched /verify passed)            │
                └───────────────┬──────────────────┬───────────┘
                                │                  │
                                ▼                  ▼
          ┌───────────────────────────┐  ┌──────────────────────────────┐
          │ Task 1 — LLM hardening    │  │ Task 2 — Trace export + replay│
          │   - agents/llms.py        │  │   - export tooling (CLI       │
          │     (retry/backoff for    │  │     subcommand or script)     │
          │      429s + 5xxs;         │  │   - vendored trace artifact   │
          │      deterministic seed;  │  │     under data/traces/        │
          │      embedding cache-     │  │   - documented replay path    │
          │      invalidation rule)   │  │     (replays a saved trace    │
          │   - unit tests with fake  │  │      back into the same       │
          │     transport (no live    │  │      CausalReport render)     │
          │     HTTP)                 │  │   - unit tests                │
          └─────────────┬─────────────┘  └────────────────┬─────────────┘
                        │                                  │
                        │  retry + seed + cache-rule       │  export + replay landed
                        └─────────────────┬────────────────┘
                                          ▼
                  ┌─────────────────────────────────────────┐
                  │ Task 3 — Rehearsal materials + README   │
                  │ + human-checklist hand-off              │
                  │   - README.md (top-level) 1-minute      │
                  │     run-it-yourself guide listing       │
                  │     OPENROUTER_API_KEY + LANGSMITH_API_ │
                  │     KEY and the replay command          │
                  │   - rehearsal runbook (the human        │
                  │     checklist for the paid-synth swap   │
                  │     + 3 demo runs + trace export)       │
                  │   - optional helper script wrapping the │
                  │     env-var setup + demo commands       │
                  │   - any thin pre-flight doctor checks   │
                  │   NO paid-synth run by the executing    │
                  │   agent; NO 3-run observation here.     │
                  └────────────────┬────────────────────────┘
                                   │
                                   ▼
              Phase 7 effective close (merge of automatable
              work) → tag `v0.8.0-demo` per branching_strategy.md
              §8. The laptop-bound 3-run observational gate is a
              post-merge human checklist (executed by the user
              when a demo laptop is in use), not new task scope.
```

**Parallelism rationale.** Tasks 1 and 2 share no editing surface and can run concurrently. Task 1 touches only `src/expertview/agents/llms.py` (edit) and `tests/unit/test_llms.py` (new if absent); per [architecture.md §5](../../architecture.md)'s *"module boundaries are walls"* and *"LLM provider clients are instantiated only in `agents/llms.py`"* rules, the retry wrapper lives inside `agents/llms.py` next to the existing `ThrottledInvestigatorLlm`, and nothing downstream needs to know. Task 2 touches export tooling (a new `cli.py` subcommand or a small script under `scripts/`), a new vendored artifact under `data/traces/`, and its own tests — disjoint from `agents/llms.py`. Task 3 is the only task that imports from both — it relies on Task 1's retry/backoff for a robust paid-synth call and on Task 2's export tooling for the trace artifact — and it also writes the top-level `README.md`, so it is sequential by necessity.

**Sequential pinch points.**

- **Task 1 → Task 3**: the rehearsal runbook in Task 3 instructs the user to set `EXPERTVIEW_SYNTH_MODEL` to a paid frontier ID and run the demo against both incidents. The runbook can only honestly promise resilience on those runs once Task 1's retry/backoff is on `main`. The runbook should be written assuming Task 1 has landed.
- **Task 2 → Task 3**: the runbook references the trace-export command and the replay command that Task 2 ships; the README documents the replay path. Without Task 2 merged, the runbook would point at commands that do not exist and the README would have no replay path to mention.
- **Task 1 ∥ Task 2**: explicitly *not* a pinch point — they edit disjoint files and the executing agent may take them in either order or in parallel.

---

## How to use this folder

1. Pick the next unblocked task from the table above (an unblocked task is one whose `Depends on` column is fully merged into `main`). For Phase 7, Tasks 1 and 2 are both unblocked at the start; Task 3 unblocks once both are merged.
2. Read its file end-to-end before starting. Each task file is self-contained — it states purpose, steps, code locations, connections, and risks.
3. Follow the planning loop in [workflow.md §1](../../workflow.md): clarifying Q&A → plan file → user approval → implement → summarize. The task file is the *scope*, not the plan; the executing agent still writes a plan and gets approval.
4. Open a PR per [branching_strategy.md §5](../../branching_strategy.md). The task file's branch suggestion is a starting point.
5. When all three PRs are merged and the **effective close conditions in the pre-flight** are met (all automatable materials on `main`), log the phase close (including the laptop-gate deferral and the human-checklist hand-off) in [decisions.md](../../decisions.md) and tag `v0.8.0-demo` per [branching_strategy.md §8](../../branching_strategy.md). The user then fires the **rehearsal runbook produced by Task 3** when a demo laptop is in use — paid-synth swap, three demo runs, trace export, and watched observation are all human steps performed against the merged code; they do not block the phase tag.

---

## Skill-candidacy flag (carried forward from Phases 4–6)

Phase 7 finally lands the **trace-export + replay path** that the `agent-trace-replay` skill candidate in [open_questions.md §Skill candidates](../../open_questions.md) has been blocked on. After Task 2 merges, the skill is **candidate-ready**: there is a documented tooling path that a future skill could wrap. But the skill is still at occurrence count one in Phase 7 — once for the rehearsal trace — and CLAUDE.md's threshold is **≥3 repetitions**. Per the "propose, do not apply" rule, no skill is drafted in Phase 7. Surface the readiness at phase close so the user can decide when (and whether) to promote it; the natural trigger is a third reuse, e.g., a Path-B hackathon-day debugging session or a follow-up incident the user wants to replay.

The other two candidates remain unchanged: `rca-investigator-prompt` (six investigator-shaped repetitions across Phases 2–4) and `domain-rag-seed` (five domain-loader repetitions across Phases 2–3) are still over the threshold and still un-drafted — these are unrelated to Phase 7's scope.

---

## What this folder is *not* for

- Not a substitute for [build_plan.md](../../build_plan.md) — that document remains the canonical phase definition and quality-gate source.
- Not an architecture document — see [architecture.md](../../architecture.md) for module boundaries and protocol shapes.
- Not a decision log — locked choices live in [decisions.md](../../decisions.md).
- Not implementation guidance — task files name *what* to build and *why*, never prescribed implementations. The executing agent decides the *how*.
