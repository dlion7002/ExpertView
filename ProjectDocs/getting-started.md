# Getting Started with ExpertView

A step-by-step guide to install ExpertView, configure it, and run the multi-agent
Root Cause Analysis (RCA) demo on your own machine — both the **Streamlit** surface
and the **live CLI** fallback. It also covers the developer quality gates (tests,
lint, format) and the most common first-run issues.

> **TL;DR** (if you already have `uv` and an OpenRouter key):
> ```powershell
> uv sync
> Copy-Item .env.example .env      # then edit .env and set OPENROUTER_API_KEY
> uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml --live
> uv run streamlit run src/expertview/ui/app.py
> ```

---

## 1. What you're running

ExpertView investigates an industrial manufacturing incident with **five domain
investigators** (mechanical, process, supply chain, environmental, human factors)
that run in parallel as LangGraph branches against domain-specific RAG stores,
spawn a sub-investigation when the evidence warrants it, and converge on an
evidence-weighted `CausalReport`. There are two ways to watch it run:

| Surface | Command | Use it for |
|---|---|---|
| **Streamlit** (primary demo) | `uv run streamlit run src/expertview/ui/app.py` | The single-screen demo: live parallel status, the Mermaid topology, and the final causal report. |
| **Live CLI** (Plan B) | `uv run python -m expertview.cli demo --incident <path> --live` | A rich-terminal mirror of the same run — the venue-laptop fallback if Streamlit misbehaves. |
| **Plain CLI** | `uv run python -m expertview.cli demo --incident <path>` | Blocking run that prints only the final report. |

Both live surfaces share the same streaming core and node labels, so they tell the
identical story. See [architecture.md](../architecture.md) for the full module map.

---

## 2. Prerequisites

1. **Python 3.11 or 3.12.** The project pins **3.12** (see [.python-version](../../.python-version));
   `uv` will fetch a matching interpreter automatically if you don't have one.
2. **[uv](https://docs.astral.sh/uv/)** — the package/environment manager this project uses.
   - Windows (PowerShell):
     ```powershell
     winget install --id=astral-sh.uv -e
     ```
     or
     ```powershell
     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
     ```
   - Verify: `uv --version`
3. **Git** (you most likely already have the repo cloned).
4. **An OpenRouter API key** — required for any real run. Free open-weight models
   cover the build/demo path; a paid frontier model is optional for the polished demo.
   Get one at <https://openrouter.ai/>.
5. **Disk + network for the first run.** On the first run ExpertView downloads a small
   local embedding model (`BAAI/bge-small-en-v1.5`, ~130 MB) via `sentence-transformers`.
   This is a one-time download, cached by Hugging Face; embeddings then run **locally**
   and need no API key.

> **No OpenRouter key yet?** You can still install everything and run the test suite —
> the unit tests and most integration tests use fakes and never hit the network. Only
> the live demo and the live-provider integration tests need the key.

---

## 3. Get the code

If you haven't cloned it yet:

```powershell
git clone https://github.com/dlion7002/ExpertView.git
cd ExpertView
```

All commands below assume your shell's working directory is the **repository root**
(the folder containing `pyproject.toml`).

---

## 4. Install dependencies

```powershell
uv sync
```

This creates a project-local virtual environment in `.venv/` and installs everything
from [pyproject.toml](../../pyproject.toml) — the runtime dependencies (LangGraph,
langchain-openai, sentence-transformers, rich, streamlit, …) **and** the `dev` group
(pytest, ruff, python-dotenv). You do **not** need to activate `.venv` manually; the
`uv run …` prefix used throughout this guide runs commands inside it.

> **Windows note — the `VIRTUAL_ENV` warning.** If you see
> `warning: VIRTUAL_ENV=... does not match the project environment path '.venv'`,
> it's harmless: another tool (often the IDE) exported a different `VIRTUAL_ENV`. `uv`
> ignores it and uses `.venv`. To silence it, clear the variable in your shell:
> ```powershell
> Remove-Item Env:VIRTUAL_ENV
> ```

---

## 5. Configure your environment

ExpertView reads configuration from a git-ignored `.env` file. Copy the template and
fill in your values:

```powershell
Copy-Item .env.example .env
```

Then open [.env](../../.env) and set, at minimum:

| Variable | Required? | What it does |
|---|---|---|
| `OPENROUTER_API_KEY` | **Yes** (for real runs) | Auth for all LLM calls (investigators + synthesizer), routed through OpenRouter's OpenAI-compatible API. |
| `EXPERTVIEW_SYNTH_MODEL` | No (defaults to `deepseek/deepseek-v4-flash:free`) | The synthesizer's OpenRouter model ID. Use a free model for the build, a paid frontier model for the demo (see §8). |
| `LANGSMITH_API_KEY` | No | Enables LangSmith trace capture for every node + LLM call. Leave unset to disable tracing — the run still works. |
| `LANGSMITH_PROJECT` | No (defaults to `expertview-dev`) | Groups your traces in the LangSmith dashboard. |

Notes:

- The **investigator** model is fixed at `openrouter/owl-alpha` (free) in code — there's
  no env var for it.
- **Never commit `.env`** (it's git-ignored) and never put real keys in `.env.example`.
- The CLI and the Streamlit app load `.env` automatically from the repo root. The
  provider factory itself never reads `.env` — so if you run code another way, export
  the variables first or use `uv run --env-file .env …`.

See [.env.example](../../.env.example) for the annotated list of model options.

---

## 6. Verify the install (developer quality gates)

These are the same checks CI runs. Run them from the repo root:

```powershell
uv run pytest                  # unit + integration tests
uv run ruff check .            # lint
uv run ruff format --check .   # format check
```

Expectations:

- **Unit tests** are hermetic — they use fakes and pass with no API key and no network.
- A **few integration tests** make real OpenRouter calls (e.g.
  `tests/integration/test_provider_keys.py`). Without `OPENROUTER_API_KEY` they fail or
  skip; with a key they depend on the free model being up (see [Troubleshooting](#10-troubleshooting)).
- `ruff check` and `ruff format --check` should report clean. To auto-fix formatting,
  drop the `--check`: `uv run ruff format .`.

---

## 7. Run the demo

There are two rehearsed incidents under [data/incidents/](../../data/incidents/):

- `cnc_out_of_tolerance.yaml` — CNC bore out of tolerance.
- `process_recipe_drift.yaml` — injection-molding recipe drift after a changeover.

### 7a. Streamlit (primary surface)

```powershell
uv run streamlit run src/expertview/ui/app.py
```

Streamlit opens a browser tab. Pick an incident, click **Run investigation**, and watch:

- the per-investigator status panel light up as each branch completes,
- the **Mermaid topology** of the compiled LangGraph, and
- the final evidence-weighted causal report with confidence bars and citations.

### 7b. Live CLI (the rich-terminal Plan B)

```powershell
uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml --live
```

The `--live` flag streams a `rich` table that flips each stage from **Waiting** to
**Complete** as its node finishes (including the spawned sub-investigator when it
fires), then renders the same final report. The node labels match the Streamlit
surface exactly.

### 7c. Plain CLI (blocking, final report only)

```powershell
uv run python -m expertview.cli demo --incident data/incidents/process_recipe_drift.yaml
```

Same result, no live view — useful for scripting or piping the report.

> You can also use the installed console script instead of `python -m`:
> ```powershell
> uv run expertview demo --incident data/incidents/cnc_out_of_tolerance.yaml --live
> ```

### What happens on the first run

The first invocation of any surface compiles the graph, which:

1. downloads the local embedding model (one-time, ~130 MB) — expect a short pause,
2. indexes the domain documents under [data/domains/](../../data/domains/) into
   in-memory RAG stores, and
3. constructs the OpenRouter-backed LLM clients (this is where a missing
   `OPENROUTER_API_KEY` first surfaces as an error).

If LangSmith is configured, the CLI prints a clickable trace URL at the end of the run.

---

## 8. Switching the synthesizer model (free build vs. paid demo)

The synthesizer model is selected at runtime via `EXPERTVIEW_SYNTH_MODEL` — an
OpenRouter model ID. The investigators always use the free `openrouter/owl-alpha`.

- **Build / everyday (free):** keep the default `deepseek/deepseek-v4-flash:free`
  (or another free ID from [.env.example](../../.env.example)).
- **Demo / final rehearsal (paid frontier):** set a paid ID for a single run, e.g.

  ```powershell
  $env:EXPERTVIEW_SYNTH_MODEL = "anthropic/claude-opus-4.7"
  uv run python -m expertview.cli demo --incident data/incidents/cnc_out_of_tolerance.yaml --live
  ```

  This overrides `.env` for the current shell session only. Unset it with
  `Remove-Item Env:EXPERTVIEW_SYNTH_MODEL` to fall back to the `.env` value.

---

## 9. Project layout (where things live)

```
ExpertView/
├─ src/expertview/
│  ├─ cli.py               # CLI entry point: `demo` command, --live mode, report rendering
│  ├─ agents/              # investigators, synthesizer, and the sole LLM-client factory (llms.py)
│  ├─ orchestration/       # LangGraph runner (make_graph), shared state, streaming core
│  ├─ rag/                 # domain KnowledgeStore implementations
│  ├─ evidence/            # pydantic models (Finding, Hypothesis, CausalReport, …) + convergence math
│  ├─ prompts/             # versioned investigator/synthesizer prompts (never inlined in code)
│  └─ ui/                  # Streamlit app + render helpers
├─ data/
│  ├─ incidents/           # rehearsed incident YAML files
│  └─ domains/             # per-domain markdown corpus indexed into the RAG stores
├─ tests/                  # unit/ (hermetic) and integration/ (some live-provider)
└─ ProjectDocs/            # vision, architecture, build plan, decisions, phase plans, this guide
```

---

## 10. Troubleshooting

| Symptom | Cause & fix |
|---|---|
| `RuntimeError: OPENROUTER_API_KEY is required …` | No key in the environment. Confirm `.env` exists at the repo root with a real `OPENROUTER_API_KEY`, and that you're running from the repo root (or use `uv run --env-file .env …`). |
| `502 Bad Gateway` / `Provider returned error` (provider "Stealth") | The **free** `owl-alpha` investigator model is temporarily down upstream — not a bug in your setup. Retry later, or switch the build to a different free model where applicable. |
| `429` / rate-limit errors during repeated runs | OpenRouter free-tier throttling. Run incidents **sequentially**, not concurrently; the per-run investigator concurrency is already capped at 5. |
| First run hangs for a while with no output | One-time download of the `BAAI/bge-small-en-v1.5` embedding model. Let it finish; subsequent runs are fast. |
| `warning: VIRTUAL_ENV=… does not match … '.venv'` | Harmless (see §4). Clear it with `Remove-Item Env:VIRTUAL_ENV` to silence. |
| Garbled characters in the terminal report on Windows | The CLI reconfigures stdout to UTF-8 and falls back to ASCII bars automatically; if your console is still cp1252-locked, use Windows Terminal or set the code page to UTF-8 (`chcp 65001`). |
| `streamlit: command not found` | Run it through uv: `uv run streamlit run …` (don't call a global `streamlit`). |
| LangSmith trace notice says tracing is disabled | Expected when `LANGSMITH_API_KEY` is unset — the run still completes. Set the key to capture traces. |

---

## 11. Next steps

- [vision.md](../vision.md) — what ExpertView is for and who it's for.
- [architecture.md](../architecture.md) — module boundaries, protocols, data flow.
- [build_plan.md](../build_plan.md) — phase order and quality gates.
- [branching_strategy.md](../branching_strategy.md) — the Git/PR/tag workflow.
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — day-to-day branch, commit, and PR expectations.
