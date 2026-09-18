"""
Text preprocessing (blueprint Pipeline Stage 3).

Supports Latin + Devanagari tokenization. Dense unsupported-script input is
flagged so the analysis pipeline can abstain to REVIEW instead of returning
an empty silent analysis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_WS_RE = re.compile(r"\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9\u0900-\u097F])")
_CLAUSE_SPLIT_RE = re.compile(
    r"\b(but|however|although|though|whereas|except that|लेकिन|परंतु|किंतु)\b",
    re.IGNORECASE,
)
# Latin tokens OR Devanagari word runs OR numbers
_TOKEN_RE = re.compile(
    r"[A-Za-z][A-Za-z\-/]*|[\u0900-\u097F]+|\d+(?:\.\d+)?%?"
)
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")

_PROTECTED_ABBR = ["e.g.", "i.e.", "no.", "approx.", "psi.", "vs."]

# Small Hindi / Romanized safety lexicon overlay (pragmatic prototype, not full NER).
HINDI_SAFETY_LEXICON: dict[str, str] = {
    "लोतो": "loto",
    "लोटो": "loto",
    "परमिट": "permit",
    "अनुमति": "permit",
    "गैस": "gas",
    "विद्युत": "electrical",
    "बिजली": "electrical",
    "ऊंचाई": "height",
    "गिरना": "fall",
    "स्caffold": "scaffold",
    "हेलमेट": "helmet",
    "सुरक्षा": "safety",
    "खतरा": "hazard",
    "दुर्घटना": "incident",
    "बिना": "without",
    "नहीं": "not",
    "loto": "loto",
    "ptw": "permit",
    "permit": "permit",
}


@dataclass
class LanguageSupport:
    script: str  # latin | devanagari | mixed | other
    supported: bool
    latin_token_count: int
    devanagari_char_count: int
    reason: str | None = None


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\t", " ")
    text = _WS_RE.sub(" ", text).strip()
    return text


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    protected = text
    for i, abbr in enumerate(_PROTECTED_ABBR):
        protected = protected.replace(abbr, abbr.replace(".", f"__ABBR{i}__"))
    parts = _SENTENCE_SPLIT_RE.split(protected)
    sentences = []
    for p in parts:
        for i, abbr in enumerate(_PROTECTED_ABBR):
            p = p.replace(f"__ABBR{i}__", ".")
        p = p.strip()
        if p:
            sentences.append(p)
    return sentences or [text]


def split_clauses(sentence: str) -> list[str]:
    parts = _CLAUSE_SPLIT_RE.split(sentence)
    skip = {"but", "however", "although", "though", "whereas", "except that", "लेकिन", "परंतु", "किंतु"}
    clauses = [p.strip() for p in parts if p.strip() and p.lower() not in skip]
    return clauses or [sentence]


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text or "")


def normalize_for_matching(text: str) -> str:
    """Lowercase Latin; map known Hindi safety terms to English glosses for matching."""
    cleaned = clean_text(text).lower()
    for hi, en in HINDI_SAFETY_LEXICON.items():
        cleaned = cleaned.replace(hi.lower(), f" {en} ")
    return _WS_RE.sub(" ", cleaned).strip()


def detect_language_support(text: str) -> LanguageSupport:
    text = text or ""
    dev_count = len(_DEVANAGARI_RE.findall(text))
    latin_letters = len(_LATIN_LETTER_RE.findall(text))
    tokens = tokenize(text)
    latin_tokens = [t for t in tokens if _LATIN_LETTER_RE.search(t)]
    # Expand matching text with lexicon glosses so Hindi-only safety words still yield Latin tokens after normalize
    normalized = normalize_for_matching(text)
    gloss_latin = len(_LATIN_LETTER_RE.findall(normalized))

    if latin_letters == 0 and dev_count == 0:
        return LanguageSupport("other", False, 0, 0, "No recognizable Latin or Devanagari script.")
    if latin_letters == 0 and dev_count > 0:
        # Hindi-only: supported if lexicon/normalize yields usable Latin glosses OR enough Devanagari tokens for rules
        if gloss_latin >= 8 or len(tokenize(normalized)) >= 3:
            return LanguageSupport("devanagari", True, len(latin_tokens), dev_count, None)
        return LanguageSupport(
            "devanagari",
            False,
            0,
            dev_count,
            "Devanagari narrative with insufficient safety lexicon coverage — routed to human REVIEW.",
        )
    if latin_letters > 0 and dev_count > 0:
        return LanguageSupport("mixed", True, len(latin_tokens), dev_count, None)
    if len(latin_tokens) == 0 and latin_letters < 10:
        return LanguageSupport(
            "other",
            False,
            0,
            dev_count,
            "Unsupported script or empty token stream — routed to human REVIEW.",
        )
    return LanguageSupport("latin", True, len(latin_tokens), 0, None)
