"""Similar-report retrieval (blueprint Part 1.3 Stage 12) with FAISS + cited excerpts."""
from __future__ import annotations

import re

import numpy as np
from sqlalchemy.orm import Session

from app.ml import faiss_index
from app.models.analysis import PrecursorFingerprint
from app.models.report import Report
from app.nlp.preprocess import tokenize


def _excerpt_from_narrative(query_narrative: str, match_narrative: str, max_len: int = 220) -> str:
    """Pick a short window from the match that overlaps query tokens when possible."""
    if not match_narrative:
        return ""
    text = match_narrative.strip()
    q_tokens = {t.lower() for t in tokenize(query_narrative) if len(t) > 3}
    sentences = re.split(r"(?<=[.!?])\s+", text)
    best = ""
    best_score = -1
    for sent in sentences:
        tokens = {t.lower() for t in tokenize(sent)}
        score = len(q_tokens & tokens)
        if score > best_score:
            best_score = score
            best = sent.strip()
    if not best:
        best = text[:max_len]
    if len(best) > max_len:
        best = best[: max_len - 1].rstrip() + "…"
    return best


def find_similar_reports(db: Session, report_id: int, top_k: int = 5) -> list[dict]:
    target_fp = db.query(PrecursorFingerprint).filter(PrecursorFingerprint.report_id == report_id).first()
    if not target_fp:
        return []

    target_report = db.query(Report).filter(Report.id == report_id).first()
    query_narrative = target_report.narrative if target_report else ""

    hits = faiss_index.search(target_fp.embedding, top_k=top_k, exclude_id=report_id)

    # Fallback: brute-force if FAISS empty / cold
    if not hits:
        all_fps = db.query(PrecursorFingerprint).filter(PrecursorFingerprint.report_id != report_id).all()
        if not all_fps:
            return []
        target_vec = np.array(target_fp.embedding, dtype=np.float32)
        corpus_vecs = np.array([fp.embedding for fp in all_fps], dtype=np.float32)
        if corpus_vecs.ndim != 2 or corpus_vecs.shape[1] != target_vec.shape[0]:
            return []
        norm_target = target_vec / (np.linalg.norm(target_vec) or 1.0)
        norms = np.linalg.norm(corpus_vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        similarities = (corpus_vecs / norms) @ norm_target
        order = np.argsort(similarities)[::-1][:top_k]
        hits = [(all_fps[i].report_id, float(similarities[i])) for i in order]
        # Opportunistically rebuild FAISS for next calls
        try:
            faiss_index.rebuild_from_db(db)
        except Exception:
            pass

    report_ids = [rid for rid, _ in hits]
    fps = {
        fp.report_id: fp
        for fp in db.query(PrecursorFingerprint).filter(PrecursorFingerprint.report_id.in_(report_ids)).all()
    }
    reports = {r.id: r for r in db.query(Report).filter(Report.id.in_(report_ids)).all()}

    results = []
    for rid, score in hits:
        fp = fps.get(rid)
        r = reports.get(rid)
        if not fp or not r:
            continue
        is_reference = r.source.value == "PUBLIC_CORPUS" if hasattr(r.source, "value") else r.source == "PUBLIC_CORPUS"
        excerpt = _excerpt_from_narrative(query_narrative, r.narrative or "")
        results.append({
            "report_id": fp.report_id,
            "report_code": r.report_code,
            "title": r.title,
            "similarity": round(float(score), 4),
            "sif_potential": fp.fingerprint_json.get("sif_potential"),
            "life_saving_rule": fp.fingerprint_json.get("life_saving_rule"),
            "site": fp.fingerprint_json.get("site"),
            "activity": fp.fingerprint_json.get("activity"),
            "occurred_at": fp.fingerprint_json.get("occurred_at"),
            "source": "PUBLIC_CORPUS" if is_reference else "INTERNAL",
            "citation_label": r.citation_label if is_reference else None,
            "citation_url": r.citation_url if is_reference else None,
            "excerpt": excerpt,
        })
    return results
