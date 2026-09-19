"""Load precursor_taxonomy.json once — single source of truth for live vocabularies.

Kind-1 IOGP LSR names live in lsr_knowledge_base.json (referenced by the taxonomy).
Kind-3 energy/hazard/barrier vocabularies and standards overlays live here so
Python modules cannot drift from the JSON again.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_TAXONOMY_PATH = Path(__file__).resolve().parent / "precursor_taxonomy.json"


@lru_cache(maxsize=1)
def load_taxonomy() -> dict:
    with _TAXONOMY_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_energy_categories() -> dict[str, list[str]]:
    return dict(load_taxonomy()["supporting_vocabularies"]["energy_categories"]["items"])


def get_hazard_labels() -> dict[str, str]:
    return dict(load_taxonomy()["supporting_vocabularies"]["hazard_labels"]["items"])


def get_energy_source_labels() -> dict[str, str]:
    return dict(load_taxonomy()["supporting_vocabularies"]["energy_source_labels"]["items"])


def get_barrier_keywords() -> dict[str, list[str]]:
    return dict(load_taxonomy()["supporting_vocabularies"]["barrier_types"]["items"])


def get_barrier_statuses() -> list[str]:
    return list(load_taxonomy()["supporting_vocabularies"]["barrier_statuses"]["items"])


def get_sif_bands() -> list[str]:
    return list(load_taxonomy()["supporting_vocabularies"]["sif_bands"]["items"])


def get_hazard_to_iso() -> dict[str, list[str]]:
    return dict(load_taxonomy()["secondary_overlays"]["hazard_to_iso"])


def get_barrier_to_psm() -> dict[str, list[str]]:
    return dict(load_taxonomy()["secondary_overlays"]["barrier_to_psm"])
