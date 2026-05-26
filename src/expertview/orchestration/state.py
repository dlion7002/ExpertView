"""LangGraph shared-state schema.

`ExpertViewState` is the one allowed non-pydantic cross-node type in the
codebase (per CLAUDE.md). The list-typed fields use the `operator.add`
reducer so concurrent investigator branches merge by list concatenation
when they emit state patches simultaneously via the LangGraph Send API.
"""

import operator
from typing import Annotated, TypedDict

from expertview.evidence.models import (
    CausalReport,
    Finding,
    Hypothesis,
    Incident,
)


class ExpertViewState(TypedDict):
    incident: Incident
    # operator.add reducer = list concatenation across parallel branches.
    # Without it, the 5-way investigator fan-out would silently last-writer-win.
    findings: Annotated[list[Finding], operator.add]
    hypotheses: Annotated[list[Hypothesis], operator.add]
    spawned_subinvestigations: Annotated[list[str], operator.add]
    # Single-writer (synthesizer); no reducer.
    causal_report: CausalReport | None
