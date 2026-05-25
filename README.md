# ExpertView

ExpertView is a pre-hackathon, portfolio-ready Root Cause Analysis system for industrial manufacturing incidents. The project is being built as a modular LangGraph + RAG application where domain investigators work in parallel and converge on an evidence-weighted causal report.

The repository is intentionally managed with a lightweight professional workflow so it can be explained clearly during a company demo.

## Repository Workflow

ExpertView uses a GitHub Flow / lightweight trunk-based workflow:

- `main` is the stable, demo-ready branch.
- Feature, fix, documentation, and maintenance work happen in short-lived branches.
- Pull requests are used as review and documentation checkpoints, even for solo development.
- CI validates repository health now and runs Python quality gates once the Python package is scaffolded.
- Demo-ready milestones are marked with annotated release tags.

Start with:

- [Branching strategy](ProjectDocs/branching_strategy.md) for the full workflow and demo talk track.
- [Contributing guide](CONTRIBUTING.md) for day-to-day branch, commit, PR, and release expectations.
- [Project vision](ProjectDocs/vision.md) for the product intent.
- [Architecture](ProjectDocs/architecture.md) for module boundaries and technical design.
- [Build plan](ProjectDocs/build_plan.md) for phase order and quality gates.

## Current Status

This repository is still in the foundation stage. Product features should not be added until the documented workflow, skeleton, and quality gates are in place.
