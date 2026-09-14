"""
Safety Terminology Normalization (blueprint Pipeline Stage 4).

Maps OIL/oilfield jargon and abbreviations onto canonical safety concepts so
downstream rule matching does not have to enumerate every surface form. This
lexicon is intentionally a plain Python dict (not a compiled model) so the
team can extend it with real OIL-specific terminology later without touching
any other module -- see README "Limitations & Future Enhancements".
"""
from __future__ import annotations

import re

# canonical_tag -> list of surface forms (longest-first matching handled at build time)
CANONICAL_TERMS: dict[str, list[str]] = {
    "ENERGY_ISOLATION": [
        "lock out tag out", "lockout tagout", "lockout/tagout", "lock-out/tag-out",
        "loto", "isolation", "isolate", "isolated", "zero energy", "de-energized",
        "de-energised", "energy isolation",
    ],
    "PERMIT_TO_WORK": [
        "permit to work", "permit-to-work", "work permit", "ptw", "work authorization",
        "work authorisation",
    ],
    "SIMOPS": ["simultaneous operations", "simops"],
    "CONFINED_SPACE": [
        "confined space", "vessel entry", "tank entry", "enclosed space", "manhole entry",
    ],
    "HOT_WORK": [
        "hot work", "welding", "grinding", "cutting torch", "naked flame", "open flame",
    ],
    "LINE_OF_FIRE": [
        "line of fire", "suspended load", "dropped object", "pinch point", "struck by",
    ],
    "MECHANICAL_LIFTING": [
        "lifting operation", "crane lift", "rigging", "mechanical lifting", "lift plan",
    ],
    "WORKING_AT_HEIGHT": [
        "working at height", "work at height", "scaffold", "fall arrest", "fall protection",
        "elevated platform", "elevated work",
    ],
    "GAS_TESTING": [
        "gas test", "gas testing", "atmospheric test", "lel test", "gas detector",
    ],
    "EXCLUSION_ZONE": [
        "exclusion zone", "barricade", "cordoned off", "restricted area", "cordon",
    ],
    "DRIVING": ["driving", "vehicle movement", "journey management", "seatbelt"],
    "BYPASS_SAFETY_CONTROLS": [
        "bypass", "override", "defeat interlock", "disabled alarm", "overridden interlock",
    ],
    "PRESSURE_RELIEF": ["pressure relief", "relief valve", "psv", "venting"],
    "SUPERVISION": ["supervision", "supervisor present", "toolbox talk"],
    "PPE": [
        "personal protective equipment", "ppe", "hard hat", "safety glasses", "harness",
        "gloves",
    ],
}

def _surface_to_pattern(surface: str) -> str:
    """Build a regex for one surface form that treats a space and a hyphen as
    interchangeable word separators (e.g. "confined space" also matches
    "confined-space"), so real-world phrasing variation doesn't silently
    defeat a keyword hit that the term list already intends to catch."""
    parts = [re.escape(token) for token in surface.split(" ")]
    return r"\b" + r"[\s-]+".join(parts) + r"\b"


_ALL_PAIRS: list[tuple[str, str]] = sorted(
    ((surface, tag) for tag, forms in CANONICAL_TERMS.items() for surface in forms),
    key=lambda pair: len(pair[0]),
    reverse=True,
)
_COMPILED = [
    (re.compile(_surface_to_pattern(surface), re.IGNORECASE), tag)
    for surface, tag in _ALL_PAIRS
]


def tag_canonical_terms(text: str) -> set[str]:
    """Return the set of canonical safety-concept tags mentioned in the text."""
    tags: set[str] = set()
    for pattern, tag in _COMPILED:
        if pattern.search(text):
            tags.add(tag)
    return tags
