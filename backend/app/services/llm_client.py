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
  - The prompt only ever includes already-extracted structured fields (and
    optional retrieved excerpts for RAG polish), never an instruction to
    "decide" anything -- this bounds prompt-injection risk from report
    narratives (Part 7.2).
"""
from __future__ import annotations

import re

import httpx

from app.core.config import get_settings


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
    THIS report.
    """
    text_lower = text.lower()
    allowed = {str(v).lower() for v in structured_fields.values() if v}
    lsr_names, hazard_labels, barrier_types = _known_vocabularies()
    for name in lsr_names + hazard_labels + barrier_types:
        name_lower = name.lower()
        pattern = r"\b" + re.escape(name_lower) + r"\b"
        if re.search(pattern, text_lower) and not any(name_lower in a or a in name_lower for a in allowed):
            return False
    return True


def is_llm_configured() -> bool:
    settings = get_settings()
    if not settings.LLM_PROVIDER:
        return False
    if settings.LLM_PROVIDER == "ollama":
        return True
    return bool(settings.LLM_API_KEY)


def _build_prompt(
    template_explanation: str,
    structured_fields: dict,
    retrieved_excerpts: list[dict] | None = None,
) -> str:
    excerpt_block = ""
    if retrieved_excerpts:
        lines = []
        for i, item in enumerate(retrieved_excerpts[:3], start=1):
            cite = item.get("citation_label") or item.get("title") or f"match-{i}"
            excerpt = (item.get("excerpt") or "").strip()
            if excerpt:
                lines.append(f"{i}. [{cite}] {excerpt}")
        if lines:
            excerpt_block = (
                "\n\nRetrieved historical excerpts (for phrasing context only; "
                "do not invent new hazards/rules):\n" + "\n".join(lines)
            )
    return (
        "Rewrite the following safety-analysis summary in one or two clear, "
        "concise sentences for an HSE analyst. Do NOT introduce any hazard, "
        "barrier, or Life-Saving Rule that is not already listed below. "
        "Do not add new facts.\n\n"
        f"Structured fields: {structured_fields}\n\n"
        f"Draft summary: {template_explanation}"
        f"{excerpt_block}"
    )


def _call_anthropic(prompt: str) -> str:
    settings = get_settings()
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
    return "".join(block.get("text", "") for block in data.get("content", [])).strip()


def _call_ollama(prompt: str) -> str:
    settings = get_settings()
    base = settings.OLLAMA_BASE_URL.rstrip("/")
    resp = httpx.post(
        f"{base}/api/chat",
        json={
            "model": settings.LLM_MODEL,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"num_predict": 200},
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()
    message = data.get("message") or {}
    return (message.get("content") or "").strip()


def enhance_explanation(
    template_explanation: str,
    structured_fields: dict,
    retrieved_excerpts: list[dict] | None = None,
) -> tuple[str, str]:
    """Returns (explanation_text, source) where source is 'template' or 'llm_enhanced'."""
    if not is_llm_configured():
        return template_explanation, "template"

    settings = get_settings()
    # Re-read env each call so .env edits apply after process reload / cache clear.
    get_settings.cache_clear()
    settings = get_settings()

    prompt = _build_prompt(template_explanation, structured_fields, retrieved_excerpts)
    try:
        provider = settings.LLM_PROVIDER.lower().strip()
        if provider == "anthropic":
            text = _call_anthropic(prompt)
        elif provider == "ollama":
            text = _call_ollama(prompt)
        else:
            return template_explanation, "template"

        if text and _validate_llm_output(text, structured_fields):
            return text, "llm_enhanced"
        return template_explanation, "template"
    except Exception:
        return template_explanation, "template"
