<!--
Task skeleton for ProjectDocs/phases/phase-N/task-K-<slug>.md.
Fill the {{PLACEHOLDERS}} and STRIP all <!-- ... --> comments from the rendered output.
Reference precedent: ProjectDocs/phases/phase-2/task-1-data-authoring.md (sequential task)
and phase-2/task-3-mechanical-investigator.md (parallelizable task).
-->

# Task {{K}} — {{TASK_TITLE}}

> **Branch suggestion**: `{{BRANCH_NAME}}`
> **Parallelism**: **{{PARALLELISM_LABEL}}.** {{PARALLELISM_NOTE}}
> **Depends on**: {{DEPENDS_ON}}
<!--
PARALLELISM_LABEL is one of: "Sequential", "Parallelizable with Tasks K, L, M".
PARALLELISM_NOTE is a one-sentence clarifier (e.g., "Blocks Tasks 2 and 5",
"No shared editing surface with siblings").
DEPENDS_ON names prior tasks or the prior phase tag, e.g.:
"Phase N-1 complete (v0.X.0-demo tagged)" or "Task K" or "Phase 1 plus Task 1".
-->

## Purpose

{{PURPOSE_PARAGRAPH}}
<!--
1-2 paragraphs. State what this task produces and how it advances the phase.
End by clarifying what this task does NOT do (e.g., "This task does not modify
orchestration/runner.py — the dispatcher rewrite is Task 5's responsibility.")
-->

## Why it matters

{{WHY_IT_MATTERS_BULLETS}}
<!--
2-4 bullets. Each bullet cites a specific decision, architecture rule, or
build_plan goal that justifies the task's existence. Examples:
- "decisions.md (2026-05-25 Q2) locks the CNC scenario; this corpus is the proof."
- "Phase N's quality gate requires X; this task ships X."
- "architecture.md section 5 requires nodes be pure async (State) -> dict;
   establishing the right shape here means Phase N+1's siblings copy a clean pattern."
-->

## Concrete steps (what to produce)

1. **{{STEP_1_HEADING}}** — {{STEP_1_BODY}}
2. **{{STEP_2_HEADING}}** — {{STEP_2_BODY}}
3. **{{STEP_3_HEADING}}** — {{STEP_3_BODY}}
4. **{{STEP_4_HEADING}}** — {{STEP_4_BODY}}
5. **{{STEP_5_HEADING}}** — {{STEP_5_BODY}}
6. **Verify locally**: `uv run pytest {{TEST_PATH}}` green; `uv run ruff check .` and `uv run ruff format --check .` clean.
<!--
4-7 numbered steps. The last step is always the local verify command.
Each step names *what* to produce, not *how* to write it.
Bold the imperative verb opening of each step (matches phase-2/3 precedent).
-->

## What each step does

{{WHAT_EACH_STEP_DOES_BULLETS}}
<!--
One bullet per numbered step, explaining the *why* in one sentence.
Format: "**Step K** does X because Y."
The verify step's bullet is always "**Step N** is the local quality gate."
-->

## Code locations

{{CODE_LOCATIONS_BULLETS}}
<!--
One bullet per new or modified file. Annotate with (new), (edit), or (new if absent).
Use src-relative absolute paths exactly as they will appear in the repo, e.g.:
- `src/expertview/agents/investigators/process.py` (new).
- `src/expertview/orchestration/runner.py` (edit -- dispatcher body, make_graph node registration).
-->

## Connections

**Upstream**:

{{UPSTREAM_BULLETS}}
<!--
Bulleted list of what this task imports or depends on. Group by source:
- evidence/models.py -- Incident, Finding (Phase 1).
- agents/llms.py -- create_investigator_llm() (Phase 1).
- rag/domains/mechanical.py -- reference implementation (Phase 2).
Cite the originating phase in parentheses.
-->

**Downstream**:

{{DOWNSTREAM_BULLETS}}
<!--
Use [[task-K-slug]] wiki-link syntax for sibling task files.
Cite future phases by name (e.g., "Phase 4's spawning logic").
Example:
- [[task-5-dispatcher-wiring-verify]] imports this factory and registers the node.
- Phase 4's spawning trigger keys on this node's findings.
-->

## Parallelism rationale

{{PARALLELISM_RATIONALE_BULLETS}}
<!--
2-4 bullets explaining why this task does or does not share editing surface with siblings.
Reference architecture.md section 5's "module boundaries are walls" where relevant.
Name the exact paths the task touches, and confirm none overlap with sibling tasks.
-->

## Risks / constraints / assumptions

{{RISKS_BULLETS}}
<!--
Mix of **Risk** / **Constraint** / **Assumption** entries.
Each entry: bold label, colon, description. Add "Mitigation: ..." for risks.
Always include the relevant CLAUDE.md hard rules and architecture.md walls.
Common entries to consider:
- Constraint: prompts live as files under src/expertview/prompts/ (CLAUDE.md hard rules).
- Constraint: the only legal LLM construction site is agents/llms.py.
- Constraint: module boundaries are walls (architecture.md section 5).
- Risk: <specific failure mode>. Mitigation: <how the steps above address it>.
- Assumption: <upstream invariant>. If it fails: <what to do>.
-->

## Definition of done

{{DOD_BULLETS}}
<!--
Concrete, checkable bullets. Always include these last two:
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- PR opened on `{{BRANCH_NAME}}` per branching_strategy.md section 5.
The PR-description bullet should call out anything reviewers should look for
(curator-attention files, mechanical cross-cutting edits, empirical thresholds).
-->
