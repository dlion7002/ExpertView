---
name: phase-task-breakdown
description: Drafts the ExpertView phase task-breakdown folder at ProjectDocs/phases/phase-N/ from build_plan.md. Generates a README index and N self-contained task files matching the locked structure first established by phase-1 and refined in phase-2 / phase-3. Use when the user types /phase-task-breakdown, asks to break down phase N, plan phase N, or create phase-N tasks.
---

# Phase Task Breakdown

Drafts `ProjectDocs/phases/phase-N/` for the ExpertView project. Produces a `README.md` index plus N task files matching the locked structure.

## When to invoke

Triggered by `/phase-task-breakdown <N>` or by phrases like "break down phase N", "plan phase N", "create phase-N tasks". `N` is the phase number from `ProjectDocs/build_plan.md`.

## Workflow

### 1. Gather phase context

Read in this order:

- `CLAUDE.md` — hard rules, workflow rules, architecture rules.
- `ProjectDocs/build_plan.md` — locate `Phase N`. Extract the **phase goal** and **quality gate** verbatim; these go into the README header block.
- `ProjectDocs/architecture.md` §2 (module map) and §5 (architecture rules).
- `ProjectDocs/phases/phase-(N-1)/` — most recent example; confirm the locked structure has not drifted.
- `ProjectDocs/decisions.md` — any locked decision that bears on this phase.

### 2. Ask 3-4 structural questions

Use `AskUserQuestion`. Default question set, adapted to the phase:

1. **Task shape** — vertical bundle (one task per domain / module / branch), horizontal layer (one task per architectural layer), or hybrid. Phase 2 was horizontal (one domain, layered slices); phase 3 was vertical (four domains, one bundle per domain).
2. **Where cross-cutting tasks live** — dispatcher / wiring / `/verify` / observability: standalone tasks or folded into a single final task.
3. **Phase-specific scope choice** — anything in the build_plan's risk register that could land in this phase or be deferred (throttling, retries, caching, structlog, parameter tuning). Surface as an explicit decision.
4. **Skill / pattern flag** — if a pattern in this phase repeats one already used twice elsewhere, flag it (CLAUDE.md's ≥3 threshold for skill candidacy).

Skip any question whose answer is already locked in `decisions.md`.

### 3. Plan and get approval

Present a plan in chat: file count, task-by-task one-liner, files / paths that will **not** be touched, material risks. Wait for explicit user approval before writing.

### 4. Draft the files

Use the templates as the structure source of truth. Fill the `{{PLACEHOLDERS}}` and **strip** the `<!-- ... -->` guidance comments from rendered output.

- [templates/README_TEMPLATE.md](templates/README_TEMPLATE.md) → `ProjectDocs/phases/phase-N/README.md`.
- [templates/TASK_TEMPLATE.md](templates/TASK_TEMPLATE.md) → each `ProjectDocs/phases/phase-N/task-K-<slug>.md`.

Use `[[task-K-slug]]` wiki-link syntax when one task references a sibling in its Connections section (matches phase-2 / phase-3 precedent).

### 5. Report and stop

Report: files created with paths, cross-cutting risks discovered during drafting, any stale memory or doc noticed in passing. **Do not** `git add`, **do not** commit, **do not** modify `decisions.md` / `open_questions.md` / `pyproject.toml`, **do not** write code under `src/`. Drafting is the entire scope.

## Hard constraints (from CLAUDE.md)

- Never edit `.env`, `pyproject.toml`, or `decisions.md` without explicit approval.
- Module boundaries are walls — when describing Connections in a task file, never invent imports across architecture-rule boundaries (e.g., `rag/` does not import from `agents/`).
- No emojis in any output file.
- No prompt strings inlined in code — if a task involves a prompt, it lives under `src/expertview/prompts/`.
- Match the project's matter-of-fact tone (see existing `ProjectDocs/*.md`).

## Reference materials

- `CLAUDE.md` — operating guide.
- `ProjectDocs/build_plan.md` — canonical phase definitions.
- `ProjectDocs/architecture.md` — module map + architecture rules.
- `ProjectDocs/decisions.md` — locked decisions.
- `ProjectDocs/phases/phase-1/`, `phase-2/`, `phase-3/` — locked-structure references.
