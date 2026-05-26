# Task 4 — Synthesizer Node + Prompt

> **Branch suggestion**: `feature/synthesizer-node`
> **Parallelism**: **Parallelizable with Tasks 2 and 3.**
> **Depends on**: Phase 1 (uses `evidence/models`, `agents/base`, `agents/llms`, `orchestration/state`). Does **not** depend on Task 3 — develops against fixture `Finding`s.

## Purpose

Build the terminal LangGraph node: the synthesizer. It reads `findings` from `ExpertViewState`, calls the synthesizer LLM (whatever `EXPERTVIEW_SYNTH_MODEL` selects via `create_synthesizer_llm()`, defaulting to `deepseek/deepseek-v4-flash:free` during build), and returns `{"causal_report": CausalReport(...)}` as its state patch. Ship the versioned prompt file alongside the node.

The Phase 2 synthesizer is minimal — "single hypothesis from a single finding" per [build_plan.md §Phase 2](../../build_plan.md). Phase 5 (evidence-weighted convergence) extends this to confidence scoring and causal linking across many findings; do **not** preempt that work here.

## Why it matters

- The synthesizer is the **sole reader of the final state snapshot** ([CLAUDE.md architecture rules](../../../CLAUDE.md)). Its purity matters: no disk writes, no spawning, no state writes outside the returned patch.
- The synthesizer is the only node whose model identity swaps at demo time (`openrouter/owl-alpha` stays free; the synthesizer flips from `deepseek/deepseek-v4-flash:free` to a paid frontier ID via env). Phase 7's rehearsal exercises that swap — Phase 2 must produce a coherent report against the *free* build synthesizer so the swap path is testable.
- The CausalReport this node emits is what the demo audience reads. If its shape is right, the Phase 6 UI just renders it; if wrong, the UI has to compensate.

## Concrete steps (what to produce)

1. **Create `src/expertview/prompts/synthesizer/default.md`** — the versioned prompt file. Required behavior elicited:
   - Role framing for an RCA synthesizer that reads investigator findings and produces a single, coherent causal report.
   - Instruction to preserve and surface every citation present in the input findings (citations are the demo's credibility).
   - Output contract: structured JSON parseable into `CausalReport` (`incident_id`, `top_hypotheses` [list of `Hypothesis`], `causal_chain` [list of `CausalLink`], `confidence_summary` [string]). Even with a single finding, the report must produce at least one `Hypothesis` whose `supporting_findings` references the input finding.
2. **Create `src/expertview/agents/synthesizer.py`** exporting a node factory. Suggested shape:
   - `def make_synthesizer_node(llm: ChatOpenAI) -> Callable[[ExpertViewState], Awaitable[dict]]:`
   - The returned async node:
     - Reads `incident: Incident` and `findings: list[Finding]` from state.
     - Loads the prompt template from `prompts/synthesizer/default.md` and renders it with the incident + findings.
     - Awaits the LLM call.
     - Parses the response into a `CausalReport` via pydantic (`CausalReport.model_validate(...)` against the LLM-returned JSON) — validate at the boundary.
     - Returns `{"causal_report": report}`.
   - No state writes outside the returned patch; no disk writes; no spawning logic ([CLAUDE.md architecture rules](../../../CLAUDE.md)).
3. **Add a unit test** in `tests/unit/test_synthesizer.py` that:
   - Builds the node with a fake LLM (returns a hard-coded JSON string that parses into a `CausalReport`).
   - Invokes the node against a stub `ExpertViewState` carrying one `Incident` and two fixture `Finding`s (each with citations).
   - Asserts the returned patch is `{"causal_report": <CausalReport>}`, that `incident_id` matches, that `top_hypotheses` is non-empty, and that citations from the input findings flow through into at least one `Hypothesis.supporting_findings` entry.
4. **Verify locally**: `uv run pytest tests/unit/test_synthesizer.py` green; `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- **Step 1** captures the synthesizer's job in a versioned file. Keeping the citation-preservation requirement in the prompt is what makes the demo's "citation back to the corpus" gate achievable end-to-end.
- **Step 2** establishes the synthesizer node shape — pure, factory-built, terminal. Phase 5 will extend the logic (confidence weighting, causal chains across findings) without changing this shape.
- **Step 3** locks the contract without paying for an LLM call. Real-model behavior is exercised in Task 5's `/verify`.
- **Step 4** is the local quality gate.

## Code locations

- `src/expertview/prompts/synthesizer/default.md` (new).
- `src/expertview/agents/synthesizer.py` (new).
- `tests/unit/test_synthesizer.py` (new).

## Connections

**Upstream**:

- `evidence/models.py` — `Finding`, `Hypothesis`, `CausalLink`, `CausalReport`, `Incident`.
- `agents/base.py` — `Synthesizer` protocol (the node's behavior is compatible with the protocol's `converge(...)` semantics, wrapped in a LangGraph node signature). Note: the protocol takes both `hypotheses` and `findings`; in Phase 2 there are no upstream hypotheses on state, so the node operates from findings alone and *generates* hypotheses as part of building the `CausalReport`.
- `agents/llms.py` — `create_synthesizer_llm()`. The function honors `EXPERTVIEW_SYNTH_MODEL` per [decisions.md](../../decisions.md); this node should not read that env var directly.
- `orchestration/state.py` — `ExpertViewState`.

**Downstream**:

- [[task-5-runner-cli-wiring]] constructs the synthesizer LLM via `create_synthesizer_llm()`, calls the factory here, and registers the returned function as the terminal graph node.
- Phase 5 (evidence-weighted convergence) extends the prompt and adds pre-LLM weighting via `evidence/convergence.py` — the synthesizer node signature stays stable.
- Phase 6's UI renders the `CausalReport` directly; the shape needs to be right *here*.
- Phase 7's synthesizer-swap rehearsal flips `EXPERTVIEW_SYNTH_MODEL` to a paid frontier ID and re-runs this exact prompt; transfer drift is the risk that rehearsal catches.

## Parallelism rationale

- The synthesizer consumes only the `Finding` schema and the LLM factory — both are Phase 1 artifacts. It does not depend on Task 2's loader or Task 3's investigator implementation; fixture findings substitute at unit-test time.
- Three branches with no shared editing surface among `agents/synthesizer.py`, `agents/investigators/mechanical.py`, and `rag/domains/mechanical.py`. Architecture rule from [architecture.md §5](../../architecture.md) keeps the fan-out safe.

## Risks / constraints / assumptions

- **Constraint**: prompts live as files under `src/expertview/prompts/`. Never inline ([CLAUDE.md hard rules](../../../CLAUDE.md)).
- **Constraint**: the synthesizer is side-effect-free. No state writes outside the patch, no disk writes, no spawning ([CLAUDE.md architecture rules](../../../CLAUDE.md)).
- **Constraint**: the only legal LLM construction site is `agents/llms.py`. The node receives the LLM via the factory's argument; do not call `ChatOpenAI(...)` inside the synthesizer.
- **Risk**: prompt-transfer drift between `deepseek/deepseek-v4-flash:free` (build) and a paid frontier (`anthropic/claude-opus-4.7` or similar) at demo time. Mitigation: Phase 7 explicitly rehearses the swap; the prompt should avoid model-family-specific patterns (no Claude-specific XML scaffolds, no DeepSeek-specific thinking tokens).
- **Risk**: `CausalReport` is a deeply nested model (`Hypothesis` → `Finding`; `CausalLink` → `Hypothesis | Symptom`). The LLM may emit shapes that don't validate. Mitigation: the prompt provides a concrete JSON schema example; the parser raises a clear pydantic error on validation failure; Phase 7 adds retry/backoff at the LLM-call layer if structural drift persists.
- **Risk**: citations get summarized away. Mitigation: explicit instruction in the prompt to preserve citations verbatim into `Hypothesis.supporting_findings`. Unit test asserts citation flow-through.
- **Assumption**: in Phase 2 the node receives a single `Finding` (the mechanical investigator's output). The prompt and parser must still handle multi-finding input cleanly — Phase 3 will deliver five findings concurrently and this node should not need to change to absorb that.

## Definition of done

- Prompt file exists at `src/expertview/prompts/synthesizer/default.md` and contains the citation-preservation requirement explicitly.
- `agents/synthesizer.py` exports a node factory; the returned node is an async `(ExpertViewState) -> dict` function compatible with `StateGraph.add_node(...)` and returns only `{"causal_report": CausalReport(...)}`.
- Unit test passes with fake LLM; asserts the `causal_report` patch shape, the `incident_id` match, non-empty `top_hypotheses`, and citation flow-through.
- No `ChatOpenAI(...)` or `HuggingFaceEmbeddings(...)` constructed in this module.
- No disk writes, no state writes outside the returned patch, no `os.environ` reads.
- No prompt strings inlined in `.py` files.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `feature/synthesizer-node` per [branching_strategy.md §5](../../branching_strategy.md). PR description should note that real-model behavior (citation preservation, JSON parseability under the build synthesizer) is exercised by Task 5's `/verify`, and that the paid-frontier swap is a Phase 7 rehearsal — not a Phase 2 concern.
