"""Reference corpus provenance tagging must stay honest and complete."""
from __future__ import annotations

import json
from pathlib import Path

from app.data.corpus_provenance import CORPUS_PROVENANCE_ENUM, CORPUS_PROVENANCE_STATEMENT

CORPUS_PATH = Path(__file__).resolve().parents[2] / "data" / "reference_corpus" / "incidents.json"


def test_every_incident_has_valid_provenance():
    assert CORPUS_PATH.exists()
    entries = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert entries
    for i, e in enumerate(entries):
        prov = e.get("provenance")
        assert prov in CORPUS_PROVENANCE_ENUM, f"row {i}: invalid provenance {prov!r}"
        assert (e.get("narrative") or "").strip()
        assert (e.get("citation_label") or "").strip()
        url = (e.get("citation_url") or "").strip()
        if prov.startswith("REAL_"):
            assert url.startswith("http://") or url.startswith("https://"), (
                f"row {i}: REAL_* rows require resolvable citation_url, got {url!r}"
            )


def test_provenance_counts_match_statement():
    entries = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    counts = {k: 0 for k in CORPUS_PROVENANCE_ENUM}
    for e in entries:
        counts[e["provenance"]] += 1
    assert counts["REAL_OSHA"] == 12
    assert counts["REAL_DGMS"] == 0
    assert counts["SYNTHETIC_DEMO"] == 3
    assert "12 REAL_OSHA" in CORPUS_PROVENANCE_STATEMENT
    assert "0 REAL_DGMS" in CORPUS_PROVENANCE_STATEMENT
    assert "3 SYNTHETIC_DEMO" in CORPUS_PROVENANCE_STATEMENT
