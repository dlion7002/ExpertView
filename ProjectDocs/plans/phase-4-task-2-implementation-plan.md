# Phase 4 Task 2 Implementation Plan

## Goal

Wire the Task 1 bearing-anomaly predicate and supplier-history sub-investigator into the LangGraph runner so the rehearsed CNC scenario can dynamically spawn a supply-chain sub-investigation before synthesis.

## Affected Files

- `src/expertview/orchestration/runner.py`
- `src/expertview/agents/investigators/sub_investigator.py`
- `tests/integration/test_dynamic_spawning.py`
- `ProjectDocs/decisions.md`

## Change Sketch

- Add an explicit `spawning_join` node after the five parallel investigator branches.
- Add `_should_spawn(state)` as a pure conditional-edge dispatcher over `is_bearing_anomaly`.
- Register `sub_investigator` with the existing supply-chain store and shared investigator LLM, then route `sub_investigator` to `synthesizer`.
- Add sub-investigator structlog start/finish events using `domain="sub_investigator"`.
- Add deterministic integration tests for spawn and fallthrough branches with fake stores and fake LLMs.

## Risks

- The conditional edge must run after all five investigator findings merge, or the bearing finding can be missed.
- The synthesizer must run only after the sub-investigator in the spawn branch, or the spawned finding will not be visible in the report.
- Existing unrelated working-tree changes must remain unstaged.
