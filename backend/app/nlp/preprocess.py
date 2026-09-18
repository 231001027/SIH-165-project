"""
Text preprocessing (blueprint Pipeline Stage 3).

Tokenization still recognizes Latin + Devanagari for diagnostics and future
multilingual *retrieval*. The rule NLP pipeline (entities / barriers / LSR) is
English-only: use `is_pipeline_supported_language` before analysis so dense
non-Latin input fails closed with UNSUPPORTED_LANGUAGE instead of a silent
empty analysis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import get_settings

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
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z\-/]*")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")

_PROTECTED_ABBR = ["e.g.", "i.e.", "no.", "approx.", "psi.", "vs."]

# Small Hindi / Romanized safety lexicon overlay (kept for optional gloss experiments /
# future retrieval phases). Devanagari narratives must NOT be treated as supported
# by the English rule pipeline — see is_pipeline_supported_language().
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

UNSUPPORTED_LANGUAGE_MESSAGE = (
    "This prototype currently supports English-language input only. "
    "Automated analysis was not run for this report; manual review is required."
)


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
    """Lowercase Latin; map known Hindi safety terms to English glosses for matching.

    Not used to authorize Devanagari through the English rule pipeline — that gate
    is `is_pipeline_supported_language`.
    """
    cleaned = clean_text(text).lower()
    for hi, en in HINDI_SAFETY_LEXICON.items():
        cleaned = cleaned.replace(hi.lower(), f" {en} ")
    return _WS_RE.sub(" ", cleaned).strip()


def latin_token_ratio(text: str) -> float:
    """Share of tokenize() tokens that are ASCII Latin-alphabet (not Devanagari/numbers-only)."""
    tokens = tokenize(clean_text(text or ""))
    if not tokens:
        return 0.0
    latin = [t for t in tokens if _LATIN_TOKEN_RE.fullmatch(t)]
    return len(latin) / len(tokens)


def is_pipeline_supported_language(narrative: str) -> bool:
    """Return True iff the narrative is processable by the English-only rule NLP pipeline.

    Detection is script/token based (no langdetect/fasttext). After whitespace
    collapse, we require that at least PIPELINE_LATIN_TOKEN_RATIO_MIN of tokens
    from `_TOKEN_RE` are ASCII Latin-alphabet tokens (`_LATIN_TOKEN_RE`).

    Known limitation: Romanized Hindi (Latin script) still PASSES this check even
    though downstream keyword matching will not find Hindi terms — we intentionally
    do not attempt Romanized-Hindi semantic understanding here. Multilingual
    *retrieval* is a separate phase; this gate only protects rule extraction.
    """
    text = clean_text(narrative or "")
    if not text:
        return False
    tokens = tokenize(text)
    if not tokens:
        return False
    threshold = get_settings().PIPELINE_LATIN_TOKEN_RATIO_MIN
    return latin_token_ratio(text) >= threshold


def detect_language_support(text: str) -> LanguageSupport:
    """Diagnostic script labelling. Pipeline authorization uses is_pipeline_supported_language."""
    text = text or ""
    dev_count = len(_DEVANAGARI_RE.findall(text))
    latin_letters = len(_LATIN_LETTER_RE.findall(text))
    tokens = tokenize(text)
    latin_tokens = [t for t in tokens if _LATIN_TOKEN_RE.fullmatch(t)]
    supported = is_pipeline_supported_language(text)

    if latin_letters == 0 and dev_count == 0:
        return LanguageSupport("other", False, 0, 0, UNSUPPORTED_LANGUAGE_MESSAGE)
    if latin_letters == 0 and dev_count > 0:
        return LanguageSupport(
            "devanagari",
            False,  # English rule pipeline: Devanagari is never supported
            len(latin_tokens),
            dev_count,
            UNSUPPORTED_LANGUAGE_MESSAGE if not supported else None,
        )
    if latin_letters > 0 and dev_count > 0:
        return LanguageSupport(
            "mixed",
            supported,
            len(latin_tokens),
            dev_count,
            None if supported else UNSUPPORTED_LANGUAGE_MESSAGE,
        )
    if not supported:
        return LanguageSupport(
            "other" if len(latin_tokens) == 0 else "latin",
            False,
            len(latin_tokens),
            dev_count,
            UNSUPPORTED_LANGUAGE_MESSAGE,
        )
    return LanguageSupport("latin", True, len(latin_tokens), 0, None)
