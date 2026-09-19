"""
Negation-aware Barrier Failure Engine (blueprint Part 3.7).

This is one of the project's core differentiators: "LOTO was correctly
applied" must NOT be tagged as a failure, while "LOTO was not applied" must
be. The blueprint's ideal is dependency-parse-based negation scope; for a
dependency parse without a heavy model dependency we approximate it with:

  1. sentence split -> clause split (on but/however/although) so an
     affirmative clause elsewhere in the sentence cannot leak into a
     negative clause (or vice versa) for the SAME barrier mention;
  2. for each barrier keyword hit, search a bounded token window *within
     its own clause* for the strongest matching status pattern, checked in
     a fixed priority order (see STATUS_PATTERNS below);
  3. default to NOT_VERIFIED/UNKNOWN when no polarity cue is found near a
     barrier mention, per the project's abstention principle -- the engine
     never *guesses* that a barrier failed just because it was mentioned.

This is deliberately simpler than a full dependency parser, but it is
explainable, fast, fully offline, and directly testable against the
blueprint's own worked examples (see tests/test_negation.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.data.taxonomy_loader import get_barrier_keywords
from app.nlp.preprocess import split_sentences, split_clauses

# Loaded from precursor_taxonomy.json (single source of truth — do not hardcode here).
BARRIER_KEYWORDS: dict[str, list[str]] = get_barrier_keywords()

# Checked in this order -- first match near the barrier mention wins.
# Each entry: (status, pattern_tag, [regex fragments])
STATUS_PATTERNS: list[tuple[str, str, list[str]]] = [
    ("BYPASSED", "EXPLICIT_BYPASS", [
        r"bypass(?:ed)?", r"overrid(?:den|e)", r"defeat(?:ed)?", r"disabled", r"skipped",
        r"overridden",
    ]),
    ("NOT_VERIFIED", "PROCEEDED_WITHOUT_VERIFICATION", [
        r"before confirming", r"before verifying", r"before checking",
        r"without confirming", r"without verifying", r"without checking",
        # Generic "work proceeded before X was <done>" pattern -- covers phrasing
        # like "before the gas test was completed" / "before the permit was signed"
        # where the specific verb (completed/signed/confirmed/...) would otherwise
        # be matched as a bare affirmative cue further down this priority list.
        r"before\s+(?:the\s+)?[\w\s]{0,35}?(?:was|were|is|are|had been)\s+"
        r"(?:completed|confirmed|verified|checked|signed|finished|issued|established)",
    ]),
    ("NOT_VERIFIED", "EXPLICIT_UNVERIFIED", [
        r"not verified", r"unverified", r"not confirmed", r"not checked",
        r"could not be verified", r"was not (?:yet )?verified",
    ]),
    ("MISSING", "EXPLICIT_MISSING", [
        r"not applied", r"not (?:in place|used|worn|present)", r"no isolation", r"no permit",
        r"no ppe", r"no guard(?:ing)?", r"no barrier", r"without (?:a |any )?(?:isolation|permit|"
        r"ppe|guard|harness|lanyard|standby attendant|documented lift plan|fire watch|gas test)",
        r"absent", r"\bmissing\b", r"did not use", r"was not established", r"not established",
        r"was not (?:applied|used|worn|in place|issued)", r"wasn'?t (?:applied|used|worn|in place)",
        r"failed to (?:apply|use|wear|don)", r"began without", r"proceeded without",
    ]),
    ("FAILED", "EXPLICIT_FAILURE", [
        r"failed", r"did not work", r"malfunction(?:ed)?", r"gave way", r"ineffective",
        r"broke", r"ruptured unexpectedly",
    ]),
    ("PRESENT_EFFECTIVE", "EXPLICIT_AFFIRMATIVE", [
        r"correctly applied", r"properly applied", r"was applied", r"in place",
        r"verified", r"confirmed", r"completed", r"effective", r"successfully",
        r"was in place", r"was worn", r"was used correctly", r"functioned as intended",
        r"\bwore\b", r"\bworn\b",
        # Additional real-world compliance phrasing (a barrier can be reported as
        # working without ever using the word "applied"/"verified" -- e.g. "the
        # exclusion zone was properly established and enforced"). Each of these is
        # safely ordered AFTER the negative-status tiers above, so "was NOT
        # established"/"without a documented lift plan"-style negations are still
        # caught first and never reach this tier.
        r"established", r"enforced", r"maintained", r"\bposted\b", r"reviewed",
        r"\bfollowed\b", r"within inspection", r"barricaded", r"\bvalid\b",
    ]),
]

_WINDOW_CHARS = 60  # characters of context searched to either side of the barrier mention


@dataclass
class BarrierFinding:
    barrier_type: str
    status: str
    evidence_text: str
    confidence: float
    pattern_tag: str = ""
    critical_gap: bool = False  # True for the "proceeded before verifying" pattern


def _find_status_in_clause(clause: str, keyword_span: tuple[int, int]) -> tuple[str, str, str] | None:
    """Search `clause` around keyword_span for the first matching status pattern.
    Affirmative patterns are checked in the same priority pass so that, e.g.,
    'isolation confirmed' does not also match a stray negative elsewhere."""
    start = max(0, keyword_span[0] - _WINDOW_CHARS)
    end = min(len(clause), keyword_span[1] + _WINDOW_CHARS)
    window = clause[start:end]
    for status, pattern_tag, fragments in STATUS_PATTERNS:
        for frag in fragments:
            m = re.search(frag, window, re.IGNORECASE)
            if m:
                return status, pattern_tag, window.strip()
    return None


def analyze_barriers(narrative: str) -> list[BarrierFinding]:
    findings: dict[str, BarrierFinding] = {}
    for sentence in split_sentences(narrative):
        for clause in split_clauses(sentence):
            lower_clause = clause.lower()
            for barrier_type, keywords in BARRIER_KEYWORDS.items():
                for kw in keywords:
                    pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
                    match = pattern.search(lower_clause)
                    if not match:
                        continue
                    result = _find_status_in_clause(clause, match.span())
                    if result:
                        status, pattern_tag, evidence = result
                    else:
                        status, pattern_tag, evidence = "NOT_VERIFIED", "NO_POLARITY_CUE", clause.strip()

                    confidence = 0.9 if result else 0.4
                    critical_gap = pattern_tag == "PROCEEDED_WITHOUT_VERIFICATION"

                    existing = findings.get(barrier_type)
                    # Prefer the highest-confidence / most specific finding per barrier type
                    if existing is None or confidence > existing.confidence:
                        findings[barrier_type] = BarrierFinding(
                            barrier_type=barrier_type,
                            status=status,
                            evidence_text=evidence,
                            confidence=confidence,
                            pattern_tag=pattern_tag,
                            critical_gap=critical_gap,
                        )
                    break  # one keyword hit per barrier type per clause is enough
    return list(findings.values())
