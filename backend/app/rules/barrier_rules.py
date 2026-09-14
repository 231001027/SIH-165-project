"""Converts negation-engine barrier findings into a risk-scoring component and
reason codes. Severity mapping follows blueprint Part 2.4's worked definition
("0 if verified/effective, 0.5 if unverified/ambiguous, 1.0 if explicitly
failed/bypassed/absent") with one refinement we document as our own design
decision: a barrier explicitly left NOT_VERIFIED because work *proceeded
before* verifying it (e.g. "opened the flange before confirming isolation")
is stronger evidence of an unsafe act than an ambiguous, un-discussed
barrier, so it is scored closer to an explicit failure (0.8) than to genuine
ambiguity (0.5)."""
from __future__ import annotations

from app.nlp.negation import BarrierFinding

STATUS_SEVERITY = {
    "PRESENT_EFFECTIVE": 0.0,
    "NOT_VERIFIED": 0.5,
    "UNKNOWN": 0.5,
    "MISSING": 0.9,
    "BYPASSED": 1.0,
    "FAILED": 1.0,
}

NO_BARRIER_MENTIONED_COMPONENT = 0.25  # mild uncertainty, not "assume failure"


def barrier_failure_component(findings: list[BarrierFinding]) -> tuple[float, str | None]:
    """Returns (component 0-1, worst_barrier_type_or_None)."""
    if not findings:
        return NO_BARRIER_MENTIONED_COMPONENT, None

    best_finding = None
    best_severity = -1.0
    for finding in findings:
        severity = STATUS_SEVERITY.get(finding.status, 0.5)
        if finding.critical_gap:
            severity = max(severity, 0.8)
        if severity > best_severity:
            best_severity = severity
            best_finding = finding

    return best_severity, (best_finding.barrier_type if best_finding else None)
