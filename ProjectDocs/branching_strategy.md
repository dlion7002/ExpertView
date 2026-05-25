# ExpertView — Branching Strategy

> This document explains how ExpertView uses Git branches, pull requests, checks, and tags. It is written so the workflow can be shown directly during a company demo.

## 1. Chosen strategy

ExpertView uses a **lightweight GitHub Flow / trunk-based workflow**.

The model is:

```text
main
  ↑
pull request
  ↑
short-lived branch
```

`main` stays stable and demo-ready. Work happens in short-lived topic branches. Changes move into `main` through pull requests after review and automated checks.

This is intentionally simpler than enterprise GitFlow. ExpertView is a focused solo-built demo project, not a product with multiple versions maintained in parallel.

## 2. Why this fits ExpertView

This strategy fits the project because:

- The project is solo-built, so a heavy process would look artificial.
- The goal is a reliable demo, so `main` must remain stable.
- The work naturally happens in small phases from [build_plan.md](build_plan.md).
- Pull requests create a visible review history for company reviewers.
- Automated checks prove that quality gates are not just written down.
- Release tags identify the exact commits that were demo-ready.

The workflow shows professional discipline without pretending this project needs long-lived release management.

## 3. Role of `main`

`main` is the source of truth for stable work.

Expected rules for `main`:

- It should always be runnable or, during the documentation-only foundation phase, internally consistent.
- It should only receive changes through reviewed pull requests.
- It should pass CI before merge.
- It should be the branch used for demos, screenshots, release tags, and portfolio review.
- It should not contain half-finished feature work.

For GitHub repository settings, protect `main` with:

- Require pull request before merge.
- Require status checks to pass.
- Require branches to be up to date before merge.
- Prevent force pushes.

## 4. Branch naming

Use short-lived branches with a clear prefix:

| Prefix | Use for | Example |
|---|---|---|
| `feature/*` | New capabilities, skeleton modules, or major sections | `feature/langgraph-state-skeleton` |
| `fix/*` | Bug fixes or broken behavior | `fix/rag-loader-paths` |
| `docs/*` | Documentation-only changes | `docs/demo-workflow` |
| `chore/*` | Tooling, CI, formatting, repository setup | `chore/github-actions-ci` |

Branch names should be lowercase, hyphen-separated, and tied to one clear outcome.

Avoid:

- `develop`
- `release/*`
- `hotfix/*`
- Long-running personal branches
- Catch-all names such as `updates`, `misc`, or `final`

## 5. Pull request expectations

Pull requests are the main collaboration checkpoint.

For this solo project, a PR still matters because it records:

- What changed.
- Why the change exists.
- How it was verified.
- Whether docs or decisions were updated.
- Whether the change affects the demo.

A good PR should be small enough to review in one sitting and should include:

- Summary of the change.
- Affected files or modules.
- Verification commands and results.
- Screenshots or demo notes when UI behavior exists.
- Link to any updated decision or open question.

Merge style should prefer **squash merge** for small branches when the branch contains noisy intermediate commits, or **merge commit** when preserving a clean multi-commit story helps explain the work.

## 6. Commit expectations

Commits should be small and intentional.

Use:

```text
<area>: <one-line summary>
```

Examples:

- `docs: add branching strategy`
- `chore: add pull request template`
- `feature: introduce evidence models`
- `fix: correct provider selection`

The commit body should explain why the change matters when the reason is not obvious. The diff already shows what changed.

Do not bypass hooks or checks with `--no-verify`, `--no-gpg-sign`, or similar flags.

## 7. Automated checks

CI runs on pull requests and pushes to `main`.

At the foundation stage, CI validates repository health:

- Required workflow documents are present.
- Markdown and YAML files keep basic text hygiene.
- Python quality gates are ready to run once the package is scaffolded.

Once `pyproject.toml` exists, CI runs the project quality gate:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Later, once the demo CLI exists, the release-readiness check should include:

```powershell
uv run python -m expertview.cli demo
```

## 8. Release tags

Demo-ready states are marked with annotated tags on `main`.

Recommended naming:

| Tag | Meaning |
|---|---|
| `v0.1.0-demo` | Workflow and repository foundation ready |
| `v0.2.0-demo` | Skeleton and contracts ready |
| `v0.3.0-demo` | First end-to-end vertical slice ready |
| `v1.0.0-demo` | Final rehearsed company / hackathon demo |

Use annotated tags:

```powershell
git switch main
git pull --ff-only
git tag -a v0.1.0-demo -m "Demo-ready workflow foundation"
git push origin v0.1.0-demo
```

Each tag should have short release notes that explain:

- What is stable enough to demonstrate.
- What checks passed.
- What is intentionally out of scope.
- Any known demo limitations.

## 9. Difference from GitFlow

ExpertView intentionally does **not** use full GitFlow.

| Topic | Lightweight ExpertView workflow | Heavy GitFlow-style workflow |
|---|---|---|
| Stable branch | `main` | `main` plus `develop` |
| Feature work | Short-lived branches into `main` | Feature branches into `develop` |
| Releases | Annotated tags on stable `main` | Long-lived `release/*` branches |
| Emergency fixes | `fix/*` into `main` | `hotfix/*` branches with back-merges |
| Best fit | Solo demo project, fast iteration, portfolio review | Multiple maintained production versions |

GitFlow would add vocabulary without solving a real project problem here. The lightweight strategy is easier to execute, easier to explain, and more honest for a focused pre-hackathon build.

## 10. Demo talk track

Use this when explaining the repository to a company:

> "I kept the workflow intentionally lightweight. `main` is the stable demo branch. I do feature work in short-lived branches like `feature/langgraph-skeleton` or `docs/demo-workflow`, then merge through pull requests. Even though this is a solo project, PRs act as review checkpoints: they explain intent, list verification, and connect code changes to decisions. CI runs on PRs and on `main`, so the demo branch stays trustworthy. When a state is worth presenting, I tag it as a demo release, for example `v0.1.0-demo`. I avoided GitFlow because this project does not need `develop`, release branches, or multiple maintained versions. The process is intentionally small, but it still shows branch discipline, review habits, quality gates, and release traceability."

If the reviewer asks how work is planned, point them to:

- [build_plan.md](build_plan.md) for phase planning.
- [workflow.md](workflow.md) for quality gates.
- [decisions.md](decisions.md) for locked decisions.
- [../CONTRIBUTING.md](../CONTRIBUTING.md) for branch and PR expectations.
