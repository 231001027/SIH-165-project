"""Secondary ISO 45001 / PSM-inspired tags mapped from extracted fields.

These are prototype design labels for dashboard context — they do NOT replace
IOGP Life-Saving Rules as the primary classifier output.
"""
from __future__ import annotations


# Heuristic maps (prototype design decisions, not official OIL/ISO scoring).
_HAZARD_TO_ISO = {
    "Stored / pressurized energy": ["ISO 45001:8.1 Operational planning", "PSM: Mechanical Integrity"],
    "Falling from height": ["ISO 45001:8.1 Operational planning", "PSM: Safe Work Practices"],
    "Struck by / crushing": ["ISO 45001:8.1 Operational planning", "PSM: Mechanical Integrity"],
    "Fire / explosion": ["ISO 45001:8.2 Emergency preparedness", "PSM: Hot Work"],
    "Confined space atmosphere": ["ISO 45001:8.1 Operational planning", "PSM: Confined Space"],
    "Electrical contact": ["ISO 45001:8.1 Operational planning", "PSM: Energy Isolation"],
    "Chemical exposure": ["ISO 45001:8.1 Operational planning", "PSM: Process Safety Information"],
}

_BARRIER_TO_PSM = {
    "Isolation / LOTO": ["PSM: Energy Isolation / LOTO"],
    "Permit to Work": ["PSM: Safe Work Practices / PTW"],
    "Gas Testing": ["PSM: Confined Space Entry"],
    "PPE": ["ISO 45001:8.1.2 Eliminating hazards"],
    "Supervision / Spotter": ["ISO 45001:7.2 Competence"],
    "Scaffolding / Fall Protection": ["ISO 45001:8.1 Operational planning"],
}


def map_standards_tags(
    hazard_label: str | None,
    barrier_types: list[str] | None = None,
    lsr_primary: str | None = None,
) -> list[str]:
    tags: list[str] = []
    if hazard_label and hazard_label in _HAZARD_TO_ISO:
        tags.extend(_HAZARD_TO_ISO[hazard_label])
    for b in barrier_types or []:
        tags.extend(_BARRIER_TO_PSM.get(b, []))
    if lsr_primary and lsr_primary != "No applicable rule":
        tags.append(f"IOGP LSR primary: {lsr_primary}")
    # Dedupe preserving order
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
