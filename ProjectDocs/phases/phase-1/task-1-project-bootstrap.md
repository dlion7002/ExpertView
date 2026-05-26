# Task 1 — Project Bootstrap

> **Branch suggestion**: `chore/project-bootstrap`
> **Parallelism**: **Sequential — blocks every other Phase 1 task.**
> **Depends on**: nothing (Phase 0 is complete per [build_plan.md](../../build_plan.md)).

## Purpose

Establish the empty-but-importable Python package, the uv-managed dependency stack locked in [decisions.md](../../decisions.md), and the `.env.example` listing the three provider keys. Until this lands, no other Phase 1 task can run `uv run` anything or `import expertview` anything.

## Why it matters

- Every subsequent task assumes `pyproject.toml` exists and `uv sync` works.
- The package skeleton mirrors [architecture.md §2](../../architecture.md). Getting the directory tree right once prevents three downstream branches from inventing slightly different layouts.
- `.env.example` is what makes the provider-key test in Task 4 runnable on a fresh clone — it documents the three secrets without ever shipping them.

## Concrete steps (what to produce)

1. **Create `pyproject.toml`** managed by uv. Declare the dependency set from [build_plan.md §Phase 1 outputs](../../build_plan.md) verbatim: `langgraph`, `langchain-core`, `langchain-openai`, `langchain-huggingface`, `langchain-community`, `sentence-transformers`, `langsmith`, `pydantic`, `structlog`, `rich`, `pytest`, `pytest-asyncio`, `python-dotenv` (dev), `ruff`. Declare Python 3.11+ per [decisions.md (2026-05-20 Python + uv)](../../decisions.md). Configure ruff (lint + format) inside `pyproject.toml`. Add a `[project.scripts]` entry so `python -m expertview.cli` resolves later. Add no other dependency without adding a [decisions.md](../../decisions.md) entry first — this is a [CLAUDE.md hard rule](../../../CLAUDE.md).
2. **Create `.python-version`** with the pinned interpreter version uv should provision (3.11+).
3. **Create `.gitignore`** covering `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.env`, IDE noise, and the embedding cache directory that will be introduced in Phase 2. The existing `.gitignore` (already untracked at repo root per `git status`) may need to be merged rather than overwritten — inspect first.
4. **Create `.env.example`** listing the env vars enumerated in [build_plan.md §Phase 1 outputs](../../build_plan.md): `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `EXPERTVIEW_SYNTH_MODEL`. Each entry gets a one-line comment explaining what it controls. No real keys — placeholder values only. **Never edit `.env`** (CLAUDE.md hard rule); `.env.example` is the only env file in scope here.
5. **Create the `src/expertview/` package skeleton** matching [architecture.md §2](../../architecture.md) exactly. That means empty `__init__.py` files in `expertview/`, `expertview/agents/`, `expertview/agents/investigators/`, `expertview/rag/`, `expertview/rag/domains/`, `expertview/evidence/`, `expertview/orchestration/`, `expertview/prompts/`, `expertview/prompts/investigator/`, `expertview/prompts/synthesizer/`. Module files themselves (`models.py`, `state.py`, etc.) are produced by Tasks 2–5; this task only lays down the directory tree and `__init__.py` files so imports resolve.
6. **Create `tests/` skeleton**: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/fixtures/__init__.py`. Configure pytest in `pyproject.toml` to discover `tests/` and to enable `pytest-asyncio` in `auto` mode.
7. **Create empty placeholder `data/` directory tree** matching [architecture.md §2](../../architecture.md): `data/domains/{mechanical,process,supply_chain,environmental,human_factors}/.gitkeep`, `data/incidents/.gitkeep`. Phase 2+ populates these.
8. **Verify importability**: `uv sync`, then `uv run python -c "import expertview"` must succeed with no output. `uv run ruff check .` and `uv run ruff format --check .` must be clean on the empty package.

## What each step does

- Step 1 locks the dependency stack that the rest of Phase 1 imports. Doing it once here, with [decisions.md](../../decisions.md) as the gate for additions, prevents dependency churn across the three parallel branches.
- Step 2 ensures uv provisions the right interpreter on a fresh machine.
- Steps 3–4 set the hygiene baseline for secrets and ignored artifacts before any code lands.
- Step 5 is the architecture's table of contents in `__init__.py` form. Downstream tasks fill in modules; this step guarantees the paths they target exist.
- Step 6 makes `uv run pytest` a no-op-but-green so subsequent tasks can drop tests in incrementally.
- Step 7 reserves the data layout Phase 2's mock corpora and the locked CNC scenario will live in.
- Step 8 is the local quality gate proving the bootstrap is internally consistent before opening the PR.

## Code locations

- Repo root: `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`.
- `src/expertview/` and all subpackages per [architecture.md §2](../../architecture.md).
- `tests/` and subfolders.
- `data/domains/` and `data/incidents/` with `.gitkeep` placeholders.

## Connections (downstream)

- Task 2 fills `evidence/models.py` and `orchestration/state.py`.
- Task 3 fills `rag/base.py` and `rag/inmemory.py`.
- Task 4 fills `agents/base.py` and `agents/llms.py`.
- Task 5 fills `orchestration/runner.py`.
- Phase 2 fills `data/domains/mechanical/`, `data/incidents/cnc_out_of_tolerance.yaml`, the first investigator and synthesizer nodes, and `cli.py`.

## Risks / constraints / assumptions

- **Constraint**: ruff is the only lint/format tool ([decisions.md](../../decisions.md)). Do not introduce black, isort, flake8, or mypy as separate tools.
- **Constraint**: uv is the only package manager. Do not generate `requirements.txt`, `Pipfile`, or `poetry.lock` artifacts.
- **Risk**: dependency drift. Pin versions only where the integration is fragile (e.g., `langgraph` and `langchain-*` should align). If a pin choice is non-obvious, log it in [decisions.md](../../decisions.md) the same turn — this is a [CLAUDE.md hard rule](../../../CLAUDE.md).
- **Risk**: an existing untracked `.gitignore` at repo root (visible in `git status`) may already define rules — merge rather than overwrite to avoid losing intent.
- **Assumption**: the user already has `uv` installed and a usable OpenRouter / LangSmith API key. This task does not run any provider calls — it just declares the env-var contract.
- **Hard rule reminder**: never commit `.env`, `.venv/`, `__pycache__/`, or any secret. `.gitignore` is the enforcement mechanism for this task.

## Definition of done

- `uv sync` succeeds on a clean clone.
- `uv run python -c "import expertview"` succeeds with no output.
- `uv run ruff check .` and `uv run ruff format --check .` are clean.
- `uv run pytest` runs (collecting zero tests is fine; the command must not error).
- `.env.example` lists all five env vars with explanatory comments and no real values.
- PR opened on `chore/project-bootstrap` per [branching_strategy.md §5](../../branching_strategy.md), summarizing the bootstrap and naming the downstream tasks it unblocks.
