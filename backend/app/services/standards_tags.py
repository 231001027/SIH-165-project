"""Secondary ISO 45001 / PSM-inspired tags mapped from extracted fields.

These are prototype design labels for dashboard context — they do NOT replace
IOGP Life-Saving Rules as the primary classifier output.

Maps are loaded from precursor_taxonomy.json secondary_overlays so they cannot
drift from live hazard / barrier vocabularies.
"""
from __future__ import annotations

from app.data.taxonomy_loader import get_barrier_to_psm, get_hazard_to_iso


def map_standards_tags(
    hazard_label: str | None,
    barrier_types: list[str] | None = None,
    lsr_primary: str | None = None,
) -> list[str]:
    hazard_to_iso = get_hazard_to_iso()
    barrier_to_psm = get_barrier_to_psm()
    tags: list[str] = []
    if hazard_label and hazard_label in hazard_to_iso:
        tags.extend(hazard_to_iso[hazard_label])
    for b in barrier_types or []:
        tags.extend(barrier_to_psm.get(b, []))
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
