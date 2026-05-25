# Contributing to ExpertView

ExpertView is currently a solo-built demo project, but it is managed as if changes were being reviewed by a small professional team. The process is intentionally lightweight: enough structure to protect `main`, document decisions, and make demo milestones traceable, without adding unnecessary long-lived branches.

## Branching Model

Use short-lived branches from `main`:

| Branch type | Use for | Example |
|---|---|---|
| `feature/*` | New product capabilities or major project sections | `feature/langgraph-skeleton` |
| `fix/*` | Bug fixes or broken behavior | `fix/provider-env-validation` |
| `docs/*` | Documentation-only changes | `docs/branching-strategy` |
| `chore/*` | Repository maintenance, tooling, or configuration | `chore/ci-health-checks` |

`main` should always represent the stable, demo-ready state of the project. Avoid `develop`, `release/*`, and `hotfix/*` branches unless the project later needs multiple maintained release lines.

## Pull Requests

Every non-trivial change should move through a pull request. For solo work, the pull request is still useful because it creates a review checkpoint, explains the intent, shows the quality gates, and gives a company reviewer a clean history of decisions.

Each pull request should include:

- The goal of the change.
- The files or modules affected.
- The checks run locally.
- Any documentation or decision-log updates.
- Any demo impact or release-tag recommendation.

Before merging, the pull request should be up to date with `main`, CI should be green, and the change should be small enough to review in one sitting.

## Commits

Use one logical change per commit. A module and its tests can live in the same commit.

Commit message format:

```text
<area>: <one-line summary>

Explain why the change exists when the reason is not obvious from the diff.
```

Examples:

- `docs: document lightweight branching strategy`
- `chore: add repository health CI`
- `feature: scaffold evidence schemas`

## Automated Checks

GitHub Actions runs on pull requests and pushes to `main`.

Current foundation-stage checks validate repository documentation and text-file hygiene. Once `pyproject.toml` exists, CI also runs:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The project-level definition of done remains in [ProjectDocs/workflow.md](ProjectDocs/workflow.md).

## Release Tags

Use annotated tags for demo-ready milestones:

```powershell
git tag -a v0.1.0-demo -m "Demo-ready workflow foundation"
git push origin v0.1.0-demo
```

Tags should identify states that are worth showing to a company, judge, or interviewer. Each tag should correspond to a stable `main` commit with passing checks and clear release notes.
