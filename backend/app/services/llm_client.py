"""
Bounded LLM assistance (blueprint Part 5.4 / 5.6 / 7.3).

Strict rules enforced here:
  - The LLM is NEVER the sole SIF authority. It is only ever asked to
    rephrase/expand an explanation that has already been fully computed by
    the deterministic rule engine + ML classifier + LSR/barrier engines.
  - If LLM_API_KEY is not configured, or the call fails/times out for any
    reason, the system transparently falls back to the template-based
    explanation (app/services/explanation_service.py) and marks
    explanation_source="template" on the AnalysisResult so the UI can show
    "LLM-enhanced explanation unavailable -- showing rule/embedding-based
    result" per Part 7.3.
  - The prompt only ever includes already-extracted structured fields, never
    an instruction to "decide" anything -- this bounds prompt-injection risk
    from report narratives (Part 7.2).
"""
from __future__ import annotations

import re

import httpx

from app.core.config import get_settings

settings = get_settings()

# Full known vocabularies (blueprint Part 5.4 Trust Layer safeguard: "reject/flag
# any LLM output that introduces a hazard/barrier/LSR not present in the source
# text"). These are deliberately imported from the SAME modules the deterministic
# pipeline uses, so this list can never silently drift out of sync with what the
# rule/LSR/barrier engines can actually produce.
def _known_vocabularies() -> tuple[list[str], list[str], list[str]]:
    from app.nlp.entity_extraction import HAZARD_LABELS
    from app.nlp.negation import BARRIER_KEYWORDS
    from app.rules.lsr_engine import get_knowledge_base

    lsr_names = [r["rule"] for r in get_knowledge_base()]
    hazard_labels = list(HAZARD_LABELS.values())
    barrier_types = list(BARRIER_KEYWORDS.keys())
    return lsr_names, hazard_labels, barrier_types


def _validate_llm_output(text: str, structured_fields: dict) -> bool:
    """Returns False if `text` mentions a KNOWN hazard/barrier/LSR name that is
    not among the values already computed by the deterministic pipeline for
    THIS report -- i.e. the LLM appears to have introduced an unsupported
    safety claim rather than merely rephrasing the given fields. This is a
    vocabulary check, not a general hallucination detector: it cannot catch a
    fabricated claim phrased without one of these known terms, but it directly
    closes the specific failure mode the Trust Layer calls out (Part 5.4) --
    the model naming a *different* rule/hazard/barrier than the one extracted.
    """
    text_lower = text.lower()
    allowed = {str(v).lower() for v in structured_fields.values() if v}
    lsr_names, hazard_labels, barrier_types = _known_vocabularies()
    for name in lsr_names + hazard_labels + barrier_types:
        name_lower = name.lower()
        # Word-boundary match, not naive substring containment -- a short
        # acronym like "PPE" is otherwise a substring of ordinary words (e.g.
        # "ma-PPE-d"), which would reject perfectly safe rephrased text.
        pattern = r"\b" + re.escape(name_lower) + r"\b"
        if re.search(pattern, text_lower) and not any(name_lower in a or a in name_lower for a in allowed):
            return False
    return True


def is_llm_configured() -> bool:
    return bool(settings.LLM_API_KEY and settings.LLM_PROVIDER)


def enhance_explanation(template_explanation: str, structured_fields: dict) -> tuple[str, str]:
    """Returns (explanation_text, source) where source is 'template' or 'llm_enhanced'.
    Always safe to call even with no LLM configured -- returns the template untouched."""
    if not is_llm_configured():
        return template_explanation, "template"

    prompt = (
        "Rewrite the following safety-analysis summary in one or two clear, "
        "concise sentences for an HSE analyst. Do NOT introduce any hazard, "
        "barrier, or Life-Saving Rule that is not already listed below. "
        "Do not add new facts.\n\n"
        f"Structured fields: {structured_fields}\n\n"
        f"Draft summary: {template_explanation}"
    )
    try:
        if settings.LLM_PROVIDER == "anthropic":
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.LLM_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.LLM_MODEL,
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=8.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = "".join(block.get("text", "") for block in data.get("content", []))
            text = text.strip()
            if text and _validate_llm_output(text, structured_fields):
                return text, "llm_enhanced"
            # Either empty or it introduced a hazard/barrier/LSR name that isn't
            # part of this report's own extracted evidence -- reject and fall
            # back rather than show an unsupported safety claim.
            return template_explanation, "template"
        # Other providers could be added here following the same bounded pattern.
        return template_explanation, "template"
    except Exception:
        # Any network/API failure silently and safely falls back -- the core
        # pipeline must never break because the LLM is unavailable (Part 7.3).
        return template_explanation, "template"
