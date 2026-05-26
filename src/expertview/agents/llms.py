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
