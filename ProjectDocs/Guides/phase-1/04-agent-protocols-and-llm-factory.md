# Agent Protocols And LLM Factory

## Purpose

This guide explains the Phase 1 agent boundary and provider factory. The agent protocols describe what future investigators and synthesizers must do. The LLM factory is the only implemented place where provider clients, embeddings, and rerankers are constructed.

## Flow Summary

1. Future code will receive an `Incident` and prior `Finding` objects.
2. Concrete investigators will implement `Investigator.investigate()` and return `list[Finding]`.
3. The future synthesizer will implement `Synthesizer.converge()` and return a `CausalReport`.
4. Any code needing model clients calls constructors in `agents/llms.py`.
5. The constructors read real keys from `os.environ`.
6. `EXPERTVIEW_SYNTH_MODEL` selects the synthesizer model — holds an OpenRouter model ID directly (default `deepseek/deepseek-v4-flash:free` for build; e.g. `anthropic/claude-opus-4.7` for demo).
7. Integration tests run live provider round trips only when matching env vars are set.

## Relevant Files

- `src/expertview/agents/base.py`: `Investigator` and `Synthesizer` protocols.
- `src/expertview/agents/llms.py`: provider factory and model constants.
- `.env.example`: documents the env vars consumed by the factory.
- `src/expertview/evidence/models.py`: owns all protocol input/output models.
- `tests/integration/test_provider_keys.py`: env-gated live provider checks.

## Step 1 - Public Agent Protocols

### Location

`src/expertview/agents/base.py`

### Code

```python
"""Public agent protocols for investigators and synthesizers."""

from typing import Protocol

from expertview.evidence.models import CausalReport, Finding, Hypothesis, Incident


class Investigator(Protocol):
    domain: str

    async def investigate(
        self,
        incident: Incident,
        prior_findings: list[Finding],
    ) -> list[Finding]: ...


class Synthesizer(Protocol):
    async def converge(
        self,
        hypotheses: list[Hypothesis],
        findings: list[Finding],
    ) -> CausalReport: ...
```

### What it does

The protocols define the public behavior expected from future concrete agents.

An `Investigator` has a `domain` and asynchronously turns an `Incident` plus prior findings into new findings.

A `Synthesizer` asynchronously turns hypotheses and findings into a final causal report.

### What it receives or depends on

- Pydantic models from `evidence/models.py`.
- `typing.Protocol` for structural typing.

### What it produces or changes

This file produces type contracts only. It does not instantiate clients, run prompts, query RAG, or change state.

### What it connects to

- Future `agents/investigators/*.py` files should satisfy `Investigator`.
- Future `agents/synthesizer.py` should satisfy `Synthesizer`.
- `orchestration/runner.py` will eventually wire concrete nodes that use these behaviors.

### Why it matters

The protocols keep the agent layer reusable. They also clarify that cross-agent data is pydantic model data, not raw dicts.

## Step 2 - Provider And Retrieval Client Factory

### Location

`src/expertview/agents/llms.py`

### Code

```python
"""Provider factory for ExpertView LLM and embedding clients.

This module is the only legal construction site for LLM provider clients.
Callers are responsible for loading environment variables before calling
these constructors; this module reads `os.environ` directly and never loads
`.env` files (`tests/conftest.py` is the sanctioned test-process loader).

LLMs are routed through OpenRouter via the OpenAI-compatible API surface,
so every model (free open-weight for build, paid frontier for demo) is
reachable through a single `ChatOpenAI` client and a single
`OPENROUTER_API_KEY`. Investigators run on `openrouter/owl-alpha` (free,
1M context, agentic). The synthesizer model is selectable at runtime via
`EXPERTVIEW_SYNTH_MODEL`, holding an OpenRouter model ID directly
(default `deepseek/deepseek-v4-flash:free` for build,
`anthropic/claude-opus-4.7` or similar at demo time).

Embeddings run locally via `sentence-transformers` (`BAAI/bge-small-en-v1.5`)
to keep the OpenRouter credit unspent and to remove the network dependency
from RAG ingest.
"""

import os
from typing import Final

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

OPENROUTER_API_KEY_ENV: Final = "OPENROUTER_API_KEY"
SYNTHESIZER_MODEL_ENV: Final = "EXPERTVIEW_SYNTH_MODEL"

OPENROUTER_BASE_URL: Final = "https://openrouter.ai/api/v1"

INVESTIGATOR_MODEL_ID: Final = "openrouter/owl-alpha"
DEFAULT_SYNTHESIZER_MODEL_ID: Final = "deepseek/deepseek-v4-flash:free"

EMBEDDING_MODEL_NAME: Final = "BAAI/bge-small-en-v1.5"


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"{name} is required to construct this provider client.")
    return value


def _selected_synthesizer_model() -> str:
    selected = os.environ.get(SYNTHESIZER_MODEL_ENV, DEFAULT_SYNTHESIZER_MODEL_ID).strip()
    if not selected:
        raise ValueError(f"{SYNTHESIZER_MODEL_ENV} must be a non-empty OpenRouter model ID.")
    return selected


def create_investigator_llm(
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    return ChatOpenAI(
        model=INVESTIGATOR_MODEL_ID,
        base_url=OPENROUTER_BASE_URL,
        api_key=_required_env(OPENROUTER_API_KEY_ENV),
        temperature=temperature,
        max_tokens=max_tokens,
    )


def create_synthesizer_llm(
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    return ChatOpenAI(
        model=_selected_synthesizer_model(),
        base_url=OPENROUTER_BASE_URL,
        api_key=_required_env(OPENROUTER_API_KEY_ENV),
        temperature=temperature,
        max_tokens=max_tokens,
    )


def create_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        encode_kwargs={"normalize_embeddings": True},
    )
```

### What it does

This module centralizes provider construction.

`_required_env()` reads an env var and fails loudly if it is absent or blank. It names the missing variable but never logs or returns secret values anywhere except to the provider constructor.

`_selected_synthesizer_model()` reads `EXPERTVIEW_SYNTH_MODEL`, defaults to `deepseek/deepseek-v4-flash:free`, and rejects empty values. The selector holds an OpenRouter model ID directly — no enum, no whitelist.

`create_investigator_llm()` returns a `ChatOpenAI` client pointed at OpenRouter, hard-pinned to `openrouter/owl-alpha` (free, agentic foundation model).

`create_synthesizer_llm()` returns a `ChatOpenAI` client pointed at OpenRouter, parameterized by whatever ID `EXPERTVIEW_SYNTH_MODEL` selects (free build model by default; a paid frontier model at demo time).

`create_embeddings()` returns a `HuggingFaceEmbeddings` instance backed by `BAAI/bge-small-en-v1.5` via `sentence-transformers`. No API key, no network call — first construction downloads the ~130 MB model into `~/.cache/huggingface/` and caches it; subsequent calls are instant.

### What it receives or depends on

- `os.environ`: runtime environment variables.
- `.env.example`: documents the expected variables, but this module does not load `.env`.
- `langchain_openai`: `ChatOpenAI` (configured with `base_url="https://openrouter.ai/api/v1"`).
- `langchain_huggingface`: `HuggingFaceEmbeddings` (backed by `sentence-transformers`).

### What it produces or changes

It produces provider client objects. It does not call the models by itself and does not mutate project state.

### What it connects to

- Future investigator nodes: call `create_investigator_llm()`.
- Future synthesizer node: call `create_synthesizer_llm()`.
- Future RAG domain loaders: call `create_embeddings()` and pass the result into `InMemoryKnowledgeStore`.
- `tests/integration/test_provider_keys.py`: calls these constructors and performs live smoke checks (embeddings always runs locally; LLM round-trips skip if `OPENROUTER_API_KEY` is absent).

### Why it matters

This file is the security and architecture choke point for model clients. If a provider endpoint or model ID changes, this should be the only source file that needs an update.

## Step 3 - Provider-Key Integration Tests

### Location

`tests/integration/test_provider_keys.py`

### Code

```python
"""Provider round-trip smoke tests for the LLM factory.

The investigator and synthesizer tests hit OpenRouter and skip cleanly when
`OPENROUTER_API_KEY` is missing. The embedding test runs unconditionally
because `BAAI/bge-small-en-v1.5` ships locally via `sentence-transformers`
(first run downloads ~130 MB into the HuggingFace cache; subsequent runs
are instant).
"""

import os

import pytest

from expertview.agents import llms

_ONE_TOKEN_PROMPT = "Reply with exactly one word: OK"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        pytest.skip(f"{name} is not set")
    return value


def test_local_embeddings_round_trip() -> None:
    embeddings = llms.create_embeddings()
    vector = embeddings.embed_query("hydraulic cylinder bearing anomaly")

    assert isinstance(vector, list)
    assert vector
    assert all(isinstance(value, float) for value in vector[:8])


@pytest.mark.asyncio
async def test_openrouter_investigator_round_trip() -> None:
    _require_env(llms.OPENROUTER_API_KEY_ENV)

    model = llms.create_investigator_llm(max_tokens=1)
    response = await model.ainvoke(_ONE_TOKEN_PROMPT)

    assert str(response.content).strip()


@pytest.mark.asyncio
async def test_openrouter_synthesizer_round_trip() -> None:
    _require_env(llms.OPENROUTER_API_KEY_ENV)

    model = llms.create_synthesizer_llm(max_tokens=1)
    response = await model.ainvoke(_ONE_TOKEN_PROMPT)

    assert str(response.content).strip()
```

### What it does

The tests verify live provider connectivity, but only when the required env var is already present.

- Local embeddings test always runs; checks that a query produces a non-empty float vector via `BAAI/bge-small-en-v1.5`.
- OpenRouter investigator test checks that the investigator model path (`openrouter/owl-alpha`) can answer; skips if `OPENROUTER_API_KEY` is absent.
- OpenRouter synthesizer test checks that whatever `EXPERTVIEW_SYNTH_MODEL` selects (default `deepseek/deepseek-v4-flash:free`) can answer; skips if `OPENROUTER_API_KEY` is absent.

### What it receives or depends on

- Real env vars in the test process.
- Live provider access.
- `pytest-asyncio` for async LLM tests.

### What it produces or changes

It produces test results only. It does not write files or state. When keys are missing, it skips rather than failing.

### What it connects to

- `agents/llms.py`: tests the public constructors.
- `.env.example`: documents how to supply the required variables locally.
- Phase 1 quality gate: provider-key round trips are part of the intended verification story.

### Why it matters

Provider auth and model IDs are high-risk demo failures. These tests make that risk visible early without making fresh clones fail by default.

## Where To Look Next

After the agent and provider boundaries, the next flow is graph construction:

- `05-orchestration-runner-and-quality-gates.md`
- `src/expertview/orchestration/runner.py`
