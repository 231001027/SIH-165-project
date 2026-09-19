"""Shared base-narrative normalization for leakage checks (CLI + pytest)."""
from __future__ import annotations

from collections import defaultdict


def base_narrative_key(narrative: str) -> str:
    """Normalize narrative for leakage grouping (strip variant prefixes/suffixes)."""
    text = narrative or ""
    for p in (
        "Shift handover note: ",
        "Supervisor walkdown recorded that ",
        "Permit close-out comment: ",
    ):
        if text.startswith(p):
            text = text[len(p) :]
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


def compute_split_overlap(rows: list[dict]) -> dict:
    by_split: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        key = base_narrative_key(row.get("narrative") or "")
        split = row.get("split") or ""
        if split:
            by_split[split].add(key)
    train = by_split.get("train", set())
    test = by_split.get("test", set())
    val = by_split.get("val", set())
    overlap = train & test
    pct = (100.0 * len(overlap) / len(test)) if test else 0.0
    return {
        "n_rows": len(rows),
        "n_train": len(train),
        "n_test": len(test),
        "n_val": len(val),
        "overlap_count": len(overlap),
        "leakage_pct_of_test": pct,
        "examples": sorted(overlap),
    }
