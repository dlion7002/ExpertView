"""Provider-key smoke tests for the Task 4 LLM factory.

These tests intentionally hit live provider endpoints only when the matching
environment variables are already present. Fresh clones without keys should
skip cleanly.
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


def _require_synthesizer_selector(expected: str) -> None:
    selected = os.environ.get(llms.SYNTHESIZER_MODEL_ENV)
    if selected != expected:
        pytest.skip(f"{llms.SYNTHESIZER_MODEL_ENV} is not set to {expected}")


def test_nvidia_embeddings_round_trip() -> None:
    _require_env(llms.NVIDIA_API_KEY_ENV)

    embeddings = llms.create_embeddings()
    vector = embeddings.embed_query("hydraulic cylinder bearing anomaly")

    assert isinstance(vector, list)
    assert vector
    assert all(isinstance(value, float) for value in vector[:8])


@pytest.mark.asyncio
async def test_nvidia_investigator_llm_round_trip() -> None:
    _require_env(llms.NVIDIA_API_KEY_ENV)

    model = llms.create_investigator_llm(max_completion_tokens=1)
    response = await model.ainvoke(_ONE_TOKEN_PROMPT)

    assert str(response.content).strip()


@pytest.mark.asyncio
async def test_deepseek_synthesizer_round_trip_when_selected() -> None:
    _require_env(llms.NVIDIA_API_KEY_ENV)
    _require_synthesizer_selector(llms.SYNTHESIZER_DEEPSEEK_R1)

    model = llms.create_synthesizer_llm(max_tokens=1)
    response = await model.ainvoke(_ONE_TOKEN_PROMPT)

    assert str(response.content).strip()


@pytest.mark.asyncio
async def test_opus_synthesizer_round_trip_when_selected() -> None:
    _require_env(llms.ANTHROPIC_API_KEY_ENV)
    _require_synthesizer_selector(llms.SYNTHESIZER_OPUS_4_7)

    model = llms.create_synthesizer_llm(max_tokens=1)
    response = await model.ainvoke(_ONE_TOKEN_PROMPT)

    assert str(response.content).strip()
