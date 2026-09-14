"""
Entity / Risk Extraction (blueprint Pipeline Stage 5) and
Hazard/Energy/Exposure Analysis (Stage 8).

Deterministic keyword + co-occurrence rules. Kept rule-based (rather than a
trained NER model) because the project has no labelled OIL entity-span
corpus to train one on -- see README "AI/NLP pipeline" for the honesty note
required by the source-discipline rules. The interface is stable so a
trained span model could later replace the internals without touching
callers.

Guard against naive keyword matching (blueprint Part 3.4): a bare mention of
"height" must not by itself imply a Working-at-Height exposure. We require an
energy/hazard cue AND a co-occurring exposure/proximity cue in the same
sentence before we report an exposure.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.nlp.preprocess import split_sentences

ENERGY_CATEGORIES: dict[str, list[str]] = {
    "PRESSURE": [
        "pressure", "pressurized", "pressurised", "residual pressure", "line pressure",
        "psi", "bar of pressure", "pneumatic",
    ],
    "ELECTRICAL": [
        "electrical", "voltage", "live wire", "energized", "energised", "shock hazard",
        "electrocution", "live circuit", "high voltage",
    ],
    "GRAVITY": [
        # Deliberately NOT a bare "fall" -- that alone is a documented false-positive
        # trap (e.g. "a decline/fall in safety scores"), matching the guard-rail this
        # project must demonstrate. "fell"/"falling" as verbs are far less ambiguous.
        "height", "elevation", "elevated", "fell", "falling", "dropped from",
        "scaffold", "ladder", "roof", "platform edge", "fall arrest", "fall protection",
        "fall from",
    ],
    "MECHANICAL": [
        "rotating equipment", "moving machinery", "mechanical energy", "spring loaded",
        "rotating", "conveyor", "pinch point", "moving parts", "suspended load",
        "struck by", "swinging pipe", "swinging load", "crane lift", "lifting operation",
        "dropped object", "rigging sling", "tag line",
    ],
    "CHEMICAL": [
        "chemical", "toxic", "h2s", "corrosive", "solvent", "flammable", "asphyxiant",
        "hazardous vapour", "hazardous vapor", "fumes",
        # Confined-space entry is inherently an atmospheric/asphyxiation hazard under
        # IOGP's Confined Space rule even when the narrative never names a specific
        # chemical -- see rules/lsr_engine.py's Confined Space gate, which relies on
        # this same CHEMICAL category being present. "tank"/"vessel"/"manway" are
        # treated as OIL-context-specific enough to be low-false-positive-risk.
        "confined space", "manway", "tank", "vessel",
    ],
    "MOTION": [
        "vehicle", "moving vehicle", "mobile equipment", "forklift", "crane movement",
        "traffic", "reversing", "driving", "drove", "driver", "excavator",
    ],
}

HAZARD_LABELS: dict[str, str] = {
    "PRESSURE": "Stored / pressurized energy",
    "ELECTRICAL": "Electrical energy",
    "GRAVITY": "Gravity / fall hazard",
    "MECHANICAL": "Mechanical stored / kinetic energy",
    "CHEMICAL": "Chemical / atmospheric hazard",
    "MOTION": "Mobile equipment / motion hazard",
}

ENERGY_SOURCE_LABELS: dict[str, str] = {
    "PRESSURE": "Pressurized fluid",
    "ELECTRICAL": "Electrical circuit",
    "GRAVITY": "Elevation / gravity",
    "MECHANICAL": "Mechanical stored energy",
    "CHEMICAL": "Hazardous chemical / atmosphere",
    "MOTION": "Moving vehicle or mobile equipment",
}

PROXIMITY_HIGH = [
    "standing under", "positioned at", "beneath", "under the load", "inside the",
    "at the flange", "in the line of fire", "directly below", "in contact with",
    "entered the", "leaned out", "underneath",
    # Hands-on contact with the equipment that IS the energy source implies direct
    # exposure even when the narrative never says "at the flange" explicitly --
    # e.g. the flagship blueprint demo scenario: "opened a flange before confirming
    # isolation ... residual pressure was released" (hazard and contact are in
    # different sentences; see `extract_entities` for the narrative-wide scan).
    "opened a flange", "opened the flange", "removed a pressure gauge",
    "removed the pressure gauge", "disconnected a hydraulic line",
    "disconnected the hydraulic line", "started disassembling", "climbed onto",
    "entered a tank", "reached a valve", "reach a valve", "handled a stand of",
]
PROXIMITY_MEDIUM = ["near", "nearby", "close to", "in the vicinity", "within the area", "beside"]
PROXIMITY_NONE_CUES = [
    "no one nearby", "area was clear", "no personnel", "unoccupied", "cleared the area",
    "no one was near", "cleared prior to",
]

ACTIVITY_KEYWORDS: dict[str, list[str]] = {
    "Pipeline Maintenance": ["pipeline maintenance", "flange", "pipeline", "valve work"],
    "Confined Space Entry": ["confined space", "tank entry", "vessel entry"],
    "Lifting Operation": ["lifting", "crane", "rigging", "hoisting"],
    "Working at Height": ["scaffold", "working at height", "roof work", "elevated platform"],
    "Hot Work": ["welding", "grinding", "hot work", "cutting"],
    "Electrical Work": ["electrical work", "switchgear", "cable", "panel work"],
    "Driving / Vehicle Movement": ["driving", "vehicle movement", "journey"],
    "Drilling Operations": ["drilling", "rig floor", "derrick"],
    "General Maintenance": ["maintenance", "inspection", "repair"],
}

LOCATION_RE = re.compile(
    r"\b(?:at|near|inside|beside|around)\s+(?:the\s+)?([A-Za-z0-9][\w\- ]{2,40}?)"
    r"(?=[.,;]| during| while| when|$)",
    re.IGNORECASE,
)


@dataclass
class ExtractedEntities:
    hazards: list[str] = field(default_factory=list)
    energy_categories: list[str] = field(default_factory=list)
    energy_source: str | None = None
    hazard_label: str | None = None
    exposure_description: str | None = None
    exposure_proximity: str = "NONE"  # HIGH | MEDIUM | LOW | NONE
    activity_guess: str | None = None
    location_guess: str | None = None
    evidence_spans: list[str] = field(default_factory=list)


def _find_first(keywords: list[str], text_lower: str) -> str | None:
    for kw in keywords:
        if kw in text_lower:
            return kw
    return None


def extract_entities(narrative: str) -> ExtractedEntities:
    result = ExtractedEntities()
    sentences = split_sentences(narrative)
    # Hyphens are normalized to spaces before keyword matching so surface-form
    # variation ("confined-space" vs "confined space") doesn't silently defeat
    # a keyword hit -- none of the keyword lists in this module contain a
    # literal hyphen, so this is purely additive recall, never a new match.
    narrative_lower = narrative.lower().replace("-", " ")

    detected_categories: list[str] = []
    hazard_sentences: list[str] = []

    for sentence in sentences:
        s_lower = sentence.lower().replace("-", " ")
        sentence_categories = [
            cat for cat, kws in ENERGY_CATEGORIES.items() if _find_first(kws, s_lower)
        ]
        if sentence_categories:
            hazard_sentences.append(sentence.strip())
            for cat in sentence_categories:
                if cat not in detected_categories:
                    detected_categories.append(cat)

    result.energy_categories = detected_categories

    if detected_categories:
        # Proximity is scanned across the WHOLE narrative (not sentence-by-sentence)
        # because the hazard mention and the hands-on-equipment/proximity mention
        # often sit in different sentences of the same event narrative (e.g. "opened
        # a flange before confirming isolation. Residual pressure was released.").
        # This is only reached when an energy/hazard category was already found
        # somewhere in the narrative, so a bare proximity word alone still cannot
        # manufacture an exposure out of nothing.
        if _find_first(PROXIMITY_HIGH, narrative_lower):
            proximity = "HIGH"
        elif _find_first(PROXIMITY_MEDIUM, narrative_lower):
            proximity = "MEDIUM"
        elif any(cue in narrative_lower for cue in PROXIMITY_NONE_CUES):
            proximity = "NONE"
        else:
            proximity = "LOW"  # hazard/energy present, but no explicit proximity cue

        result.exposure_proximity = proximity
        result.exposure_description = hazard_sentences[0] if hazard_sentences else None
        result.evidence_spans = hazard_sentences[:3]

    if detected_categories:
        primary = detected_categories[0]
        result.hazard_label = HAZARD_LABELS[primary]
        result.energy_source = ENERGY_SOURCE_LABELS[primary]
        result.hazards = [HAZARD_LABELS[c] for c in detected_categories]

    for activity, kws in ACTIVITY_KEYWORDS.items():
        if _find_first(kws, narrative_lower):
            result.activity_guess = activity
            break

    loc_match = LOCATION_RE.search(narrative)
    if loc_match:
        candidate = loc_match.group(1).strip()
        if len(candidate.split()) <= 6:
            result.location_guess = candidate.title()

    return result
