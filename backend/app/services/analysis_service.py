"""
The core orchestrator: runs every pipeline stage (blueprint Stages 3-11) for
one report and persists the result. Pipeline steps are independently callable
so LangGraph nodes and the non-graph fallback share one implementation.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import (
    AnalysisResult, ReportEntity, ReportBarrier, PrecursorFingerprint, SifClassification,
)
from app.models.report import Report
from app.nlp.entity_extraction import extract_entities, ExtractedEntities
from app.nlp.negation import analyze_barriers, BarrierFinding
from app.rules.lsr_engine import classify_lsr, NO_APPLICABLE_RULE
from app.rules.sif_rules import run_rule_engine
from app.ml.embeddings import get_embedding_provider
from app.ml.classifier import get_classifier, build_feature_vector
from app.services.explanation_service import build_explanation
from app.services.fingerprint_service import build_fingerprint
from app.services import llm_client
from app.services.similarity_service import find_similar_by_embedding
from app.ml import faiss_index
from app.nlp.preprocess import (
    is_pipeline_supported_language,
    UNSUPPORTED_LANGUAGE_MESSAGE,
)
from app.services.standards_tags import map_standards_tags
from app.services.oisd_matrix import classify_from_pipeline

settings = get_settings()
_WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "core" / "risk_weights.json"
with open(_WEIGHTS_PATH, "r", encoding="utf-8") as f:
    _RISK_CONFIG = json.load(f)

_ORDINAL = {"NON_SIF": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
MODEL_VERSION = "sifguard-v0.1-prototype"


def ensure_embedding_provider_fitted(db: Session) -> None:
    provider = get_embedding_provider()
    if provider.is_ready():
        return
    narratives = [r.narrative for r in db.query(Report).all()]
    if len(narratives) < 3:
        return
    provider.fit(narratives)


def _compute_risk_score(rule_result) -> tuple[float, dict]:
    w = _RISK_CONFIG["weights"]
    breakdown = {
        "hazard_energy": round(w["hazard_energy"] * rule_result.hazard_energy_component, 1),
        "worker_exposure": round(w["worker_exposure"] * rule_result.worker_exposure_component, 1),
        "barrier_failure": round(w["barrier_failure"] * rule_result.barrier_failure_component, 1),
        "activity_criticality": round(w["activity_criticality"] * rule_result.activity_criticality_component, 1),
        "repeat_precursor": round(w["repeat_precursor"] * rule_result.repeat_precursor_component, 1),
    }
    risk_score = round(sum(breakdown.values()), 1)
    breakdown["total"] = risk_score
    breakdown["_disclaimer"] = _RISK_CONFIG["_disclaimer"]
    return risk_score, breakdown


def _rule_band(risk_score: float, entities, barrier_failure_component: float) -> str:
    has_any_signal = (
        bool(entities.energy_categories)
        or entities.exposure_proximity != "NONE"
        or barrier_failure_component >= 0.5
    )
    if not has_any_signal and risk_score < 20:
        return "NON_SIF"
    bands = _RISK_CONFIG["bands"]
    if risk_score >= bands["HIGH"]:
        return "HIGH"
    if risk_score >= bands["MEDIUM"]:
        return "MEDIUM"
    if risk_score >= bands["LOW"] and has_any_signal:
        return "LOW"
    return "NON_SIF"


def _rule_confidence(risk_score: float, band: str, evidence_confidence: float) -> float:
    if band == "NON_SIF":
        return round(min(97.0, max(55.0, 95 - risk_score * 2.2)), 1)
    if band == "HIGH":
        bands = _RISK_CONFIG["bands"]
        margin_bonus = min(15.0, max(0.0, (risk_score - bands["HIGH"]) * 0.4))
        return round(min(99.0, 55 + evidence_confidence * 0.3 + margin_bonus), 1)
    if band == "MEDIUM":
        bands = _RISK_CONFIG["bands"]
        margin_bonus = min(10.0, max(0.0, (risk_score - bands["MEDIUM"]) * 0.3))
        return round(min(95.0, 45 + evidence_confidence * 0.35 + margin_bonus), 1)
    if band == "LOW":
        return round(min(90.0, 40 + evidence_confidence * 0.4), 1)
    return 50.0


def _fuse_and_decide(rule_band: str, rule_conf: float, ml_probs: dict[str, float] | None):
    if not ml_probs:
        final_band = rule_band
        confidence = rule_conf
        agreement_gap = 0
    else:
        ml_band = max(ml_probs, key=ml_probs.get)
        ml_conf = round(ml_probs[ml_band] * 100, 1)
        agreement_gap = abs(_ORDINAL.get(rule_band, 0) - _ORDINAL.get(ml_band, 0))

        if agreement_gap == 0:
            final_band = rule_band
            confirmation_bonus = max(0.0, min(10.0, (ml_conf - 25) * 0.25))
            confidence = round(min(100.0, rule_conf + confirmation_bonus), 1)
        elif agreement_gap == 1:
            final_band = rule_band if _ORDINAL[rule_band] >= _ORDINAL[ml_band] else ml_band
            confidence = round(max(0.0, rule_conf - 12), 1)
        elif rule_conf >= 70:
            final_band = rule_band
            confidence = round(max(0.0, rule_conf - 15), 1)
        else:
            final_band = rule_band
            confidence = round(max(0.0, min(rule_conf, ml_conf) - 10), 1)

    review_required = False
    abstain_reason = None
    thresholds = _RISK_CONFIG["confidence_bands"]

    if ml_probs and agreement_gap >= 2 and rule_conf < 70:
        final_classification = "REVIEW"
        review_required = True
        abstain_reason = (
            f"Conflicting signals: rule engine indicates {rule_band}, ML classifier indicates "
            f"{max(ml_probs, key=ml_probs.get)}. Confidence insufficient for an automated decision."
        )
    elif confidence < thresholds["LOW"]:
        final_classification = "REVIEW"
        review_required = True
        abstain_reason = "Insufficient evidence for a confident automated SIF classification."
    elif confidence < thresholds["MEDIUM"]:
        final_classification = "REVIEW"
        review_required = True
        abstain_reason = f"Weak evidence (confidence {confidence}%). Routed to human HSE review."
    elif confidence < thresholds["HIGH"]:
        final_classification = final_band
        review_required = True
    else:
        final_classification = final_band
        review_required = False

    return final_classification, confidence, review_required, abstain_reason


def _count_repeat_precursors(db: Session, report: Report, lsr_primary: str) -> int:
    if not report.site_id or lsr_primary == NO_APPLICABLE_RULE:
        return 0
    window_start = report.occurred_at - timedelta(days=90)
    q = (
        db.query(func.count(AnalysisResult.id))
        .join(Report, Report.id == AnalysisResult.report_id)
        .filter(
            Report.site_id == report.site_id,
            Report.id != report.id,
            Report.occurred_at >= window_start,
            Report.occurred_at <= report.occurred_at,
            AnalysisResult.primary_lsr == lsr_primary,
            AnalysisResult.sif_classification.in_([SifClassification.HIGH, SifClassification.MEDIUM]),
        )
    )
    return q.scalar() or 0


def _potential_consequence(band: str) -> str:
    return {
        "HIGH": "Serious injury / fatality",
        "MEDIUM": "Serious injury possible if circumstances were slightly different",
        "LOW": "Minor injury potential",
        "NON_SIF": "No significant injury potential identified",
        "REVIEW": "Undetermined -- pending human HSE review",
        "UNSUPPORTED_LANGUAGE": "Undetermined -- narrative language/script not supported for automated analysis",
    }.get(band, "Undetermined")


def _zero_embedding(provider) -> list[float]:
    dim = getattr(provider, "dimension", None) or 20
    return [0.0] * int(dim)


# ---------------------------------------------------------------------------
# Shared pipeline steps (used by LangGraph nodes AND the sequential fallback)
# ---------------------------------------------------------------------------

def step_preprocess(report: Report) -> dict[str, Any]:
    """Language gate + narrative preparation. Sets language_supported / early halt."""
    raw = report.narrative or ""
    supported = is_pipeline_supported_language(raw)
    return {
        "report_id": report.id,
        "narrative": raw,
        "language_supported": supported,
        "language_reason": None if supported else UNSUPPORTED_LANGUAGE_MESSAGE,
        "matching_text": raw if supported else "",
        "stages": ["preprocess"],
        "halt": not supported,
    }


def step_extract(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("halt"):
        return state
    entities = extract_entities(state["narrative"])
    stages = list(state.get("stages") or []) + ["extract_entities"]
    return {
        **state,
        "stages": stages,
        "entities": entities,
        "hazard_label": entities.hazard_label,
        "energy_categories": list(entities.energy_categories),
    }


def step_barriers_lsr(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("halt"):
        return state
    entities: ExtractedEntities = state["entities"]
    narrative = state["narrative"]
    barrier_findings = analyze_barriers(narrative)
    lsr_result = classify_lsr(narrative, entities)
    stages = list(state.get("stages") or []) + ["barriers_lsr_rules"]
    return {
        **state,
        "stages": stages,
        "barrier_findings": barrier_findings,
        "barrier_types": [bf.barrier_type for bf in barrier_findings],
        "lsr_primary": lsr_result.primary,
        "lsr_result": lsr_result,
    }


def step_ml_fuse(db: Session, report: Report, state: dict[str, Any]) -> dict[str, Any]:
    """Rules + risk + embed + ML fuse. Does NOT persist fingerprint or upsert FAISS."""
    if state.get("halt"):
        return state

    entities: ExtractedEntities = state["entities"]
    barrier_findings: list[BarrierFinding] = state["barrier_findings"]
    lsr_result = state["lsr_result"]
    raw_narrative = state["narrative"]

    repeat_count = _count_repeat_precursors(db, report, lsr_result.primary)
    rule_result = run_rule_engine(entities, barrier_findings, lsr_result.primary, repeat_count)
    risk_score, risk_breakdown = _compute_risk_score(rule_result)
    rule_band = _rule_band(risk_score, entities, rule_result.barrier_failure_component)
    rule_conf = _rule_confidence(risk_score, rule_band, rule_result.rule_confidence)

    provider = get_embedding_provider()
    if not provider.is_ready():
        from app.ml.embeddings import TFIDF_SVD_LOCAL, resolve_embedding_model_name
        if resolve_embedding_model_name() != TFIDF_SVD_LOCAL:
            try:
                provider.load()
            except Exception:
                pass
        else:
            corpus = [r.narrative for r in db.query(Report).all()]
            if raw_narrative not in corpus:
                corpus.append(raw_narrative)
            if len(corpus) >= 3:
                provider.fit(corpus, persist=False)

    ml_probs = None
    embedding = None
    if provider.is_ready():
        embedding = provider.embed_single(raw_narrative)
    if provider.is_ready() and get_classifier().is_ready() and embedding is not None:
        feature_vector = build_feature_vector(embedding, {
            "hazard_energy_component": rule_result.hazard_energy_component,
            "worker_exposure_component": rule_result.worker_exposure_component,
            "barrier_failure_component": rule_result.barrier_failure_component,
            "activity_criticality_component": rule_result.activity_criticality_component,
            "repeat_precursor_component": rule_result.repeat_precursor_component,
        })
        classifier = get_classifier()
        expected = getattr(classifier.model, "n_features_in_", None)
        if expected is None or feature_vector.shape[0] == expected:
            ml_probs = classifier.predict_proba(feature_vector)
    if embedding is None:
        embedding = _zero_embedding(provider)

    final_classification, confidence, review_required, abstain_reason = _fuse_and_decide(
        rule_band, rule_conf, ml_probs
    )

    worst_barrier_type = rule_result.worst_barrier_type
    worst_barrier_status = None
    if barrier_findings:
        worst = max(
            barrier_findings,
            key=lambda bfnd: {
                "PRESENT_EFFECTIVE": 0, "NOT_VERIFIED": 2, "UNKNOWN": 2, "MISSING": 3,
                "BYPASSED": 4, "FAILED": 4,
            }.get(bfnd.status, 1),
        )
        worst_barrier_status = worst.status

    standards = map_standards_tags(
        entities.hazard_label,
        [bf.barrier_type for bf in barrier_findings],
        lsr_result.primary,
    )
    risk_breakdown["standards_tags"] = standards

    stages = list(state.get("stages") or []) + ["ml_fuse"]
    return {
        **state,
        "stages": stages,
        "repeat_count": repeat_count,
        "rule_result": rule_result,
        "risk_score": risk_score,
        "risk_breakdown": risk_breakdown,
        "rule_band": rule_band,
        "embedding": embedding if isinstance(embedding, list) else list(embedding),
        "ml_probs": ml_probs,
        "final_classification": final_classification,
        "confidence": confidence,
        "review_required": review_required,
        "abstain_reason": abstain_reason,
        "worst_barrier_type": worst_barrier_type,
        "worst_barrier_status": worst_barrier_status,
        "standards_tags": standards,
    }


def step_retrieve(db: Session, report: Report, state: dict[str, Any]) -> dict[str, Any]:
    """Retrieve similar reports using this report's embedding BEFORE fingerprint persist."""
    if state.get("halt"):
        return {**state, "stages": list(state.get("stages") or []) + ["faiss_retrieve"], "similar_reports": []}

    similar: list[dict] = []
    try:
        similar = find_similar_by_embedding(
            db,
            state.get("embedding") or [],
            state.get("narrative") or "",
            exclude_id=report.id,
            top_k=5,
        )
    except Exception:
        similar = []

    stages = list(state.get("stages") or []) + ["faiss_retrieve"]
    return {**state, "stages": stages, "similar_reports": similar}


def step_explain_persist(db: Session, report: Report, state: dict[str, Any]) -> AnalysisResult:
    """Build explanation (with retrieved excerpts), persist analysis + fingerprint, FAISS upsert."""
    if state.get("halt"):
        return _persist_language_abstention(db, report, state.get("language_reason") or UNSUPPORTED_LANGUAGE_MESSAGE)

    entities: ExtractedEntities = state["entities"]
    barrier_findings: list[BarrierFinding] = state["barrier_findings"]
    lsr_result = state["lsr_result"]
    rule_result = state["rule_result"]
    final_classification = state["final_classification"]
    confidence = state["confidence"]
    review_required = state["review_required"]
    abstain_reason = state["abstain_reason"]
    risk_score = state["risk_score"]
    risk_breakdown = state["risk_breakdown"]
    rule_band = state["rule_band"]
    embedding = state["embedding"]
    worst_barrier_type = state["worst_barrier_type"]
    worst_barrier_status = state["worst_barrier_status"]
    standards = state["standards_tags"]
    similar_for_llm = state.get("similar_reports") or []
    repeat_count = state["repeat_count"]

    explanation = build_explanation(
        sif_classification=final_classification,
        hazard_label=entities.hazard_label,
        exposure_proximity=entities.exposure_proximity,
        worst_barrier_type=worst_barrier_type,
        worst_barrier_status=worst_barrier_status,
        lsr_primary=lsr_result.primary,
        reason_codes=rule_result.reason_codes,
    )
    explanation, explanation_source = llm_client.enhance_explanation(
        explanation,
        {
            "sif": final_classification, "hazard": entities.hazard_label,
            "lsr": lsr_result.primary, "barrier": worst_barrier_type,
            "barrier_status": worst_barrier_status,
        },
        retrieved_excerpts=similar_for_llm[:3],
    )

    existing = db.query(AnalysisResult).filter(AnalysisResult.report_id == report.id).first()
    if existing:
        db.delete(existing)
        db.flush()

    activity_extracted = (report.activity.name if report.activity else None) or entities.activity_guess
    location_extracted = report.location or entities.location_guess
    potential = _potential_consequence(
        final_classification if final_classification != "REVIEW" else rule_band
    )

    oisd_classification = classify_from_pipeline(
        energy_categories=list(entities.energy_categories or []),
        exposure_proximity=entities.exposure_proximity,
        barrier_findings=barrier_findings,
        repeat_precursor_count=repeat_count,
        sif_classification=final_classification,
    )

    analysis = AnalysisResult(
        report_id=report.id,
        model_version=MODEL_VERSION,
        sif_classification=SifClassification(final_classification),
        confidence=confidence,
        review_required=review_required,
        abstain_reason=abstain_reason,
        risk_score=risk_score,
        risk_breakdown=risk_breakdown,
        reason_codes=rule_result.reason_codes,
        primary_lsr=lsr_result.primary,
        primary_lsr_confidence=lsr_result.primary_confidence,
        secondary_lsr=lsr_result.secondary,
        secondary_lsr_confidence=lsr_result.secondary_confidence,
        lsr_evidence=lsr_result.evidence,
        hazard=entities.hazard_label,
        energy_source=entities.energy_source,
        energy_category=entities.energy_categories[0] if entities.energy_categories else None,
        exposure_description=entities.exposure_description,
        exposure_proximity=entities.exposure_proximity,
        activity_extracted=activity_extracted,
        location_extracted=location_extracted,
        potential_consequence=potential,
        explanation_text=explanation,
        explanation_source=explanation_source,
        original_prediction={
            "sif_classification": final_classification,
            "confidence": confidence,
            "primary_lsr": lsr_result.primary,
            "hazard": entities.hazard_label,
            "energy_source": entities.energy_source,
            "exposure_description": entities.exposure_description,
            "exposure_proximity": entities.exposure_proximity,
            "activity_extracted": activity_extracted,
            "location_extracted": location_extracted,
            "potential_consequence": potential,
            "risk_score": risk_score,
            "reason_codes": rule_result.reason_codes,
        },
        oisd_classification=oisd_classification,
        repeat_precursor_count=repeat_count,
    )
    db.add(analysis)
    db.flush()

    for span in entities.evidence_spans[:5]:
        db.add(ReportEntity(
            analysis_id=analysis.id, entity_type="EXPOSURE_EVIDENCE",
            entity_text=span, evidence_span=span, confidence=0.8,
        ))
    if entities.hazard_label:
        db.add(ReportEntity(
            analysis_id=analysis.id, entity_type="HAZARD",
            entity_text=entities.hazard_label, confidence=0.8,
        ))
    if entities.activity_guess:
        db.add(ReportEntity(
            analysis_id=analysis.id, entity_type="ACTIVITY",
            entity_text=entities.activity_guess, confidence=0.6,
        ))
    if entities.location_guess:
        db.add(ReportEntity(
            analysis_id=analysis.id, entity_type="LOCATION",
            entity_text=entities.location_guess, confidence=0.5,
        ))

    for finding in barrier_findings:
        db.add(ReportBarrier(
            analysis_id=analysis.id,
            barrier_type=finding.barrier_type,
            status=finding.status,
            evidence_text=finding.evidence_text,
            confidence=finding.confidence,
        ))

    barrier_dicts = [
        {"name": bf.barrier_type, "status": bf.status, "evidence": bf.evidence_text}
        for bf in barrier_findings
    ]
    fingerprint_json = build_fingerprint(report, analysis, barrier_dicts, standards_tags=standards)
    existing_fp = db.query(PrecursorFingerprint).filter(PrecursorFingerprint.report_id == report.id).first()
    if existing_fp:
        db.delete(existing_fp)
        db.flush()
    fp_embedding = embedding if isinstance(embedding, list) else list(embedding)
    db.add(PrecursorFingerprint(
        report_id=report.id,
        fingerprint_json=fingerprint_json,
        embedding=fp_embedding,
    ))

    db.commit()
    db.refresh(analysis)

    try:
        faiss_index.upsert_vector(report.id, fp_embedding)
    except faiss_index.DimensionMismatchError:
        try:
            faiss_index.rebuild_from_db(db)
        except Exception:
            pass
    except Exception:
        try:
            faiss_index.rebuild_from_db(db)
        except Exception:
            pass

    try:
        analysis._pipeline_stages = list(state.get("stages") or []) + ["explain_persist"]  # type: ignore[attr-defined]
        analysis._similar_at_analysis = similar_for_llm  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        from app.services.notification_service import maybe_notify_hipo
        maybe_notify_hipo(db, report, analysis)
    except Exception:
        pass

    return analysis


def run_pipeline_steps(db: Session, report: Report) -> AnalysisResult:
    """Sequential fallback: same step functions as the LangGraph path."""
    state = step_preprocess(report)
    if state.get("halt"):
        return step_explain_persist(db, report, state)
    state = step_extract(state)
    state = step_barriers_lsr(state)
    state = step_ml_fuse(db, report, state)
    state = step_retrieve(db, report, state)
    return step_explain_persist(db, report, state)


def analyze_report(db: Session, report: Report) -> AnalysisResult:
    """Public entrypoint — LangGraph orchestrates stages; same DB/API contract."""
    from app.services.pipeline_graph import run_analysis_graph

    return run_analysis_graph(db, report)


def analyze_report_impl(db: Session, report: Report) -> AnalysisResult:
    """Non-graph fallback — calls the same shared step functions."""
    return run_pipeline_steps(db, report)


def _persist_language_abstention(db: Session, report: Report, reason: str) -> AnalysisResult:
    existing = db.query(AnalysisResult).filter(AnalysisResult.report_id == report.id).first()
    if existing:
        db.delete(existing)
        db.flush()
    message = reason or UNSUPPORTED_LANGUAGE_MESSAGE
    analysis = AnalysisResult(
        report_id=report.id,
        model_version=MODEL_VERSION,
        sif_classification=SifClassification.UNSUPPORTED_LANGUAGE,
        confidence=0.0,
        review_required=True,
        abstain_reason=message,
        risk_score=0.0,
        risk_breakdown={
            "analysis_status": "UNSUPPORTED_LANGUAGE",
            "language_abstention": True,
            "_disclaimer": "Language/script unsupported — automated rule NLP was not run.",
        },
        reason_codes=["UNSUPPORTED_LANGUAGE"],
        primary_lsr=NO_APPLICABLE_RULE,
        primary_lsr_confidence=0.0,
        secondary_lsr=None,
        secondary_lsr_confidence=None,
        lsr_evidence=[],
        hazard=None,
        energy_source=None,
        energy_category=None,
        exposure_description=None,
        exposure_proximity="NONE",
        activity_extracted=report.activity.name if report.activity else None,
        location_extracted=report.location,
        potential_consequence=_potential_consequence("UNSUPPORTED_LANGUAGE"),
        explanation_text=message,
        explanation_source="template",
        repeat_precursor_count=0,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


_analyze_report_body = analyze_report_impl
