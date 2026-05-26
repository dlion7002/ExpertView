# Bootstrap And Layout

## Purpose

This guide covers the Phase 1 bootstrap: how the repository becomes an importable uv-managed Python package, where configuration lives, which environment variables start provider and tracing flows, and how the placeholder data/test layout supports later phases.

## Flow Summary

1. `pyproject.toml` defines the package, dependencies, script entry point, ruff rules, and pytest discovery.
2. `.python-version` pins the uv-managed interpreter target.
3. `.env.example` documents the provider and tracing variables consumed later by `agents/llms.py` and `orchestration/runner.py`.
4. `.gitignore` prevents secrets and local artifacts from entering version control.
5. `src/expertview/` package markers make the architecture folders importable.
6. `data/domains/*/.gitkeep` and `data/incidents/.gitkeep` reserve the future corpus and incident layout.
7. `tests/unit/test_package_smoke.py` keeps `uv run pytest` green even before feature tests exist.

## Relevant Files

- `pyproject.toml`: uv package metadata, dependencies, script entry, ruff config, pytest config.
- `.python-version`: Python version target for uv.
- `.env.example`: documented environment variable contract.
- `.gitignore`: local and secret hygiene.
- `src/expertview/**/__init__.py`: package skeleton and import boundaries.
- `data/domains/*/.gitkeep`: domain corpus placeholders.
- `data/incidents/.gitkeep`: incident scenario placeholder.
- `tests/unit/test_package_smoke.py`: import smoke test.

## Step 1 - Package And Tool Configuration

### Location

`pyproject.toml`

### Code

```toml
[project]
name = "expertview"
version = "0.1.0"
description = "Multi-agent root-cause-analysis system for industrial manufacturing incidents. LangGraph + OpenRouter (one gateway, free open-weight for build, paid frontier for demo) + local embeddings + domain-specific RAG."
readme = "README.md"
requires-python = ">=3.11"
authors = [
    { name = "Jacobo D'león" },
]
license = { text = "MIT" }
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "langgraph>=0.2",
    "langchain-core>=0.3",
    "langchain-openai>=0.2",
    "langchain-huggingface>=0.1",
    "langchain-community>=0.3",
    "sentence-transformers>=3.0",
    "langsmith>=0.1",
    "pydantic>=2.7",
    "structlog>=24.1",
    "rich>=13.7",
]

[project.scripts]
expertview = "expertview.cli:main"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "python-dotenv>=1.0",
    "ruff>=0.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/expertview"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",
    "F",
    "I",
    "B",
    "UP",
    "N",
    "RUF",
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra"
```

### What it does

This file turns the repository into a buildable package named `expertview`. It declares the Phase 1 dependency stack: LangGraph, LangChain (`langchain-core` + `langchain-openai` for the OpenRouter-routed LLM client + `langchain-huggingface` for local embeddings + `langchain-community` for retrievers), `sentence-transformers` (backs `HuggingFaceEmbeddings` with `BAAI/bge-small-en-v1.5`), LangSmith, pydantic, structlog, rich, pytest, pytest-asyncio, `python-dotenv` (dev, loads `.env` for tests), and ruff.

The `[project.scripts]` entry points at `expertview.cli:main`, even though the CLI is not implemented in Phase 1. That keeps the intended public command path visible for later phases.

The ruff and pytest sections define the verification surface used by Phase 1 tasks and future CI.

### What it connects to

- `src/expertview/`: packaged by hatchling.
- `tests/`: discovered by pytest.
- `src/expertview/agents/llms.py`: imports provider classes provided by the declared LangChain dependencies.
- `src/expertview/orchestration/runner.py`: imports LangGraph from the declared dependencies.

### Why it matters

Every later flow assumes `uv run ...` can import `expertview` and resolve the dependencies. If this file is wrong, the rest of Phase 1 cannot be taught, tested, or executed.

## Step 2 - Python Version Pin

### Location

`.python-version`

### Code

```text
3.12
```

### What it does

This tells uv which local Python version to use for the project environment.

### What it connects to

- `pyproject.toml` allows Python `>=3.11`, while this local pin selects `3.12`.
- All `uv run ...` verification commands use this environment.

### Why it matters

It keeps local runs consistent and makes ruff's `target-version = "py312"` match the developer environment.

## Step 3 - Environment Variable Contract

### Location

`.env.example`

### Code

```dotenv
# ExpertView environment template.
# Copy this file to `.env` (which is git-ignored) and fill in real values locally.
# Never commit `.env`. Never put real keys in this template.

# OpenRouter API key. Used by ChatOpenAI (LangChain's OpenAI-compatible client)
# pointed at https://openrouter.ai/api/v1 for both investigator and synthesizer
# calls. One key covers free open-weight models (build) and paid frontier models
# (demo).
OPENROUTER_API_KEY=sk-or-v1-REPLACE_ME

# LangSmith API key. Enables span capture for every LangGraph node and LLM call.
# Trace replay from a saved successful run is the venue-night demo fallback.
LANGSMITH_API_KEY=lsv2_REPLACE_ME

# LangSmith project name. All traces from this checkout are grouped under it
# in the LangSmith dashboard.
LANGSMITH_PROJECT=expertview-dev

# Synthesizer model selector, read by src/expertview/agents/llms.py.
# Holds an OpenRouter model ID directly. Common values (May 2026 free catalog):
#   `deepseek/deepseek-v4-flash:free`       — free thinking model; build default.
#   `nvidia/nemotron-3-super:free`          — 120B MoE alternative if DeepSeek throttles.
#   `anthropic/claude-opus-4.7`             — paid frontier for the demo / final rehearsal.
# Embeddings run locally via `BAAI/bge-small-en-v1.5` and need no env var.
EXPERTVIEW_SYNTH_MODEL=deepseek/deepseek-v4-flash:free
```

### What it does

This file documents the runtime inputs that start provider and tracing flows.

`OPENROUTER_API_KEY` is the single LLM-gateway key, consumed by both `create_investigator_llm()` and `create_synthesizer_llm()` in `src/expertview/agents/llms.py` via `ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=...)`.

`EXPERTVIEW_SYNTH_MODEL` holds an OpenRouter model ID directly (e.g. `deepseek/deepseek-v4-flash:free` for build, `anthropic/claude-opus-4.7` for demo). `create_synthesizer_llm()` passes the ID through verbatim to `ChatOpenAI`.

Embeddings (`create_embeddings()`) construct `HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")` locally — no key, no network, ~130 MB one-time `sentence-transformers` download cached under `~/.cache/huggingface/`.

`LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` are consumed by `src/expertview/orchestration/runner.py` when `make_graph()` configures tracing.

### What it produces or changes

Nothing by itself. It is a template only. Runtime code reads real values from `os.environ`, not directly from this file.

### Why it matters

It is the shared contract between local setup, provider factory code, graph tracing, and integration tests. Never put real keys here.

## Step 4 - Ignored Local Artifacts

### Location

`.gitignore`

### Code

```gitignore
# Secrets and local environment
.env
.env.*
!.env.example
.venv/
venv/

# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/

# Logs and local runtime artifacts
*.log
*.sqlite
*.db

# Demo data and model artifacts that should not be committed accidentally
data/generated/
data/cache/
models/
checkpoints/
*.ckpt
*.safetensors

# OS and editor noise
.DS_Store
Thumbs.db
.vscode/
!.vscode/extensions.json
```

### What it does

This prevents local secrets, virtual environments, caches, generated demo data, model checkpoints, and editor noise from being committed.

### What it connects to

- `.env.example` is explicitly allowed.
- `.env` and `.env.*` are ignored.
- `.venv/`, `.pytest_cache/`, and `.ruff_cache/` are expected local products of uv, pytest, and ruff.

### Why it matters

Phase 1 introduces provider-key tests and future demo data paths. This file keeps secrets and heavy local artifacts out of version control.

## Step 5 - Package And Data Skeleton

### Location

`src/expertview/` and `data/`

### Code

```text
src/expertview/
  __init__.py
  agents/
    __init__.py
    base.py
    llms.py
    investigators/
      __init__.py
  evidence/
    __init__.py
    models.py
  orchestration/
    __init__.py
    runner.py
    state.py
  prompts/
    __init__.py
    investigator/
      __init__.py
    synthesizer/
      __init__.py
  rag/
    __init__.py
    base.py
    inmemory.py
    domains/
      __init__.py

data/
  domains/
    environmental/.gitkeep
    human_factors/.gitkeep
    mechanical/.gitkeep
    process/.gitkeep
    supply_chain/.gitkeep
  incidents/.gitkeep
```

### What it does

The package skeleton encodes the architecture boundaries. Empty `__init__.py` files make folders importable. `.gitkeep` files reserve data folders before real corpora or incidents exist.

### What it connects to

- `evidence/` owns cross-agent models.
- `orchestration/` owns LangGraph state and graph construction.
- `rag/` owns domain knowledge store contracts and implementations.
- `agents/` owns agent protocols and provider client factories.
- `prompts/` is reserved for later versioned prompt templates.
- `data/domains/` and `data/incidents/` are consumed in later phases.

### Why it matters

The structure is part of the system design. Later code should extend the existing boundaries instead of inventing new crossing points.

## Step 6 - Bootstrap Smoke Test

### Location

`tests/unit/test_package_smoke.py`

### Code

```python
"""Bootstrap smoke test: the `expertview` package must be importable.

Replaced by real coverage in Task 2 (schema round-trips) and beyond. Kept now so
`uv run pytest` exits 0 — `pytest` exits 5 when zero tests are collected, which
fails CI under `set -e`.
"""

import expertview


def test_package_importable() -> None:
    assert expertview is not None
```

### What it does

This verifies that the package can be imported. It also prevents pytest from exiting with "no tests collected" during the earliest skeleton stage.

### What it connects to

- `src/expertview/__init__.py`: must exist and be importable.
- `pyproject.toml`: must package `src/expertview` correctly.

### Why it matters

It catches packaging regressions before deeper Phase 1 tests run.

## Where To Look Next

After bootstrap, the project flow moves into the cross-agent data contract:

- `02-evidence-models-and-state.md`
- `src/expertview/evidence/models.py`
- `src/expertview/orchestration/state.py`
