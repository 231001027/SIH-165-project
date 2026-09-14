"""
Text preprocessing (blueprint Pipeline Stage 3).

Design decision (documented per source-discipline rules): rather than depend on
a heavyweight spaCy model download, this module uses a lightweight, fully
deterministic, pure-Python tokenizer/sentence-splitter. This keeps the whole
pipeline installable and runnable fully offline in minutes, which the
blueprint explicitly treats as a requirement (Part 7.3 "Offline / API failure
strategy") rather than a nice-to-have. The extraction/negation modules that
consume this are written against a small interface, so a spaCy- or
transformer-based tokenizer could be swapped in later without changing the
rest of the pipeline.
"""
import re

_WS_RE = re.compile(r"\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9])")
_CLAUSE_SPLIT_RE = re.compile(
    r"\b(but|however|although|though|whereas|except that)\b", re.IGNORECASE
)
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z\-/]*|\d+(?:\.\d+)?%?")

# Abbreviations that must never trigger a sentence break on their trailing period.
_PROTECTED_ABBR = ["e.g.", "i.e.", "no.", "approx.", "psi.", "vs."]


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
    """Split a sentence on strong contrastive conjunctions (but/however/...),
    used so the negation engine can score the correct clause for a barrier
    mention rather than an unrelated clause elsewhere in the sentence."""
    parts = _CLAUSE_SPLIT_RE.split(sentence)
    clauses = [p.strip() for p in parts if p.strip() and p.lower() not in
               ("but", "however", "although", "though", "whereas", "except that")]
    return clauses or [sentence]


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def normalize_for_matching(text: str) -> str:
    return clean_text(text).lower()
