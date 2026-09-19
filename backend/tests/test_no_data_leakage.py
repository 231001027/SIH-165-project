"""Assert zero base-narrative overlap between train and test synthetic splits."""
import csv
from pathlib import Path

import pytest

from app.data.leakage import compute_split_overlap

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "reports.csv"


@pytest.mark.skipif(not CSV_PATH.exists(), reason="synthetic CSV missing")
def test_no_base_narrative_leakage_train_test():
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    result = compute_split_overlap(rows)
    assert result["leakage_pct_of_test"] == 0.0, (
        f"train/test base-narrative leakage {result['leakage_pct_of_test']:.2f}% "
        f"({result['overlap_count']} keys), e.g. {result['examples'][:1]}"
    )
    assert result["overlap_count"] == 0
