# Summary

Describe the goal of this change in 2-4 sentences.

# Change Type

- [ ] `feature/*` - product capability or major project section
- [ ] `fix/*` - bug fix
- [ ] `docs/*` - documentation-only change
- [ ] `chore/*` - tooling, CI, or repository maintenance

# Review Checklist

- [ ] Branch name follows `feature/*`, `fix/*`, `docs/*`, or `chore/*`.
- [ ] `main` remains stable and demo-ready after merge.
- [ ] Documentation was updated where needed.
- [ ] `ProjectDocs/decisions.md` was updated for any locked decision.
- [ ] `ProjectDocs/open_questions.md` was updated if any question was resolved or introduced.
- [ ] Automated checks pass or the reason they cannot run yet is documented below.
- [ ] A release tag is recommended if this creates a demo-ready milestone.

# Verification

List the commands run and their result.

```powershell
# Example
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

# Demo Notes

Explain whether this change affects the company demo, release notes, screenshots, or the talk track.
