# Task 1 Implementation Plan — Data Authoring

## Goal

Add the first mechanical-domain corpus and the rehearsed CNC out-of-tolerance incident so Phase 2 has validated data for the mechanical RAG loader and later CLI demo.

## New files

- `data/domains/mechanical/fmea-hydraulic-cylinder.md`
- `data/domains/mechanical/fmea-spindle-bearing-wear.md`
- `data/domains/mechanical/maintenance-log-line-2-hydraulic-cylinder-2026-05-24.md`
- `data/domains/mechanical/maintenance-log-line-2-shift-3-drift.md`
- `data/domains/mechanical/service-note-hydraulic-cylinder-alignment.md`
- `data/domains/mechanical/service-note-spindle-bearing-preload.md`
- `data/domains/mechanical/supplier-change-memo-bearing-batch-b-227.md`
- `data/domains/mechanical/qa-receipt-bearing-batch-b-227.md`
- `data/incidents/cnc_out_of_tolerance.yaml`
- `tests/unit/test_incident_yaml.py`

## Implementation sketch

- Keep the corpus to 8 short markdown operations documents with clear document IDs and filenames suitable for future citations.
- Plant a plausible causal trail around line 2, shift 3, post-hydraulic-cylinder maintenance, spindle chatter, preload sensitivity, and bearing batch `B-227` from a new supplier.
- Keep the incident YAML matched exactly to the current `Incident` pydantic model.
- Validate YAML loading through `Incident.model_validate(...)` in a focused unit test.

## Risks

- The clue trail could be too sparse for downstream retrieval; mitigate by repeating the key terms across logs, service notes, and batch references.
- The clue trail could feel staged; mitigate by writing the files as normal maintenance, FMEA, service, and QA records instead of narrative exposition.
- YAML/schema drift could break the demo later; mitigate with `tests/unit/test_incident_yaml.py`.

## Verification

- `uv run pytest tests/unit/test_incident_yaml.py`
- `uv run pytest`
- `uv run ruff check .`
- `uv run ruff format --check .`
