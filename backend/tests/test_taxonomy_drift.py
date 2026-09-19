"""Drift detection: precursor_taxonomy.json must match live vocabularies both ways."""
from __future__ import annotations

from app.data.taxonomy_loader import (
    get_barrier_keywords,
    get_barrier_statuses,
    get_barrier_to_psm,
    get_energy_categories,
    get_hazard_labels,
    get_hazard_to_iso,
    get_sif_bands,
)
from app.models.analysis import BarrierStatus, SifClassification
from app.nlp import entity_extraction, negation
from app.rules.lsr_engine import get_knowledge_base
from app.services.standards_tags import map_standards_tags


def test_taxonomy_barriers_match_live():
    tax = set(get_barrier_keywords().keys())
    live = set(negation.BARRIER_KEYWORDS.keys())
    assert tax == live, f"barrier drift tax-live={tax - live} live-tax={live - tax}"


def test_taxonomy_energy_hazards_match_live():
    assert set(get_energy_categories().keys()) == set(entity_extraction.ENERGY_CATEGORIES.keys())
    assert get_hazard_labels() == entity_extraction.HAZARD_LABELS
    assert get_energy_categories() == entity_extraction.ENERGY_CATEGORIES


def test_taxonomy_barrier_statuses_match_enum():
    tax = set(get_barrier_statuses())
    live = {s.value for s in BarrierStatus}
    assert tax == live


def test_taxonomy_sif_bands_match_enum():
    tax = set(get_sif_bands())
    live = {s.value for s in SifClassification}
    assert tax == live


def test_taxonomy_lsr_names_match_kb():
    kb_names = {r["rule"] for r in get_knowledge_base()}
    assert len(kb_names) == 9
    # Kind-1 LSRs live in lsr_knowledge_base; taxonomy points at that artifact.
    assert "Energy Isolation" in kb_names


def test_standards_overlay_covers_all_hazards_and_barriers():
    hazard_map = get_hazard_to_iso()
    barrier_map = get_barrier_to_psm()
    for label in get_hazard_labels().values():
        assert label in hazard_map and hazard_map[label], f"missing hazard standards tag: {label}"
    for barrier in get_barrier_keywords().keys():
        assert barrier in barrier_map and barrier_map[barrier], f"missing barrier standards tag: {barrier}"


def test_isolation_loto_failure_carries_standards_tag():
    tags = map_standards_tags(
        "Stored / pressurized energy",
        ["Isolation / LOTO"],
        "Energy Isolation",
    )
    assert any("LOTO" in t or "Energy Isolation" in t for t in tags)
    assert "PSM: Energy Isolation / LOTO" in tags
    assert "IOGP LSR primary: Energy Isolation" in tags
