# Task 4 — Agents Skeleton + LLM Provider Factory

> **Branch suggestion**: `feature/agents-llms`
> **Parallelism**: **Parallelizable with Tasks 3 and 5.**
> **Depends on**: Task 2 (`evidence/models.py` provides `Incident`, `Finding`, `Hypothesis`, `CausalReport`).

## Purpose

Define the `Investigator` and `Synthesizer` protocols that every agent in the project must satisfy, and ship the single LLM provider factory (`agents/llms.py`) that constructs `ChatNVIDIA` and `ChatAnthropic` clients. The factory honors `EXPERTVIEW_SYNTH_MODEL` so the synthesizer can be swapped between DeepSeek-R1 (build) and Opus 4.7 (demo) by env var alone.

Bundled into the same task: the **provider-key round-trip integration test** that verifies real connectivity to NVIDIA NIM (NV-Embed-v2 + Llama 3.3 70B) and, optionally and env-gated, to DeepSeek-R1 / Opus 4.7. This is the Phase 1 quality-gate item that proves the keys + the factory actually work end-to-end.

## Why it matters

- [architecture.md §5](../../architecture.md) and [CLAUDE.md architecture rules](../../../CLAUDE.md) make `agents/llms.py` the **single legal site** for instantiating any LLM client. This task creates that single site so the rule is enforceable from day one rather than violated and retrofitted later.
- The protocol pair (`Investigator`, `Synthesizer`) is what makes the Path B reusability story in [vision.md §6](../../vision.md) credible — *"'Investigator' can be relabeled 'Triage Agent' or 'Diagnostic Agent' with no structural change."*
- The multi-provider model split in [decisions.md (2026-05-25 multi-provider)](../../decisions.md) only delivers its value if the synthesizer swap is one env-var change. The factory is what realizes that swap.
- Provider keys are the demo-day failure mode that costs the most credibility if it shows up at the venue. Verifying them now, in CI-runnable form, is cheap insurance.

## Concrete steps (what to produce)

1. **Create `src/expertview/agents/base.py`** with the `Investigator` and `Synthesizer` Protocols from [architecture.md §3](../../architecture.md). Import the relevant pydantic models from `evidence/models.py`. Keep the surface minimal — Phase 2's concrete investigator and synthesizer nodes will reveal whether more methods are needed.
2. **Create `src/expertview/agents/llms.py`** as the only place in the codebase where `ChatAnthropic`, `ChatNVIDIA`, `NVIDIAEmbeddings`, and `NVIDIARerank` are constructed. The factory needs to expose, at minimum: an investigator-model constructor (Llama 3.3 70B via NIM), an embeddings constructor (NV-Embed-v2), a reranker constructor (NV-Rerank), and a synthesizer-model constructor that reads `EXPERTVIEW_SYNTH_MODEL` and dispatches to DeepSeek-R1 (default for build) or Opus 4.7 (demo). Model IDs live as named constants here — when NVIDIA rotates a NIM endpoint, this is the only file that changes ([architecture.md §9 "expected to evolve"](../../architecture.md)).
3. **Environment variable contract**: read `NVIDIA_API_KEY`, `ANTHROPIC_API_KEY`, and `EXPERTVIEW_SYNTH_MODEL` from the environment via stdlib `os.environ`. Do not load `.env` files from inside this module — that is the caller's responsibility (CLI / test harness). Fail loudly if a required key is missing when the corresponding constructor is called. **Never edit `.env`** (CLAUDE.md hard rule); never log key values; the security review skill flags any whiff of key leakage.
4. **Create `tests/integration/test_provider_keys.py`** doing one-token / one-vector round trips. Required calls (gated on `NVIDIA_API_KEY` being present and `pytest.skip` otherwise): a single embedding call against NV-Embed-v2 and a one-token completion against Llama 3.3 70B. Optional calls (additionally gated on `ANTHROPIC_API_KEY` for Opus and on having `EXPERTVIEW_SYNTH_MODEL` set for DeepSeek-R1): one-token completions to verify the synthesizer path on both providers. The point is connectivity + auth, not response quality.
5. **Skip rules**: every integration test must `pytest.skip` cleanly when its required env var is missing, so the test suite stays green on a fresh clone without keys. The provider-key tests are the only tests in Phase 1 allowed to hit the network.
6. **Run the `/security-review` skill** before opening the PR. This is mandated by [CLAUDE.md built-in skills](../../../CLAUDE.md) and [workflow.md §5](../../workflow.md) for any change touching LLM provider clients, `agents/llms.py`, or env-var reads. Address any flagged issues before merging.
7. **Verify quality gates locally**: `uv run pytest tests/integration/test_provider_keys.py` with keys set (or skipped without); `uv run ruff check .` and `uv run ruff format --check .` clean.

## What each step does

- Step 1 establishes the agent contract. Phase 2's mechanical investigator and synthesizer satisfy it; Phase 3's four additional investigators do the same. Lift-able into Path B verbatim.
- Step 2 establishes the LLM-client-construction wall. Once this file exists, any other module instantiating `ChatAnthropic` or `ChatNVIDIA` is a code-review reject.
- Step 3 keeps the secret-handling surface tight. Environment is read; nothing is logged; failures are loud but key-free.
- Step 4 is the Phase 1 quality-gate item for provider round trips. It is also the cheapest possible regression check for "did NIM rotate the model name" — if the test starts failing, the model ID constant in `agents/llms.py` needs updating.
- Step 5 makes the test suite green on a fresh clone, which preserves the "PR check is green by default" property the lightweight GitHub Flow depends on.
- Step 6 is the workflow's enforced gate for any code path that touches secrets or LLM providers. Doing it now is faster than doing it during PR review.
- Step 7 is the local quality gate.

## Code locations

- `src/expertview/agents/base.py` (new).
- `src/expertview/agents/llms.py` (new).
- `tests/integration/test_provider_keys.py` (new).

## Connections

**Upstream**:

- Imports `Incident`, `Finding`, `Hypothesis`, `CausalReport` from Task 2's `evidence/models.py` for protocol signatures.
- Project skeleton from Task 1 must exist; `.env.example` from Task 1 documents the env vars this module reads.

**Downstream**:

- Phase 2 `agents/investigators/mechanical.py` constructs its Llama 3.3 70B client by calling the factory here.
- Phase 2 `agents/synthesizer.py` constructs its synthesizer client by calling the factory here — and that call is what `EXPERTVIEW_SYNTH_MODEL` controls.
- Phase 2 `rag/domains/mechanical.py` constructs `NVIDIAEmbeddings` by calling the factory here (embeddings are passed *into* the `InMemoryKnowledgeStore` from Task 3, satisfying the architecture wall).
- Phase 3's four additional investigators do the same as the mechanical one.
- Phase 7's retry/backoff wrapper for `ChatNVIDIA` and `ChatAnthropic` lives inside this file.

## Parallelism rationale

- Tasks 3, 4, and 5 import only from `evidence/` (and stdlib / third-party libraries). They do not import from each other.
- The architecture rule "module boundaries are walls" ([architecture.md §5](../../architecture.md)) is what makes the fan-out safe — `agents/` does not reach into `rag/` or `orchestration/`.
- A second agent can take Task 3 and a third can take Task 5 at the same time on separate `feature/*` branches. Merge order does not matter among Tasks 3/4/5.

## Risks / constraints / assumptions

- **Hard rule**: never edit `.env` ([CLAUDE.md hard rules](../../../CLAUDE.md)). This task reads from `os.environ` only; the user manages `.env` outside this codebase.
- **Hard rule**: never log API key values. Error messages on missing keys should name the env var, not its (absent) value.
- **Architecture rule**: `agents/llms.py` is the only file in the codebase that may construct `ChatAnthropic`, `ChatNVIDIA`, `NVIDIAEmbeddings`, or `NVIDIARerank`. Other agent files import the factory; they do not import the LangChain provider classes directly.
- **Architecture rule**: `evidence/` and `prompts/` are LLM-provider-pure ([architecture.md §5](../../architecture.md)). This factory must not be imported into either of those packages.
- **Risk**: silent reliance on a default model ID that NIM later rotates. Mitigation: model IDs are named constants at the top of the file so a model rotation is one-line.
- **Risk**: integration test hitting the network during CI and either burning quota or failing because CI has no keys. Mitigation is step 5 — `pytest.skip` when keys are absent. CI environments should not set `NVIDIA_API_KEY` unless the user explicitly wants the round-trip running there.
- **Risk**: prompt-injection or key leakage via error messages that include LLM response bodies. The `/security-review` skill (step 6) is the specific defense.
- **Assumption**: the user has at least `NVIDIA_API_KEY` available for the local test run. `ANTHROPIC_API_KEY` is optional during build per [decisions.md (2026-05-25 deferral of Anthropic spend cap)](../../decisions.md) — the Opus 4.7 round-trip is genuinely env-gated, not a required test.
- **Assumption**: the `langchain-anthropic` and `langchain-nvidia-ai-endpoints` versions pinned in Task 1's `pyproject.toml` are mutually compatible. If integration tests reveal incompatibility, log the resolution in [decisions.md](../../decisions.md).

## Definition of done

- `Investigator` and `Synthesizer` protocols exist in `agents/base.py` and match [architecture.md §3](../../architecture.md).
- `agents/llms.py` is the only file constructing LLM client classes; it exposes investigator-model, embeddings, reranker, and `EXPERTVIEW_SYNTH_MODEL`-driven synthesizer constructors.
- `tests/integration/test_provider_keys.py` round-trips against the required NIM endpoints when keys are present; skips cleanly when they are not.
- `/security-review` skill has been run and any findings addressed.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- No LLM client classes are constructed anywhere outside `agents/llms.py`.
- PR opened on `feature/agents-llms` per [branching_strategy.md §5](../../branching_strategy.md); the PR description explicitly notes `/security-review` was run.
