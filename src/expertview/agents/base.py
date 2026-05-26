"""Public agent protocols for investigators and synthesizers."""

from typing import Protocol

from expertview.evidence.models import CausalReport, Finding, Hypothesis, Incident


class Investigator(Protocol):
    domain: str

    async def investigate(
        self,
        incident: Incident,
        prior_findings: list[Finding],
    ) -> list[Finding]: ...


class Synthesizer(Protocol):
    async def converge(
        self,
        hypotheses: list[Hypothesis],
        findings: list[Finding],
    ) -> CausalReport: ...
