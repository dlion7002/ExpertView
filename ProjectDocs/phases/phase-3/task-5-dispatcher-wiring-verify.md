# Task 5 — Dispatcher Rewrite + Wiring + Structlog Timing + Throttle + Parallel `/verify`

> **Branch suggestion**: `feature/phase-3-wiring`
> **Parallelism**: **Sequential.** Final merge point of Phase 3. Edits `orchestration/runner.py` and `agents/llms.py` — both shared files. Must run after Tasks 1, 2, 3, and 4 are merged to `main`.
> **Depends on**: Tasks 1, 2, 3, and 4 all merged (i.e., `agents/investigators/{process,supply_chain,environmental,human_factors}.py` + corresponding loaders, prompts, and corpora exist on `main`).

## Purpose

Rewrite Phase 2's dispatcher body so the graph fans out from `dispatcher → mechanical → synthesizer` to `dispatcher → [mechanical | process | supply_chain | environmental | human_factors] → synthesizer`. The fan-out uses LangGraph's `Send` API so the five investigator branches execute concurrently and their `Finding`s merge into shared state via the `operator.add` reducer on `ExpertViewState.findings`.

Also lands in this task:

- The `asyncio.Semaphore(5)` throttle inside `agents/llms.py` covering the investigator LLM client — pre-empts OpenRouter free-tier rate-limit risk on parallel dispatch ([build_plan.md §Phase 3 risk register](../../build_plan.md)).
- Structlog `info` events at investigator-node entry and exit with timestamps and a `domain` tag, complementing the LangSmith trace with an application-side timing log.
- End-to-end `/verify` against the rehearsed CNC incident. The phase quality gate is satisfied here: wall-time ≈ slowest investigator, LangSmith trace shows five overlapping spans, structlog log shows interleaved start times.

## Why it matters

- This is the task where the parallel-fan-out architecture stops being a diagram and starts being a thing the demo can show. Until Task 5 ships, the four new investigators sit unwired on `main`.
- Phase 3's quality gate is **timing-based**: the gate fails if the run is sequential. Task 5 is where that gate is exercised. Getting the `Send` API call shape wrong (e.g., emitting from a non-dispatcher node, or returning a list instead of `Send(...)` objects) collapses the fan-out to sequential and the gate fails silently — the test must assert wall-time, not just success.
- The throttle in `agents/llms.py` is the single CLAUDE.md-compliant home for rate-limit handling. Placing it in the dispatcher would put rate-limit logic in `orchestration/`, which violates [architecture.md §5](../../architecture.md)'s "LLM clients only in `agents/llms.py`" rule.

## Concrete steps (what to produce)

1. **Rewrite `dispatcher` in `src/expertview/orchestration/runner.py`** so its body emits five `Send(...)` calls — one per investigator node — instead of routing to a single mechanical node. The dispatcher receives the current `ExpertViewState`, derives whatever per-branch state slice is needed (likely the same `Incident` and an empty `findings` accumulator handled by the reducer), and returns a list of `Send` objects:
   - `Send("mechanical", state_slice)`
   - `Send("process", state_slice)`
   - `Send("supply_chain", state_slice)`
   - `Send("environmental", state_slice)`
   - `Send("human_factors", state_slice)`

   Reference [LangGraph's `Send` API docs](https://langchain-ai.github.io/langgraph/concepts/low_level/#send) for the exact return shape and conditional-edge wiring. The dispatcher itself remains a thin node — it does not call any LLM, it only emits the fan-out.
2. **Register the four new investigator nodes in `make_graph()`** (`src/expertview/orchestration/runner.py`):
   - Construct each domain's store via its loader (`rag/domains/process.py`, etc.).
   - Construct the shared investigator LLM via `create_investigator_llm()` from `agents/llms.py`. All five investigators share the same client (this is what makes the `Semaphore` in step 3 effective).
   - Call each `make_<domain>_investigator_node(store, llm)` factory to bind the store and LLM.
   - Register the resulting async function as a node under its domain name (`"mechanical"`, `"process"`, `"supply_chain"`, `"environmental"`, `"human_factors"`) — the same name the dispatcher's `Send(...)` targets.
   - Wire the conditional edge from the dispatcher to the five investigator nodes (LangGraph's pattern for `Send`-based fan-out).
   - Each investigator node's outgoing edge goes to the synthesizer.
3. **Add an `asyncio.Semaphore(5)` to `src/expertview/agents/llms.py`**, scoped to the investigator client (not the synthesizer). Two acceptable shapes; the executing agent picks one:
   - Wrap the investigator `ChatOpenAI` instance in a thin async wrapper class that acquires the semaphore around `ainvoke` / `astream` calls.
   - Or expose a module-level async helper (e.g., `investigator_call(llm, prompt)`) that holds the semaphore and is what the investigator nodes call instead of `llm.ainvoke(...)` directly. This requires a 1-line change inside each investigator node to call through the helper — propose this option *only* if the wrapper approach turns out to break LangChain's runnable composition.

   The semaphore lives at the module level in `agents/llms.py` (instantiated once at import; shared across all investigator nodes). Synthesizer calls do not pass through it. The cap is 5 — matching the dispatcher's fan-out width — so all five investigator branches can proceed simultaneously but additional parallel dispatch (e.g., Phase 4's spawned sub-investigators) queues. Document the cap with a one-line comment per [CLAUDE.md coding standards](../../../CLAUDE.md) "non-obvious WHY only" rule (the cap of 5 deliberately matches the dispatcher's width — that is the non-obvious bit).
4. **Add structlog timing events at investigator-node boundaries.** Each investigator node, on entry, emits `log.info("investigator.start", domain=<domain>, incident_id=<id>)`. On exit (before returning the patch), emits `log.info("investigator.finish", domain=<domain>, finding_count=<n>)`. The structlog config from Phase 1 already produces timestamped JSON output; no config changes needed here.

   Implementation: add the two log lines inside each `make_<domain>_investigator_node`'s returned async function. **This is a 6-file edit** — once per existing domain. The edits to `mechanical.py` (Phase 2) and the four Phase-3 domains are mechanical and small; document that this is a deliberate touch of files outside Task 5's primary surface in the PR description.
5. **Run the end-to-end `/verify`** against the rehearsed incident:
   - `uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml`
   - Confirm: a coherent multi-domain `CausalReport` prints with citations from at least three different domain corpora.
   - Confirm: the LangSmith trace shows **five investigator spans overlapping in time** (not stacked sequentially).
   - Confirm: the structlog output shows `investigator.start` events interleaved (not in a single block followed by all `investigator.finish` events).
   - Confirm: total wall time ≈ slowest single-investigator span (within a tolerance — the synthesizer call adds a fixed tail; the dispatcher + state-merge overhead is small). A reasonable assertion is "total wall time < 1.5× max(investigator span time)"; pick a threshold that holds during rehearsal and document it in the PR description.
6. **Add an integration test** in `tests/integration/test_parallel_fanout.py` that exercises the timing-based gate without an LLM call:
   - Build `make_graph()` with fake stores and fake LLMs (the fake LLM sleeps for a fixed interval — say 0.5s — to simulate latency).
   - Invoke the graph against a fixture `Incident`.
   - Assert total wall time is within `~1.5×` of the fake-LLM sleep interval (i.e., parallel), not `~5×` (i.e., sequential).
   - Assert the resulting state's `findings` list has entries from all five domains.

   This test is the **regression guard** — it is what catches if a future refactor accidentally collapses the fan-out to sequential. It does not hit OpenRouter, so it runs on every CI invocation.
7. **Verify locally**: `uv run pytest` green; `uv run ruff check .` and `uv run ruff format --check .` clean; the manual `/verify` from step 5 produces a successful run with the timing assertion satisfied.

## What each step does

- **Step 1** is the core architectural move of the phase: the dispatcher stops being a passthrough and starts being a fan-out emitter. Everything else in this task supports or verifies this change.
- **Step 2** registers the new investigator nodes so the `Send` targets resolve. Without this, the dispatcher's `Send("process", ...)` raises a KeyError.
- **Step 3** addresses the rate-limit risk proactively (per the locked decision earlier this planning session). Placing it in `agents/llms.py` honors the architecture rule that LLM clients live in one place.
- **Step 4** produces the complementary application-side timing log. structlog's interleaving is what proves parallelism to a viewer who is reading logs rather than a LangSmith UI — useful both in the demo and in CI failure diagnosis.
- **Step 5** is the quality gate itself. `/verify` is the DoD; without a successful rehearsal, the phase is not done.
- **Step 6** locks the timing gate as a regression test. The manual `/verify` is the live demo of the phase; the integration test is the CI guarantee that future PRs do not silently break it.
- **Step 7** is the local check before opening the PR.

## Code locations

- `src/expertview/orchestration/runner.py` (edit — dispatcher body, `make_graph()` node registration, conditional edges).
- `src/expertview/agents/llms.py` (edit — add module-level `Semaphore`, wrap or expose investigator helper).
- `src/expertview/agents/investigators/mechanical.py` (edit — add structlog start/finish events).
- `src/expertview/agents/investigators/process.py` (edit — add structlog start/finish events).
- `src/expertview/agents/investigators/supply_chain.py` (edit — add structlog start/finish events).
- `src/expertview/agents/investigators/environmental.py` (edit — add structlog start/finish events).
- `src/expertview/agents/investigators/human_factors.py` (edit — add structlog start/finish events).
- `tests/integration/test_parallel_fanout.py` (new — timing-based regression test).

## Connections

**Upstream**:

- All four Phase 3 domain bundles (Tasks 1–4) — their factories are imported here.
- Phase 2's mechanical bundle — its node is now one of five rather than the sole investigator.
- Phase 2's synthesizer — unchanged; it reads merged `findings` from state. The `operator.add` reducer on `ExpertViewState.findings` does the merging automatically.
- Phase 1's `agents/llms.py` — extended here with the semaphore; the existing client factories are not modified.
- Phase 1's structlog setup — used directly; no config changes.
- LangGraph's `Send` API — the conditional-edge pattern for dynamic fan-out.

**Downstream**:

- Phase 4 will modify the dispatcher again to add a conditional edge that targets a sub-investigator node when a spawning predicate fires. The dispatcher shape established here (a function that returns a list of `Send` objects) is what Phase 4 extends.
- Phase 6's UI will read from the merged state and the LangSmith trace — both produced by this task's wiring.
- Phase 7's retry/backoff wrapper will likely sit alongside the semaphore in `agents/llms.py` (both are rate-limit-domain concerns); leaving the semaphore self-contained makes that future addition non-conflicting.

## Parallelism rationale

- This task is **sequential by necessity**: it edits `orchestration/runner.py` and `agents/llms.py`, both of which are shared across the system. It also touches all five investigator files for the structlog events. The four domain tasks could not have done these edits without conflicting.
- The final-merge pinch point is intentional: Tasks 1–4 prove they each work in isolation; Task 5 proves they all work together.

## Risks / constraints / assumptions

- **Constraint**: LLM clients live only in `agents/llms.py` ([CLAUDE.md architecture rules](../../../CLAUDE.md)). The semaphore lives here too because it is a property of the client, not of the orchestration layer.
- **Constraint**: nodes are pure async `(State) -> dict` functions. The structlog events are side effects in the loose sense; they are permitted because [architecture.md §5](../../architecture.md) explicitly allows "explicit LangSmith spans" — structlog events are the application-side equivalent and have always been part of the planned observability surface ([build_plan.md §Phase 3](../../build_plan.md)).
- **Risk — silent sequentialization**: the dispatcher returns `Send` objects but a misconfigured conditional edge collapses the fan-out to sequential. The timing-based integration test (step 6) is the catch. **The `/verify` quality gate must include a wall-time assertion**, not just a "did it produce a report" check.
- **Risk — wrong semaphore scope**: if the synthesizer accidentally goes through the same semaphore as the investigators, the throttle applies to a non-parallel call and adds no value while complicating the code path. Mitigation: the semaphore is associated with the *investigator client*, not the *synthesizer client*. The synthesizer's `ChatOpenAI` instance does not acquire it.
- **Risk — first-run embedding cost**: on a clean checkout, the first `/verify` run embeds five corpora from scratch via the local `BAAI/bge-small-en-v1.5` model. This is CPU-bound and noisy on the wall-time assertion. Mitigation: the test setup primes each store's cache before the timing assertion runs; the manual rehearsal accepts that the *first* run will be slow and the *second* run is the gate.
- **Risk — `Send` API semantics changed in a LangGraph version**: confirm the LangGraph version pinned in `pyproject.toml` matches the docs the executing agent references. If `Send` has been renamed or the conditional-edge pattern has shifted, surface it as a Phase 3 finding and update [decisions.md](../../decisions.md) accordingly.
- **Risk — OpenRouter free-tier limits during a real `/verify` run**: even with the semaphore at 5, five concurrent investigator calls can trigger upstream-provider rate limits (different upstreams behind Owl Alpha may have different caps). Mitigation: the semaphore reduces but does not eliminate this risk. If `/verify` hits 429s, lower the semaphore to 3 (so two investigators queue) and document the empirical value in the PR description. Retry/backoff is Phase 7's job, not this task's.
- **Risk — structlog touches across 5 files inflates the PR**: this is a deliberate cross-cutting edit. Mitigation: the structlog change per file is two lines (start + finish events). The PR description should call out that the 5 investigator edits are mechanical and identical except for the `domain=` label.
- **Assumption**: Phase 2's synthesizer prompt is robust enough to consume findings from five domains without modification. If `/verify` shows the synthesizer truncating, missing citations from some domains, or treating findings inconsistently, that is a *prompt* iteration concern (edit `prompts/synthesizer/default.md`), not a graph-wiring concern. Note the iteration but do not let it block the phase gate — citation coverage from at least three domains is sufficient for the gate.
- **Assumption**: the four corpora authored in Tasks 1–4 already passed user-curation. If `/verify` produces incoherent findings from a specific domain, this task surfaces the issue but does not fix it — fix lands as a follow-up PR against the relevant domain bundle.

## Definition of done

- `dispatcher` in `orchestration/runner.py` emits five `Send(...)` calls and the conditional edge routes them to the five investigator nodes.
- `make_graph()` registers all five investigator nodes by their domain names and wires each to the synthesizer.
- `agents/llms.py` has a module-level `asyncio.Semaphore(5)` scoped to the investigator client; the synthesizer client does not pass through it.
- All five investigator node functions emit `investigator.start` and `investigator.finish` structlog events with timestamps and `domain` tags.
- `tests/integration/test_parallel_fanout.py` exists and passes; it asserts both the timing characteristic (parallel, not sequential) and the merged-state shape (`findings` from all five domains).
- Manual `/verify` against `data/incidents/cnc_out_of_tolerance.yaml` succeeds:
  - A coherent multi-domain `CausalReport` is printed with citations from at least three domains.
  - The LangSmith trace shows five investigator spans overlapping in time.
  - The structlog log shows interleaved `investigator.start` events.
  - Total wall time satisfies the documented threshold (rough rule: `< 1.5× max(investigator span time)`).
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/phase-3-wiring` per [branching_strategy.md §5](../../branching_strategy.md). PR description:
  - Notes that the structlog edits to the five investigator files are mechanical and cross-cutting.
  - Records the empirical wall-time threshold observed during rehearsal.
  - Records the semaphore cap used (5 by default; lower if 429s were observed).
  - Includes a link or screenshot of the LangSmith trace showing the five overlapping spans.
- Once merged, tag `v0.4.0-demo` per [branching_strategy.md §8](../../branching_strategy.md). Phase 4 (dynamic sub-investigation) is unblocked.
