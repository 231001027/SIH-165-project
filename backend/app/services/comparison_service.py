"""Side-by-side precursor comparison with shared-field evidence spans."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisResult, ReportBarrier, ReportEntity
from app.models.report import Report
from app.nlp.entity_extraction import extract_entities
from app.nlp.negation import analyze_barriers
from app.rules.lsr_engine import classify_lsr


def _analysis_bundle(db: Session, report: Report) -> dict:
    analysis = db.query(AnalysisResult).filter(AnalysisResult.report_id == report.id).first()
    entities = []
    barriers = []
    if analysis:
        entities = db.query(ReportEntity).filter(ReportEntity.analysis_id == analysis.id).all()
        barriers = db.query(ReportBarrier).filter(ReportBarrier.analysis_id == analysis.id).all()
    else:
        # On-the-fly extraction for unanalyzed narratives (should be rare for PUBLIC_CORPUS after seed)
        ent = extract_entities(report.narrative or "")
        bf = analyze_barriers(report.narrative or "")
        lsr = classify_lsr(report.narrative or "", ent)
        return {
            "analysis": None,
            "primary_lsr": lsr.primary,
            "hazard": ent.hazard_label,
            "energy_category": ent.energy_categories[0] if ent.energy_categories else None,
            "barrier_types": {b.barrier_type for b in bf},
            "entity_spans": list(ent.evidence_spans or []),
            "barrier_evidence": {b.barrier_type: b.evidence_text for b in bf},
            "lsr_evidence": list(lsr.evidence or []),
        }

    return {
        "analysis": analysis,
        "primary_lsr": analysis.primary_lsr,
        "hazard": analysis.hazard,
        "energy_category": analysis.energy_category,
        "barrier_types": {b.barrier_type for b in barriers},
        "entity_spans": [e.evidence_span or e.entity_text for e in entities if (e.evidence_span or e.entity_text)],
        "barrier_evidence": {b.barrier_type: b.evidence_text for b in barriers if b.evidence_text},
        "lsr_evidence": list(analysis.lsr_evidence or []),
    }


def _span_for(value: str | None, spans: list[str], barrier_ev: dict, narrative: str) -> str | None:
    if not value:
        return None
    v = str(value).lower()
    for s in spans:
        if s and (v in s.lower() or s.lower() in narrative.lower()):
            return s
    for name, ev in barrier_ev.items():
        if name.lower() in v or v in name.lower():
            if ev:
                return ev
    # Fallback: first sentence containing a keyword token from value
    for token in str(value).replace("/", " ").split():
        if len(token) < 4:
            continue
        idx = narrative.lower().find(token.lower())
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(narrative), idx + len(token) + 40)
            return narrative[start:end].strip()
    return None


def compare_precursors(db: Session, query_id: int, match_id: int) -> dict:
    q = db.query(Report).filter(Report.id == query_id).first()
    m = db.query(Report).filter(Report.id == match_id).first()
    if not q or not m:
        raise ValueError("Report not found")

    qb = _analysis_bundle(db, q)
    mb = _analysis_bundle(db, m)
    fields = []

    def add_field(name: str, qv, mv, q_ev, m_ev, shared: bool, reason: str):
        fields.append({
            "field": name,
            "shared": shared,
            "query_value": qv,
            "match_value": mv,
            "query_evidence": q_ev,
            "match_evidence": m_ev,
            "reason": reason,
        })

    # LSR
    shared_lsr = bool(qb["primary_lsr"] and qb["primary_lsr"] == mb["primary_lsr"] and qb["primary_lsr"] != "No applicable rule")
    add_field(
        "primary_lsr",
        qb["primary_lsr"],
        mb["primary_lsr"],
        (qb["lsr_evidence"][0] if qb["lsr_evidence"] else None) or _span_for(qb["primary_lsr"], qb["entity_spans"], qb["barrier_evidence"], q.narrative or ""),
        (mb["lsr_evidence"][0] if isinstance(mb["lsr_evidence"], list) and mb["lsr_evidence"] and isinstance(mb["lsr_evidence"][0], str) else None)
        or _span_for(mb["primary_lsr"], mb["entity_spans"], mb["barrier_evidence"], m.narrative or ""),
        shared_lsr,
        "Same IOGP Life-Saving Rule on both reports." if shared_lsr else "Life-Saving Rule differs or is not applicable.",
    )

    # Hazard
    shared_h = bool(qb["hazard"] and qb["hazard"] == mb["hazard"])
    add_field(
        "hazard",
        qb["hazard"],
        mb["hazard"],
        _span_for(qb["hazard"], qb["entity_spans"], qb["barrier_evidence"], q.narrative or ""),
        _span_for(mb["hazard"], mb["entity_spans"], mb["barrier_evidence"], m.narrative or ""),
        shared_h,
        "Same hazard label extracted from both narratives." if shared_h else "Hazard labels differ or are missing.",
    )

    # Energy
    shared_e = bool(qb["energy_category"] and qb["energy_category"] == mb["energy_category"])
    add_field(
        "energy_category",
        qb["energy_category"],
        mb["energy_category"],
        _span_for(qb["energy_category"], qb["entity_spans"], qb["barrier_evidence"], q.narrative or ""),
        _span_for(mb["energy_category"], mb["entity_spans"], mb["barrier_evidence"], m.narrative or ""),
        shared_e,
        "Same energy category on both reports." if shared_e else "Energy categories differ or are missing.",
    )

    # Barriers (set intersection / difference)
    shared_barriers = qb["barrier_types"] & mb["barrier_types"]
    only_q = qb["barrier_types"] - mb["barrier_types"]
    only_m = mb["barrier_types"] - qb["barrier_types"]
    for b in sorted(shared_barriers):
        add_field(
            f"barrier:{b}",
            b,
            b,
            qb["barrier_evidence"].get(b) or _span_for(b, qb["entity_spans"], qb["barrier_evidence"], q.narrative or ""),
            mb["barrier_evidence"].get(b) or _span_for(b, mb["entity_spans"], mb["barrier_evidence"], m.narrative or ""),
            True,
            f"Both reports mention barrier type '{b}'.",
        )
    for b in sorted(only_q):
        add_field(
            f"barrier:{b}",
            b,
            None,
            qb["barrier_evidence"].get(b),
            None,
            False,
            f"Barrier '{b}' present only on the query report.",
        )
    for b in sorted(only_m):
        add_field(
            f"barrier:{b}",
            None,
            b,
            None,
            mb["barrier_evidence"].get(b),
            False,
            f"Barrier '{b}' present only on the retrieved incident.",
        )

    # Ensure shared fields with evidence: if a shared field lacks evidence, try harder
    for f in fields:
        if f["shared"]:
            if not f["query_evidence"]:
                f["query_evidence"] = (q.narrative or "")[:120]
            if not f["match_evidence"]:
                f["match_evidence"] = (m.narrative or "")[:120]

    is_reference = m.source.value == "PUBLIC_CORPUS" if hasattr(m.source, "value") else m.source == "PUBLIC_CORPUS"
    return {
        "query_report_id": q.id,
        "match_report_id": m.id,
        "query_narrative": q.narrative or "",
        "match_narrative": m.narrative or "",
        "match_title": m.title,
        "match_source": "PUBLIC_CORPUS" if is_reference else "INTERNAL",
        "citation_label": m.citation_label if is_reference else None,
        "citation_url": m.citation_url if is_reference else None,
        "provenance": m.provenance if is_reference else None,
        "query_highlights": [s for s in qb["entity_spans"] if s][:12],
        "match_highlights": [s for s in mb["entity_spans"] if s][:12],
        "fields": fields,
    }
