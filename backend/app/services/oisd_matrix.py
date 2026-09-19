"""OISD-style Consequence-Probability matrix (Hi-Po near-miss lens).

Kind-3 prototype inspired by OISD GDN-206 near-miss / Hi-Po concepts and
IOCL-style consequence-probability triage. This is NOT claimed as a verbatim
copy of any published OISD matrix cell-for-cell. It sits ALONGSIDE the existing
SIF risk_score components — it does not replace them.
"""
from __future__ import annotations

from typing import Any

CONSEQUENCE_LEVELS = {
    1: "Negligible",   # no injury, no property damage
    2: "Minor",        # first-aid injury, minor damage
    3: "Moderate",     # lost-time injury, moderate damage
    4: "Major",        # serious/irreversible injury, major damage
    5: "Catastrophic", # single/multiple fatality potential
}

PROBABILITY_LEVELS = {
    1: "Rare",            # has not been observed in the industry
    2: "Unlikely",        # has occurred rarely in the industry
    3: "Possible",        # has occurred several times in the industry
    4: "Likely",          # has occurred in the operating company
    5: "Almost Certain",  # recurring at this site/activity
}

# 5x5 grid -> risk band (OISD-STYLE prototype grid).
RISK_MATRIX = {
    (5, 5): "HIGH", (5, 4): "HIGH", (5, 3): "HIGH", (5, 2): "MEDIUM", (5, 1): "MEDIUM",
    (4, 5): "HIGH", (4, 4): "HIGH", (4, 3): "MEDIUM", (4, 2): "MEDIUM", (4, 1): "LOW",
    (3, 5): "HIGH", (3, 4): "MEDIUM", (3, 3): "MEDIUM", (3, 2): "LOW", (3, 1): "LOW",
    (2, 5): "MEDIUM", (2, 4): "MEDIUM", (2, 3): "LOW", (2, 2): "LOW", (2, 1): "LOW",
    (1, 5): "MEDIUM", (1, 4): "LOW", (1, 3): "LOW", (1, 2): "LOW", (1, 1): "LOW",
}

_HIGH_ENERGY = frozenset({"PRESSURE", "ELECTRICAL", "MECHANICAL", "CHEMICAL", "GRAVITY"})
_CRITICAL_BARRIERS = frozenset({
    "Isolation / LOTO",
    "Permit-to-Work",
    "Gas Detection",
    "Fall Protection",
    "Guarding",
})
_GAP_STATUSES = frozenset({"MISSING", "FAILED", "BYPASSED", "NOT_VERIFIED"})


def classify_hipo(consequence: int, probability: int) -> dict:
    """Returns band / is_hipo / rationale.

    is_hipo=True only if band=='HIGH' AND consequence >= 4
    (fatality-potential threshold per OISD Hi-Po definition).
    """
    if consequence not in CONSEQUENCE_LEVELS or probability not in PROBABILITY_LEVELS:
        raise ValueError(f"Invalid consequence/probability: {consequence}, {probability}")
    band = RISK_MATRIX[(consequence, probability)]
    is_hipo = band == "HIGH" and consequence >= 4
    rationale = (
        f"Consequence={CONSEQUENCE_LEVELS[consequence]}, "
        f"Probability={PROBABILITY_LEVELS[probability]} → {band}"
    )
    if is_hipo:
        rationale += " (Hi-Po: fatality-potential threshold met)"
    return {
        "consequence": consequence,
        "probability": probability,
        "consequence_level": CONSEQUENCE_LEVELS[consequence],
        "probability_level": PROBABILITY_LEVELS[probability],
        "band": band,
        "is_hipo": is_hipo,
        "rationale": rationale,
        "_source": "OISD-style Kind-3 prototype matrix (not a verbatim OISD publication extract)",
    }


def derive_consequence_probability(
    *,
    energy_categories: list[str] | None = None,
    exposure_proximity: str | None = None,
    barrier_findings: list[Any] | None = None,
    repeat_precursor_count: int = 0,
    sif_classification: str | None = None,
) -> tuple[int, int]:
    """Map existing pipeline outputs → (consequence 1-5, probability 1-5).

    Auditable deterministic rules — no new user inputs.
    """
    cats = set(energy_categories or [])
    proximity = (exposure_proximity or "NONE").upper()
    findings = barrier_findings or []

    def _barrier_type(bf) -> str:
        return bf.barrier_type if hasattr(bf, "barrier_type") else bf.get("barrier_type", "")

    def _barrier_status(bf) -> str:
        return bf.status if hasattr(bf, "status") else bf.get("status", "")

    critical_gap = any(
        _barrier_type(bf) in _CRITICAL_BARRIERS and _barrier_status(bf) in _GAP_STATUSES
        for bf in findings
    )
    any_gap = any(_barrier_status(bf) in _GAP_STATUSES for bf in findings)
    has_high_energy = bool(cats & _HIGH_ENERGY)
    has_motion = "MOTION" in cats
    high_exposure = proximity in ("HIGH", "MEDIUM")

    # --- Consequence ---
    if sif_classification == "NON_SIF" and not has_high_energy and not critical_gap:
        consequence = 1
    elif has_high_energy and critical_gap and high_exposure:
        consequence = 5
    elif has_high_energy and critical_gap:
        consequence = 4
    elif has_high_energy and high_exposure:
        consequence = 4
    elif has_high_energy or (any_gap and high_exposure):
        consequence = 3
    elif has_motion or any_gap or proximity == "LOW":
        consequence = 2
    else:
        consequence = 1

    # --- Probability (from repeat precursors + industry-plausible energy) ---
    count = int(repeat_precursor_count or 0)
    if count >= 3:
        probability = 5
    elif count == 2:
        probability = 4
    elif count == 1:
        probability = 3
    elif count == 0 and has_high_energy:
        probability = 2
    else:
        probability = 1

    return consequence, probability


def classify_from_pipeline(
    *,
    energy_categories: list[str] | None = None,
    exposure_proximity: str | None = None,
    barrier_findings: list[Any] | None = None,
    repeat_precursor_count: int = 0,
    sif_classification: str | None = None,
) -> dict:
    c, p = derive_consequence_probability(
        energy_categories=energy_categories,
        exposure_proximity=exposure_proximity,
        barrier_findings=barrier_findings,
        repeat_precursor_count=repeat_precursor_count,
        sif_classification=sif_classification,
    )
    return classify_hipo(c, p)
