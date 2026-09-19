"""Canonical statement of reference-corpus composition (single source for docs/UI).

Attempted DGMS annual-report PDF extraction (dgms.gov.in / dgms.net) during this
prototype: portal fetch timed out / case-study PDFs were not available in
machine-readable form for reliable citation. Therefore REAL_DGMS count is 0 —
we do NOT expand fabricated DGMS-style rows to compensate.
"""

CORPUS_PROVENANCE_ENUM = ("REAL_OSHA", "REAL_DGMS", "SYNTHETIC_DEMO")

# Counts must match data/reference_corpus/incidents.json (enforced by tests).
CORPUS_PROVENANCE_STATEMENT = (
    "Reference corpus composition: 12 REAL_OSHA (OSHA FatalFacts / news releases "
    "with resolvable citation URLs); 0 REAL_DGMS (DGMS annual-report case studies "
    "were not available in machine-readable, citable form for this prototype — "
    "attempted dgms.gov.in / dgms.net; do not treat portal-grounded demos as "
    "verbatim DGMS extracts); 3 SYNTHETIC_DEMO (team-authored India-mining-style "
    "illustrative narratives, clearly labelled, not real DGMS cases)."
)

PROVENANCE_BADGE_LABELS = {
    "REAL_OSHA": "Real OSHA citation",
    "REAL_DGMS": "Real DGMS citation",
    "SYNTHETIC_DEMO": "Synthetic demo (not a real extract)",
}
