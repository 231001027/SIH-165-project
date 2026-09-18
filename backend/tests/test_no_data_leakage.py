"""Assert zero base-narrative overlap between train and test synthetic splits."""
import csv
from pathlib import Path

import pytest

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "reports.csv"


def _base_key(narrative: str) -> str:
    text = narrative
    for p in ("Shift handover note: ", "Supervisor walkdown recorded that ", "Permit close-out comment: "):
        if text.startswith(p):
            text = text[len(p):]
    for s in (
        " Event logged near end of day shift.",
        " Observed during morning toolbox talk follow-up.",
        " Equipment tag referenced in the PTW package.",
        " (follow-up observation #2)",
        " (follow-up observation #3)",
    ):
        if text.endswith(s):
            text = text[: -len(s)]
    return text.strip().rstrip(".")


@pytest.mark.skipif(not CSV_PATH.exists(), reason="synthetic CSV missing")
def test_no_base_narrative_leakage_train_test():
    train, test = set(), set()
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = _base_key(row["narrative"])
            if row.get("split") == "train":
                train.add(key)
            elif row.get("split") == "test":
                test.add(key)
    overlap = train & test
    assert not overlap, f"train/test base-narrative overlap ({len(overlap)} keys), e.g. {next(iter(overlap))[:80]!r}"
