"""
CLI: measure base-narrative overlap between train and test synthetic splits.

Usage (from repo root or backend/):
  python scripts/check_data_leakage.py
  python -m scripts.check_data_leakage

Prints overlap percentage explicitly. Exit code 1 if any train/test overlap.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

# Allow running as script without installing the package
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.data.leakage import base_narrative_key, compute_split_overlap  # noqa: E402

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "reports.csv"


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: missing {CSV_PATH}")
        return 2
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    result = compute_split_overlap(rows)
    print(f"rows={result['n_rows']}")
    print(f"unique_train_bases={result['n_train']} unique_test_bases={result['n_test']} unique_val_bases={result['n_val']}")
    print(f"train_test_overlap_count={result['overlap_count']}")
    print(f"train_test_leakage_pct_of_test={result['leakage_pct_of_test']:.2f}%")
    if result["overlap_count"]:
        print("EXAMPLES:")
        for ex in result["examples"][:5]:
            print(f"  - {ex[:100]!r}")
        return 1
    print("OK: 0% base-narrative overlap between train and test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
