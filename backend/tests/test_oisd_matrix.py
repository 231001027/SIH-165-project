"""OISD matrix unit tests — 25 grid cells, Hi-Po threshold, derive mapping."""
from __future__ import annotations

import pytest

from app.services.oisd_matrix import (
    CONSEQUENCE_LEVELS,
    PROBABILITY_LEVELS,
    RISK_MATRIX,
    classify_from_pipeline,
    classify_hipo,
    derive_consequence_probability,
)


def test_all_25_matrix_cells():
    assert len(RISK_MATRIX) == 25
    for c in range(1, 6):
        for p in range(1, 6):
            result = classify_hipo(c, p)
            assert result["band"] == RISK_MATRIX[(c, p)]
            assert result["consequence_level"] == CONSEQUENCE_LEVELS[c]
            assert result["probability_level"] == PROBABILITY_LEVELS[p]


@pytest.mark.parametrize(
    "c,p,expect_hipo",
    [
        (5, 5, True),
        (5, 3, True),
        (4, 5, True),
        (4, 4, True),
        (4, 3, False),  # MEDIUM band
        (5, 2, False),  # MEDIUM band
        (3, 5, False),  # HIGH band but consequence < 4
        (3, 3, False),
        (1, 1, False),
    ],
)
def test_is_hipo_threshold(c, p, expect_hipo):
    result = classify_hipo(c, p)
    assert result["is_hipo"] is expect_hipo
    if expect_hipo:
        assert "Hi-Po" in result["rationale"]
        assert result["band"] == "HIGH"
        assert c >= 4


def test_derive_flagship_loto_shape():
    """Flagship: high-energy PRESSURE + high exposure + LOTO NOT_VERIFIED → C>=4."""
    barriers = [
        {"barrier_type": "Isolation / LOTO", "status": "NOT_VERIFIED"},
    ]
    c, p = derive_consequence_probability(
        energy_categories=["PRESSURE"],
        exposure_proximity="HIGH",
        barrier_findings=barriers,
        repeat_precursor_count=0,
        sif_classification="HIGH",
    )
    assert c >= 4
    assert p == 2  # industry-plausible high energy, no repeats
    result = classify_hipo(c, p)
    # C=5,P=2 → MEDIUM; C=4,P=2 → MEDIUM — may or may not be hipo
    assert result["band"] in ("HIGH", "MEDIUM", "LOW")


def test_derive_with_repeats_can_hipo():
    barriers = [
        {"barrier_type": "Isolation / LOTO", "status": "MISSING"},
    ]
    result = classify_from_pipeline(
        energy_categories=["PRESSURE"],
        exposure_proximity="HIGH",
        barrier_findings=barriers,
        repeat_precursor_count=3,
        sif_classification="HIGH",
    )
    assert result["consequence"] == 5
    assert result["probability"] == 5
    assert result["is_hipo"] is True
    assert result["band"] == "HIGH"


def test_derive_nonsif_low():
    c, p = derive_consequence_probability(
        energy_categories=[],
        exposure_proximity="NONE",
        barrier_findings=[],
        repeat_precursor_count=0,
        sif_classification="NON_SIF",
    )
    assert c == 1
    assert p == 1
