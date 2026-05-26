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
