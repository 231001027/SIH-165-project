"""
Deterministic rule engine (blueprint Part 2.3 / 5.4 "Rule engine" layer).

Produces the auditable, always-on baseline signal that keeps functioning even
if the ML classifier or LLM layer is degraded. Combines extracted entities
and barrier findings into normalized risk components (0-1) and multi-label
reason codes. This module never sees the LLM; it is pure deterministic code,
inspectable and unit-testable (tests/test_sif_classifier.py,
tests/test_barrier_engine.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.nlp.entity_extraction import ExtractedEntities
from app.nlp.negation import BarrierFinding
from app.rules.barrier_rules import barrier_failure_component

EXPOSURE_COMPONENT = {"HIGH": 0.9, "MEDIUM": 0.55, "LOW": 0.3, "NONE": 0.05}

# Prototype activity-criticality base rates, loosely informed by IOGP's own
# published fatal-incident LSR allocation ranking (Line of Fire, Confined
# Space, Bypassing Safety Controls, Driving, Energy Isolation lead the list --
# blueprint Part 0.2.B) -- NOT an official weighting, our own design choice.
ACTIVITY_CRITICALITY_BY_LSR = {
    "Line of Fire": 0.85,
    "Confined Space": 0.8,
    "Bypassing Safety Controls": 0.75,
    "Driving": 0.6,
    "Energy Isolation": 0.75,
    "Hot Work": 0.7,
    "Safe Mechanical Lifting": 0.65,
    "Work Authorization": 0.5,
    "Working at Height": 0.75,
    "No applicable rule": 0.25,
}

REASON_CODE_RULES = [
    ("HIGH_ENERGY_SOURCE", lambda ctx: len(ctx["entities"].energy_categories) > 0),
    ("WORKER_EXPOSURE", lambda ctx: ctx["entities"].exposure_proximity in ("HIGH", "MEDIUM")),
    ("CRITICAL_BARRIER_FAILURE", lambda ctx: ctx["barrier_component"] >= 0.75),
    ("UNCONTROLLED_RELEASE", lambda ctx: "PRESSURE" in ctx["entities"].energy_categories
        and ctx["barrier_component"] >= 0.5),
    ("LINE_OF_FIRE_EXPOSURE", lambda ctx: ctx["lsr_primary"] == "Line of Fire"),
    ("CONFINED_SPACE_HAZARD", lambda ctx: ctx["lsr_primary"] == "Confined Space"),
    ("FALL_FROM_HEIGHT_POTENTIAL", lambda ctx: ctx["lsr_primary"] == "Working at Height"
        or "GRAVITY" in ctx["entities"].energy_categories),
    ("MOBILE_EQUIPMENT_PROXIMITY", lambda ctx: "MOTION" in ctx["entities"].energy_categories),
    ("ELECTRICAL_ENERGY_EXPOSURE", lambda ctx: "ELECTRICAL" in ctx["entities"].energy_categories),
    ("REPEAT_PRECURSOR", lambda ctx: ctx["repeat_precursor_count"] >= 2),
]


@dataclass
class RuleEngineResult:
    hazard_energy_component: float
    worker_exposure_component: float
    barrier_failure_component: float
    activity_criticality_component: float
    repeat_precursor_component: float
    worst_barrier_type: str | None
    reason_codes: list[str] = field(default_factory=list)
    rule_confidence: float = 0.0  # how much evidence the rule engine itself found (0-100)


def run_rule_engine(
    entities: ExtractedEntities,
    barrier_findings: list[BarrierFinding],
    lsr_primary: str,
    repeat_precursor_count: int,
) -> RuleEngineResult:
    hazard_energy = min(1.0, 0.35 * len(entities.energy_categories)) if entities.energy_categories else 0.0
    exposure = EXPOSURE_COMPONENT.get(entities.exposure_proximity, 0.05)
    barrier_component, worst_barrier = barrier_failure_component(barrier_findings)
    activity_criticality = ACTIVITY_CRITICALITY_BY_LSR.get(lsr_primary, 0.4)
    repeat_component = min(1.0, repeat_precursor_count / 5.0)

    ctx = {
        "entities": entities,
        "barrier_component": barrier_component,
        "lsr_primary": lsr_primary,
        "repeat_precursor_count": repeat_precursor_count,
    }
    reason_codes = [code for code, predicate in REASON_CODE_RULES if predicate(ctx)]

    # Rule-engine's own evidence-density confidence: how many independent
    # signals fired. This is fused with the ML classifier probability later
    # (see app/services/analysis_service.py) rather than used alone.
    evidence_signals = sum([
        1 if entities.energy_categories else 0,
        1 if entities.exposure_proximity in ("HIGH", "MEDIUM") else 0,
        1 if barrier_findings else 0,
        1 if entities.activity_guess else 0,
    ])
    rule_confidence = min(100.0, evidence_signals * 22.0)

    return RuleEngineResult(
        hazard_energy_component=round(hazard_energy, 3),
        worker_exposure_component=round(exposure, 3),
        barrier_failure_component=round(barrier_component, 3),
        activity_criticality_component=round(activity_criticality, 3),
        repeat_precursor_component=round(repeat_component, 3),
        worst_barrier_type=worst_barrier,
        reason_codes=reason_codes,
        rule_confidence=round(rule_confidence, 1),
    )
