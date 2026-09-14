"""
IOGP Life-Saving Rule classification (blueprint Part 3.4).

Scores each of the 9 rules by trigger-concept keyword overlap plus a
required-energy-category gate, so a bare mention of "height" cannot alone
trigger Working at Height (Part 3.4's own guard-rail example) -- the rule
only scores if a GRAVITY-category energy/hazard cue was actually extracted
for the report. If no rule clears the minimum-evidence threshold, the engine
returns "No applicable rule", matching IOGP's own taxonomy (a report is not
forced into one of the 9 rules just because it exists).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.nlp.entity_extraction import ExtractedEntities
from app.nlp.lexicon import tag_canonical_terms

_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "lsr_knowledge_base.json"
with open(_KB_PATH, "r", encoding="utf-8") as f:
    _KB = json.load(f)["rules"]

NO_APPLICABLE_RULE = "No applicable rule"
MIN_SCORE_THRESHOLD = 0.18


@dataclass
class LsrCandidate:
    rule: str
    score: float
    evidence: list[str] = field(default_factory=list)


@dataclass
class LsrResult:
    primary: str
    primary_confidence: float
    secondary: str | None
    secondary_confidence: float | None
    evidence: list[str]
    candidates: list[LsrCandidate]


def _score_rule(rule_def: dict, narrative_lower: str, tags: set[str], entities: ExtractedEntities) -> LsrCandidate:
    evidence = []
    hits = 0
    total_terms = max(len(rule_def["trigger_concepts"]), 1)
    for term in rule_def["trigger_concepts"]:
        # Hyphens normalized on both sides so a KB term like "de-energized"
        # still matches text phrased "de energized" (or vice versa).
        term_norm = term.lower().replace("-", " ")
        if term_norm in narrative_lower:
            hits += 1
            evidence.append(term)
    keyword_score = hits / total_terms

    lexicon_bonus = 0.0
    for tag in rule_def.get("required_lexicon_tags", []):
        if tag in tags:
            lexicon_bonus = 0.35
            break

    # The energy-category gate exists to stop a BARE, context-free keyword
    # (blueprint Part 3.4's own "height" example) from forcing a match on its
    # own. But the domain lexicon (app/nlp/lexicon.py) requires a specific,
    # curated phrase for its tag to fire at all -- that is already the kind of
    # real context the gate is trying to demand, just expressed a different
    # way, so a lexicon hit is treated as an equally valid way to pass the
    # gate. Without this, a report that clearly uses the rule's own domain
    # vocabulary (e.g. "isolation valve", "rigging inspection") could still be
    # suppressed to 0.15x just because no separate hazard/energy keyword also
    # happened to appear in the same narrative.
    required_categories = rule_def.get("required_energy_categories", [])
    if required_categories:
        gate_passed = any(cat in entities.energy_categories for cat in required_categories) or lexicon_bonus > 0
        gate_multiplier = 1.0 if gate_passed else 0.15
    else:
        gate_multiplier = 1.0

    raw_score = min(1.0, keyword_score * 1.5 + lexicon_bonus) * gate_multiplier
    return LsrCandidate(rule=rule_def["rule"], score=round(raw_score, 4), evidence=evidence)


def classify_lsr(narrative: str, entities: ExtractedEntities) -> LsrResult:
    narrative_lower = narrative.lower().replace("-", " ")
    tags = tag_canonical_terms(narrative)

    candidates = [_score_rule(rule_def, narrative_lower, tags, entities) for rule_def in _KB]
    candidates.sort(key=lambda c: c.score, reverse=True)

    top = candidates[0]
    if top.score < MIN_SCORE_THRESHOLD:
        return LsrResult(
            primary=NO_APPLICABLE_RULE,
            primary_confidence=round((1 - top.score) * 40, 1),
            secondary=None,
            secondary_confidence=None,
            evidence=[],
            candidates=candidates,
        )

    primary_confidence = round(min(99.0, top.score * 100), 1)
    secondary = None
    secondary_confidence = None
    if len(candidates) > 1:
        second = candidates[1]
        if second.score >= MIN_SCORE_THRESHOLD and second.score >= top.score * 0.6:
            secondary = second.rule
            secondary_confidence = round(min(99.0, second.score * 100), 1)

    return LsrResult(
        primary=top.rule,
        primary_confidence=primary_confidence,
        secondary=secondary,
        secondary_confidence=secondary_confidence,
        evidence=top.evidence,
        candidates=candidates,
    )


def get_knowledge_base() -> list[dict]:
    return _KB
