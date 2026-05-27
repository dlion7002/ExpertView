# Task 2 — Conditional-Edge Wiring + Structlog Timing + Integration Test + Parallel `/verify`

> **Branch suggestion**: `feature/phase-4-wiring`
> **Parallelism**: **Sequential.** Final merge point of Phase 4. Edits `orchestration/runner.py` and adds an integration test; must run after Task 1 is merged to `main`.
> **Depends on**: Task 1 merged (i.e., `agents/spawning.py` exports `is_bearing_anomaly`, `agents/investigators/sub_investigator.py` exports `make_sub_investigator_node`, `prompts/investigator/sub_investigator.md` exists, and the three new supplier-history documents are on `main` under `data/domains/supply_chain/`).

## Purpose

Extend Phase 3's graph topology from `dispatcher → [5 investigators in parallel] → synthesizer` to `dispatcher → [5 investigators in parallel] → _should_spawn → (sub_investigator → synthesizer | synthesizer)`. The conditional edge `_should_spawn(state) -> str` reads merged `state["findings"]`, calls `is_bearing_anomaly` from `agents/spawning.py` over each finding, and returns `"sub_investigator"` when the predicate fires for at least one finding or `"synthesizer"` otherwise.

Also lands in this task:

- structlog `info` events at sub-investigator entry and exit, matching the Phase-3 investigator pattern (`investigator.start` / `investigator.finish` with a `domain` tag).
- An integration test in `tests/integration/test_dynamic_spawning.py` that exercises both branches of the conditional edge with fake stores and fake LLMs — no OpenRouter call, deterministic, runs in CI.
- End-to-end `/verify` against the rehearsed CNC incident. The phase quality gate is satisfied here: the LangSmith trace contains both the 5 parallel investigator spans and the dynamically spawned sub-investigator span, and the sub-investigator's `Finding` is cited in the final CausalReport.

## Why it matters

- Until Task 2 ships, the predicate and the sub-investigator node from Task 1 sit unimported on `main` — they exist, but the graph does not route to them. This is the task where dynamic sub-investigation stops being a module and starts being a thing the demo can show.
- [build_plan.md §Phase 4](../../build_plan.md) requires the spawning trigger to "fire reliably on the rehearsed scenario." Reliability is a runtime property; the `/verify` step here is what proves it.
- The conditional-edge function `_should_spawn(state) -> str` is a thin dispatcher over `agents/spawning.py`'s predicates ([build_plan.md §Phase 4 risk mitigation](../../build_plan.md)). Keeping the dispatcher thin means Phase 5 (or any future trigger addition) extends `agents/spawning.py` rather than thickening `orchestration/runner.py`.
- The phase quality gate has a **silent-failure mode**: if the predicate never fires during `/verify`, the run completes successfully but produces a synthesizer-only trace identical to Phase 3's. The integration test in step 4 and the `/verify` assertions in step 5 are designed to detect this — a green CLI exit alone is not the gate.

## Concrete steps (what to produce)

1. **Add `_should_spawn(state: ExpertViewState) -> str` to `src/expertview/orchestration/runner.py`** as a module-level function (not a node — it is the conditional-edge dispatcher). The body:
   - Iterates over `state["findings"]`.
   - Calls `is_bearing_anomaly(finding)` (imported from `agents/spawning.py`) on each.
   - Returns `"sub_investigator"` if any predicate call returns `True`, else `"synthesizer"`.

   Keep the function pure (no LLM call, no logging that affects state, no I/O). The function name `"sub_investigator"` and `"synthesizer"` are the LangGraph node names the conditional edge will route to — they must match the names used in `add_node(...)` in step 2.
2. **Register the sub-investigator node and wire the conditional edge in `make_graph()`** (`src/expertview/orchestration/runner.py`):
   - Construct the sub-investigator's store via Phase 3's `rag/domains/supply_chain.py` loader — **the same store instance used by the supply_chain investigator**. Reusing the same store avoids embedding the supply_chain corpus twice and keeps cache invalidation simple.
   - Construct the shared investigator LLM via `create_investigator_llm()` from `agents/llms.py` (the same client the five investigators use; it already passes through Phase 3's `asyncio.Semaphore`).
   - Call `make_sub_investigator_node("supply_chain", supply_chain_store, investigator_llm)` to bind the dependencies.
   - Register the result as a node under the name `"sub_investigator"` — the same name `_should_spawn` returns.
   - Wire the conditional edge: each of the five investigator nodes' outgoing edges previously went to `"synthesizer"`. After this task, those edges go to a join point (the LangGraph idiom for "wait for all five branches before evaluating a conditional"; the exact mechanism — a no-op join node, a conditional edge from each investigator that converges, or the `add_conditional_edges` API directly off the dispatcher's fan-out — is the executing agent's call. The phase-3 task-5 file took the same "name the contract, defer the idiom" stance for `Send`; do likewise here).
   - The conditional edge after the join routes via `_should_spawn` to either `"sub_investigator"` or `"synthesizer"`.
   - The sub-investigator's outgoing edge goes to `"synthesizer"`.

   The contract that matters for the quality gate: when the predicate fires, the sub-investigator runs *after* the five parallel investigators have merged their findings and *before* the synthesizer runs. The synthesizer must see both the five-investigator findings and the sub-investigator's finding in the same `state["findings"]` list.
3. **Add structlog timing events to the sub-investigator node**. This is a small edit inside `make_sub_investigator_node`'s returned async function in `agents/investigators/sub_investigator.py` (a Task-1 file). On entry, emit `log.info("investigator.start", domain="sub_investigator", incident_id=<id>)`; on exit, emit `log.info("investigator.finish", domain="sub_investigator", finding_count=<n>)`. Use `domain="sub_investigator"` in the log events (this is the trace label, not the `Finding.investigator_domain` field — the finding label remains `"supply_chain"` per Task 1's contract).

   **This edit touches a file Task 1 owns.** Document it in the PR description as a deliberate cross-task touch — the structlog events were not in Task 1's scope because Task 1 did not need to know about the dispatcher's observability contract. The edit is two lines.
4. **Add an integration test** in `tests/integration/test_dynamic_spawning.py` exercising both branches of the conditional edge:
   - **Spawn-fires branch**: build `make_graph()` with fake stores and fake LLMs. The mechanical fake LLM is configured to return a bearing-anomaly `Finding`; the other four return their normal domain findings. Invoke the graph against a fixture `Incident`. Assert: `state["findings"]` contains one sub-investigator-produced finding with `investigator_domain="supply_chain"`; the synthesizer received findings from all five domains *plus* the sub-investigator's finding; the LangGraph execution order shows the sub-investigator running before the synthesizer.
   - **Spawn-falls-through branch**: same setup but the mechanical fake LLM returns a non-bearing finding. Invoke the graph. Assert: no sub-investigator finding appears in `state["findings"]`; the synthesizer receives five findings; the LangGraph execution order does not include a sub-investigator span.

   The test does not hit OpenRouter — fake LLMs return hard-coded JSON. It runs on every CI invocation and is the **regression guard** that catches a future refactor accidentally inverting the conditional edge or skipping the sub-investigator entirely.
5. **Run the end-to-end `/verify`** against the rehearsed incident:
   - `uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml`
   - Confirm: a coherent multi-domain `CausalReport` prints with citations including at least one citation referencing a supplier-history document added in Task 1.
   - Confirm: the LangSmith trace contains six investigator-class spans — five from the parallel fan-out plus one sub-investigator span as a child of the dispatcher (or wherever the conditional edge attaches in the topology).
   - Confirm: the structlog output contains an `investigator.start` / `investigator.finish` event pair with `domain="sub_investigator"`.
   - Confirm: the sub-investigator's `Finding` is **cited** in the final CausalReport (not merely present in `state["findings"]`). This is the load-bearing quality-gate assertion — a citation in the report is what proves the synthesizer consumed the sub-investigator's finding.
6. **Verify locally**: `uv run pytest` green; `uv run ruff check .` and `uv run ruff format --check .` clean; the manual `/verify` from step 5 produces a successful run with the sub-investigator span and citation assertions satisfied.

## What each step does

- **Step 1** establishes the conditional-edge dispatcher as a thin function over `agents/spawning.py`'s predicate. Future trigger additions extend the predicate module, not this function.
- **Step 2** wires the new node and the conditional edge so the predicate's `True` branch actually reaches the sub-investigator at runtime. Without this, the predicate fires but the graph does not respond.
- **Step 3** produces the application-side observability log for the sub-investigator span, matching the Phase-3 investigator pattern. structlog interleaving in the log file is what proves the spawn fired without a LangSmith UI open.
- **Step 4** locks both branches of the conditional edge as regression tests. The fake-LLM design makes the test deterministic and CI-runnable; the manual `/verify` is the live demo of the phase, the integration test is the CI guarantee.
- **Step 5** is the quality gate itself. `/verify` is the DoD; without a successful rehearsal showing the sub-investigator span *and* its citation in the report, the phase is not done.
- **Step 6** is the local check before opening the PR.

## Code locations

- `src/expertview/orchestration/runner.py` (edit — add `_should_spawn` function, register sub-investigator node, wire conditional edge).
- `src/expertview/agents/investigators/sub_investigator.py` (edit — add structlog start/finish events; cross-task touch into a Task-1 file).
- `tests/integration/test_dynamic_spawning.py` (new — two-branch conditional-edge regression test).

## Connections

**Upstream**:

- [[task-1-spawning-predicates-and-sub-investigator]] — provides `is_bearing_anomaly` (imported by `_should_spawn`), `make_sub_investigator_node` (imported by `make_graph()`), the `sub_investigator.md` prompt (loaded inside the sub-investigator node), and the three supplier-history corpus documents (consumed by the supply_chain `KnowledgeStore` at retrieval time).
- Phase 3 — `rag/domains/supply_chain.py` (the loader the sub-investigator's store is constructed from), `agents/llms.py` (the `create_investigator_llm()` factory and the semaphore the shared client passes through), `orchestration/runner.py` (the existing dispatcher and `Send`-API fan-out — this task extends, does not rewrite).
- Phase 2 — `agents/synthesizer.py` (unchanged; reads merged `findings` from state).
- Phase 1 — `orchestration/state.py` (`ExpertViewState` and the `operator.add` reducer on `findings` that merges the sub-investigator's `Finding` into the same list).
- LangGraph's conditional-edge API (`add_conditional_edges` and its `path_map` parameter) — the framework primitive `_should_spawn` plugs into.

**Downstream**:

- Phase 5's evidence-weighted convergence may treat sub-investigator findings differently from parallel-investigator findings (e.g., weight by spawn depth). The `domain="sub_investigator"` structlog tag and the sub-investigator's distinct span in the LangSmith trace are what make this distinction queryable.
- Phase 6's UI will render the sub-investigator span in the live status panel and the Mermaid topology diagram. The conditional edge appears in `compiled_graph.get_graph().draw_mermaid()` automatically — no UI-side change is needed in this task.
- Phase 7's retry/backoff wrapper will sit alongside Phase 3's semaphore in `agents/llms.py`; the sub-investigator's LLM call goes through the same client and therefore inherits the wrapper for free.

## Parallelism rationale

- This task is **sequential by necessity**: it edits `orchestration/runner.py` (shared) and `agents/investigators/sub_investigator.py` (Task-1 file, cross-task touch for the structlog events). Either edit would conflict with Task 1 if attempted in parallel.
- The final-merge pinch point is intentional: Task 1 proves the predicate and the sub-investigator node work in isolation; Task 2 proves they work together when wired into the graph.

## Risks / constraints / assumptions

- **Constraint**: LLM clients live only in `agents/llms.py` ([CLAUDE.md architecture rules](../../../CLAUDE.md)). The sub-investigator node receives its LLM via the factory's argument; the wiring in step 2 calls `create_investigator_llm()` from `agents/llms.py` and passes the result into `make_sub_investigator_node`.
- **Constraint**: nodes are pure async `(State) -> dict` functions ([architecture.md §5](../../architecture.md)). `_should_spawn` is not a node; it is a conditional-edge function whose contract is `(State) -> str` (a target node name). The architecture rule about pure async nodes does not apply to it, but it should still be pure (no I/O, no LLM calls, no side effects) — see Phase 4's risk-mitigation language about thin dispatchers.
- **Constraint**: module boundaries are walls ([architecture.md §5](../../architecture.md)). `runner.py` imports from `agents/spawning.py` and `agents/investigators/sub_investigator.py` — both `agents/` modules, which is the existing import direction. No new boundary is crossed.
- **Risk — silent fall-through**: if the predicate never fires during `/verify`, the run completes successfully with a synthesizer-only trace and the CLI exits 0. The phase gate fails silently. Mitigation: the `/verify` checklist in step 5 explicitly asserts the sub-investigator span *exists* in the LangSmith trace *and* its finding is cited in the CausalReport — not just that the run succeeded.
- **Risk — predicate fires on the wrong finding**: if `is_bearing_anomaly` over-matches (e.g., fires on a non-anomaly mechanical finding that mentions "bearing"), the sub-investigator spawns when it should not have. Mitigation: Task 1's predicate unit tests cover the truth table; the spawn-falls-through branch of the integration test in step 4 confirms the predicate does not over-fire on a non-bearing finding.
- **Risk — conditional edge attaches at the wrong topology point**: if the conditional edge attaches *before* the five investigators merge (i.e., reading `state["findings"]` before all five branches have written), the predicate runs on an incomplete findings list and may miss the bearing-anomaly finding that lands later. Mitigation: the conditional edge attaches *after* the join — either via a no-op join node or via LangGraph's native merge semantics (the exact idiom is the executing agent's call, but the contract is "post-merge predicate evaluation"). The integration test's spawn-fires branch covers this case.
- **Risk — sub-investigator runs in parallel with synthesizer instead of before it**: a misconfigured edge could route both `"sub_investigator"` and `"synthesizer"` from the join, causing them to run concurrently — the synthesizer would miss the sub-investigator's finding. Mitigation: the wiring routes the conditional edge to *one of* `"sub_investigator"` or `"synthesizer"`, and `"sub_investigator"`'s outgoing edge goes to `"synthesizer"`. The integration test asserts the sub-investigator's finding is in `state["findings"]` when the synthesizer fake LLM is called.
- **Risk — `/verify` LangSmith trace appears empty or partial**: LangSmith tracing depends on the env-var setup from Phase 1. If `LANGSMITH_API_KEY` is unset or stale, the trace check in step 5 silently fails. Mitigation: the executing agent confirms LangSmith setup before declaring `/verify` complete (re-run the Phase 3 `/verify` first if the trace surface looks empty).
- **Risk — OpenRouter free-tier limits during a real `/verify` run with six investigator-class LLM calls**: Phase 3's semaphore caps concurrent investigator calls at five, so the sub-investigator's call (which runs *after* the five parallel investigators, not in parallel with them) sits within the cap. No additional throttling is required for Phase 4. If empirical 429s appear, the same mitigation as Phase 3 applies (lower the semaphore cap) — but Phase 7's retry/backoff is the real fix, not this task's.
- **Assumption**: the synthesizer prompt produces a CausalReport that cites sub-investigator findings when they are present in `state["findings"]`. If `/verify` shows the sub-investigator's finding in `state["findings"]` but no citation in the report, that is a prompt-iteration concern (edit `prompts/synthesizer/default.md`), not a graph-wiring concern. Note the iteration but do not let it block the phase gate; the gate language requires the citation, so prompt iteration may be necessary inside this task to reach green.
- **Assumption**: Task 1's predicate is calibrated correctly. If `/verify` shows the predicate firing on the wrong finding (or not firing at all on the rehearsed scenario), that is a predicate-calibration concern owned by Task 1 — a follow-up PR adjusts the predicate, not the wiring.

## Definition of done

- `_should_spawn(state) -> str` exists in `orchestration/runner.py` as a thin dispatcher over `is_bearing_anomaly` (imported from `agents/spawning.py`) and returns either `"sub_investigator"` or `"synthesizer"`.
- `make_graph()` registers the sub-investigator node by name `"sub_investigator"`, bound to the supply_chain `KnowledgeStore` (shared with the supply_chain investigator) and the shared investigator LLM.
- The conditional edge wires from the post-fan-out join via `_should_spawn` to either `"sub_investigator"` or `"synthesizer"`, and `"sub_investigator"`'s outgoing edge goes to `"synthesizer"`.
- The sub-investigator node emits `investigator.start` and `investigator.finish` structlog events with `domain="sub_investigator"`.
- `tests/integration/test_dynamic_spawning.py` exists and passes; both the spawn-fires and spawn-falls-through branches are exercised, and the spawn-fires branch asserts sub-investigator-produced findings reach the synthesizer.
- Manual `/verify` against `data/incidents/cnc_out_of_tolerance.yaml` succeeds:
  - A coherent multi-domain `CausalReport` is printed with citations including at least one supplier-history document.
  - The LangSmith trace shows six investigator-class spans (five parallel + one sub-investigator).
  - The structlog log contains an `investigator.start` / `investigator.finish` event pair with `domain="sub_investigator"`.
  - The sub-investigator's `Finding` is cited in the CausalReport (not merely present in `state["findings"]`).
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/phase-4-wiring` per [branching_strategy.md §5](../../branching_strategy.md). PR description:
  - Notes the cross-task structlog edit into `agents/investigators/sub_investigator.py` and explains why it lives here rather than in Task 1.
  - Includes a link or screenshot of the LangSmith trace showing the sub-investigator span as a child of the dispatcher (or wherever the conditional edge attaches in the topology).
  - Records the topology choice for the post-fan-out join (no-op join node, conditional edge from each investigator, or another idiom) — this is the implementation detail Phase 5 will need to know about to extend the conditional edge.
  - Calls out whether any synthesizer prompt iteration was required to surface the sub-investigator's citation in the CausalReport, and if so, links the prompt diff.
- Once merged, tag `v0.5.0-demo` per [branching_strategy.md §8](../../branching_strategy.md). Phase 5 (evidence-weighted convergence) is unblocked.
