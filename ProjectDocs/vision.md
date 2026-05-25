# ExpertView — Vision

> Anchored to [project_introduction.md](project_introduction.md). This document captures the *why*, *who*, *what counts as done*, and *what we explicitly are not building*. Read this first when starting any new session.

## Problem (one paragraph)

When an operational incident hits an industrial site — a machine fails, a process drifts out-of-spec, a delivered batch is bad, a service degrades — finding the root cause is slow, sequential, and structurally broken. The data isn't missing; it's scattered across mechanical, process, supply-chain, environmental, and human-factors domains, and no single investigator can hold all of it at once. Today's mean time to root cause spans days to weeks because each team investigates its own domain in turn. The same root causes recur because the full picture is never assembled. **ExpertView** addresses this with parallel, multi-agent investigation: heterogeneous domain experts run simultaneously, share evidence, spawn sub-investigations dynamically, and converge on a weighted causal explanation.

## Intended users

- **Industrial reliability engineers** running Root Cause Analysis (RCA) on manufacturing incidents.
- **Operations / incident response leads** who need a defensible causal report fast.
- **Quality engineers** investigating recurring out-of-spec product issues.

The demo audience at the hackathon will be judges with mixed technical depth, so the system must be *visually legible* (the parallelism must be obvious) and *narratively legible* (the causal report must read like an investigation, not a JSON dump).

## Project mode

**This is a pre-hackathon build.** ExpertView is constructed in advance over multiple sessions and brought to the event already polished. The hackathon day itself is for final-touch adaptation, not first-time construction. See [build_plan.md](build_plan.md) for the phase breakdown and the at-event usage strategy.

## Success criteria (for the finished pre-hackathon system)

A "done" pre-hackathon ExpertView must satisfy all of the following:

1. **Visible parallelism**: 5 domain investigators (mechanical, process, supply chain, environmental, human factors) run concurrently — not sequentially — against an incident, and the parallelism is observable in the UI or logs.
2. **Dynamic sub-investigation**: at least one spawning trigger fires reliably on the rehearsed scenario (e.g., a mechanical anomaly triggers a supplier-history sub-investigator), and the spawned agent's finding is folded into the final report.
3. **Evidence-weighted convergence**: the synthesizer produces a causal report with explicit confidence scores per hypothesis and citations back to the source documents in the domain RAG stores.
4. **One fully rehearsed scenario**: a single concrete incident (chosen during phase 0) runs end-to-end with deterministic mock data, reproducibly, on the demo laptop with hotspot-backed network as the failsafe. (Cloud-only posture — see [decisions.md](decisions.md) entry dated 2026-05-25.)
5. **Modular boundaries preserved**: the RAG layer, the parallel orchestration runner, the evidence convergence logic, and the agent abstraction are each independently lift-able into a new repo. This is the *Path B* safety net if the hackathon brief diverges from RCA.

## Non-goals (explicit)

- **Not a production system.** No auth, no multi-tenancy, no audit trail, no compliance posture.
- **Not real-time.** No streaming sensor ingest, no PLC/MES integration.
- **Not connected to live data.** All corpora are mock documents created for the demo.
- **Not a generic agent framework.** We are *not* building a reusable orchestration library — we are building a clean, modular RCA system whose modules happen to be lift-able. See [decisions.md](decisions.md) for the locked decision.
- **Not horizontally scalable.** Single process, single machine. If we need to demonstrate scale, we demonstrate it conceptually, not in code.

## Reusability principle (the Path B safety net)

Every module boundary in [architecture.md](architecture.md) exists so that, if the hackathon brief turns out to require a different application (e.g., medical diagnosis triage, security incident triage, customer support escalation), the user can lift the building blocks — `rag/`, `orchestration/`, `evidence/`, `agents/base.py`, `prompts/` — into a new project and build the divergent use case on top. The cost of preserving these boundaries during the pre-hackathon build is small; the option value at the event is large.

## What this document is *not* for

This document does not specify the architecture (see [architecture.md](architecture.md)), the build order (see [build_plan.md](build_plan.md)), or how Claude should behave during development (see [workflow.md](workflow.md) and [CLAUDE.md](../CLAUDE.md)). Keep this document anchored to *intent*; if it drifts toward implementation detail, that detail belongs elsewhere.
