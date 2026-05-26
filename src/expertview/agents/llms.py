"""Provider factory for ExpertView LLM and retrieval clients.

This module is the only legal construction site for LangChain provider
clients. Callers are responsible for loading environment variables before
calling these constructors; this module reads `os.environ` directly and never
loads `.env` files.
"""

import os
from collections.abc import Sequence
from typing import Final

from langchain_anthropic import ChatAnthropic
from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings, NVIDIARerank

NVIDIA_API_KEY_ENV: Final = "NVIDIA_API_KEY"
ANTHROPIC_API_KEY_ENV: Final = "ANTHROPIC_API_KEY"
SYNTHESIZER_MODEL_ENV: Final = "EXPERTVIEW_SYNTH_MODEL"

SYNTHESIZER_DEEPSEEK_R1: Final = "deepseek-r1"
SYNTHESIZER_OPUS_4_7: Final = "opus-4-7"
SUPPORTED_SYNTHESIZER_MODELS: Final = (
    SYNTHESIZER_DEEPSEEK_R1,
    SYNTHESIZER_OPUS_4_7,
)

NVIDIA_INVESTIGATOR_MODEL_ID: Final = "meta/llama-3.3-70b-instruct"
NVIDIA_SYNTHESIZER_MODEL_ID: Final = "deepseek-ai/deepseek-r1"
NVIDIA_EMBEDDING_MODEL_ID: Final = "nvidia/nv-embed-v2"
NVIDIA_RERANKER_MODEL_ID: Final = "nvidia/nv-rerankqa-mistral-4b-v3"
ANTHROPIC_SYNTHESIZER_MODEL_ID: Final = "claude-opus-4-7"


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"{name} is required to construct this provider client.")
    return value


def _selected_synthesizer_model() -> str:
    selected = os.environ.get(SYNTHESIZER_MODEL_ENV, SYNTHESIZER_DEEPSEEK_R1).strip()
    if selected not in SUPPORTED_SYNTHESIZER_MODELS:
        supported = ", ".join(SUPPORTED_SYNTHESIZER_MODELS)
        raise ValueError(f"{SYNTHESIZER_MODEL_ENV} must be one of: {supported}.")
    return selected


def create_investigator_llm(
    *,
    temperature: float = 0.0,
    max_completion_tokens: int | None = None,
) -> ChatNVIDIA:
    return ChatNVIDIA(
        model=NVIDIA_INVESTIGATOR_MODEL_ID,
        nvidia_api_key=_required_env(NVIDIA_API_KEY_ENV),
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
    )


def create_embeddings() -> NVIDIAEmbeddings:
    return NVIDIAEmbeddings(
        model=NVIDIA_EMBEDDING_MODEL_ID,
        nvidia_api_key=_required_env(NVIDIA_API_KEY_ENV),
    )


def create_reranker(*, top_n: int = 5) -> NVIDIARerank:
    return NVIDIARerank(
        model=NVIDIA_RERANKER_MODEL_ID,
        nvidia_api_key=_required_env(NVIDIA_API_KEY_ENV),
        top_n=top_n,
    )


def create_synthesizer_llm(
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> ChatNVIDIA | ChatAnthropic:
    selected = _selected_synthesizer_model()
    if selected == SYNTHESIZER_DEEPSEEK_R1:
        return ChatNVIDIA(
            model=NVIDIA_SYNTHESIZER_MODEL_ID,
            nvidia_api_key=_required_env(NVIDIA_API_KEY_ENV),
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )

    return ChatAnthropic(
        model_name=ANTHROPIC_SYNTHESIZER_MODEL_ID,
        api_key=_required_env(ANTHROPIC_API_KEY_ENV),
        temperature=temperature,
        max_tokens_to_sample=max_tokens,
    )


def supported_synthesizer_models() -> Sequence[str]:
    return SUPPORTED_SYNTHESIZER_MODELS
