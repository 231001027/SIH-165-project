"""
The core orchestrator: runs every pipeline stage (blueprint Stages 3-11) for
one report and persists the result. This is the single place the rule
engine, the ML classifier, the LSR engine and the barrier engine are fused
into one final, explainable SIF classification -- see `_fuse_and_decide` for
the abstention logic (blueprint Part 3.2).
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import (
    AnalysisResult, ReportEntity, ReportBarrier, PrecursorFingerprint, SifClassification,
)
from app.models.report import Report
from app.nlp.entity_extraction import extract_entities
from app.nlp.negation import analyze_barriers
from app.rules.lsr_engine import classify_lsr, NO_APPLICABLE_RULE
from app.rules.sif_rules import run_rule_engine
from app.ml.embeddings import get_embedding_provider
from app.ml.classifier import get_classifier, build_feature_vector, LABELS
from app.services.explanation_service import build_explanation
from app.services.fingerprint_service import build_fingerprint
from app.services import llm_client
from app.services.similarity_service import find_similar_reports
from app.ml import faiss_index
from app.nlp.preprocess import (
    is_pipeline_supported_language,
    UNSUPPORTED_LANGUAGE_MESSAGE,
)
from app.services.standards_tags import map_standards_tags

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
        return  # not enough corpus yet; caller (single-report path) handles this itself
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
    # A report can show genuine SIF-precursor risk purely from a barrier/process
    # failure (e.g. "maintenance began without a valid work permit") even when no
    # energy-category keyword was extracted -- so barrier evidence, not just
    # hazard/exposure evidence, must be able to keep a report out of NON_SIF.
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
    """Confidence that the BAND ITSELF is correct -- not a measure of how
    severe/risky the situation is. A calm, unambiguous NON_SIF report (little
    or no hazard evidence, nothing contradictory) should be classified with
    HIGH confidence; a report with only one weak, isolated signal should not,
    regardless of which band it lands in. `evidence_confidence` is the rule
    engine's own evidence-density signal (app.rules.sif_rules.RuleEngineResult
    .rule_confidence, 0-100: how many independent risk signals actually
    fired)."""
    if band == "NON_SIF":
        # Confidence in "nothing hazardous here" grows as risk_score shrinks
        # toward zero, independent of the (deliberately sparse) evidence count.
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
    """Returns (final_classification, confidence, review_required, abstain_reason).

    Design note: the deterministic rule engine is treated as the primary,
    always-available "safety baseline" (blueprint Part 5.4) -- its confidence
    drives the outcome. The ML classifier acts as a MODIFIER (a confirming
    bonus or a disagreement penalty), not an equally-weighted average partner.
    This matters in practice: with only ~100 hackathon-scale training rows,
    the classifier is deliberately regularized to avoid overfitting (see
    app/ml/classifier.py), which naturally flattens its predicted
    probabilities (e.g. a 0.35 argmax instead of 0.90). A 50/50 average with
    such a naturally-flatter signal would drag down confidence -- and trigger
    abstention -- even when the two layers agree on the classification, which
    is not the intended abstention behaviour."""
    if not ml_probs:
        final_band = rule_band
        confidence = rule_conf
        agreement_gap = 0
    else:
        ml_band = max(ml_probs, key=ml_probs.get)
        ml_conf = round(ml_probs[ml_band] * 100, 1)
        agreement_gap = abs(_ORDINAL.get(rule_band, 0) - _ORDINAL.get(ml_band, 0))

        if agreement_gap == 0:
            # ML confirms the rule engine: small bonus, scaled by how much the
            # classifier's own probability exceeds the 4-class uniform baseline (25%).
            final_band = rule_band
            confirmation_bonus = max(0.0, min(10.0, (ml_conf - 25) * 0.25))
            confidence = round(min(100.0, rule_conf + confirmation_bonus), 1)
        elif agreement_gap == 1:
            # Adjacent disagreement: bias toward the higher-severity band
            # (recall-first principle, blueprint Part 8.1) but discount confidence.
            final_band = rule_band if _ORDINAL[rule_band] >= _ORDINAL[ml_band] else ml_band
            confidence = round(max(0.0, rule_conf - 12), 1)
        elif rule_conf >= 70:
            # The rule engine is the deterministic, auditable safety baseline
            # (blueprint Part 5.4): if it is itself highly confident, a sharp
            # disagreement from the ML layer is treated as the ML layer being
            # wrong, not as grounds to hide the rule engine's evidence-backed
            # result -- it is still flagged for a human to glance at, though.
            final_band = rule_band
            confidence = round(max(0.0, rule_conf - 15), 1)
        else:
            final_band = rule_band  # placeholder; overridden to REVIEW below
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
    # Trailing 90-day window per blueprint Part 2.4 RepeatPrecursor component.
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


def analyze_report(db: Session, report: Report) -> AnalysisResult:
    """Public entrypoint — LangGraph orchestrates stages; same DB/API contract."""
    from app.services.pipeline_graph import run_analysis_graph

    return run_analysis_graph(db, report)


def analyze_report_impl(db: Session, report: Report) -> AnalysisResult:
    """Core analysis implementation (called by LangGraph nodes as one fused path)."""
    raw_narrative = report.narrative or ""

    # English-only rule NLP gate — fail closed before any entity/barrier/LSR work.
    if not is_pipeline_supported_language(raw_narrative):
        return _persist_language_abstention(db, report, UNSUPPORTED_LANGUAGE_MESSAGE)

    narrative = raw_narrative

    entities = extract_entities(narrative)
    barrier_findings = analyze_barriers(narrative)
    lsr_result = classify_lsr(narrative, entities)
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
                # In-memory only — never clobber seed-fitted on-disk artifacts
                # with a tiny cold-start corpus (would shrink SVD dims and break
                # the classifier feature width).
                provider.fit(corpus, persist=False)

    ml_probs = None
    classifier = get_classifier()
    embedding = None
    if provider.is_ready():
        embedding = provider.embed_single(raw_narrative)
    if provider.is_ready() and classifier.is_ready() and embedding is not None:
        feature_vector = build_feature_vector(embedding, {
            "hazard_energy_component": rule_result.hazard_energy_component,
            "worker_exposure_component": rule_result.worker_exposure_component,
            "barrier_failure_component": rule_result.barrier_failure_component,
            "activity_criticality_component": rule_result.activity_criticality_component,
            "repeat_precursor_component": rule_result.repeat_precursor_component,
        })
        expected = getattr(classifier.model, "n_features_in_", None)
        if expected is None or feature_vector.shape[0] == expected:
            ml_probs = classifier.predict_proba(feature_vector)
    if embedding is None:
        embedding = [0.0] * 20

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

    explanation = build_explanation(
        sif_classification=final_classification,
        hazard_label=entities.hazard_label,
        exposure_proximity=entities.exposure_proximity,
        worst_barrier_type=worst_barrier_type,
        worst_barrier_status=worst_barrier_status,
        lsr_primary=lsr_result.primary,
        reason_codes=rule_result.reason_codes,
    )

    # RAG: retrieve similar with excerpts for bounded LLM polish (before persisting this FP).
    similar_for_llm: list[dict] = []
    try:
        similar_for_llm = find_similar_reports(db, report.id, top_k=3)
    except Exception:
        similar_for_llm = []

    explanation, explanation_source = llm_client.enhance_explanation(
        explanation,
        {
            "sif": final_classification, "hazard": entities.hazard_label,
            "lsr": lsr_result.primary, "barrier": worst_barrier_type,
            "barrier_status": worst_barrier_status,
        },
        retrieved_excerpts=similar_for_llm,
    )

    existing = db.query(AnalysisResult).filter(AnalysisResult.report_id == report.id).first()
    if existing:
        db.delete(existing)
        db.flush()

    activity_extracted = (report.activity.name if report.activity else None) or entities.activity_guess
    location_extracted = report.location or entities.location_guess

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
        potential_consequence=_potential_consequence(final_classification if final_classification != "REVIEW" else rule_band),
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
            "potential_consequence": _potential_consequence(final_classification if final_classification != "REVIEW" else rule_band),
            "risk_score": risk_score,
            "reason_codes": rule_result.reason_codes,
        },
        repeat_precursor_count=repeat_count,
    )
    db.add(analysis)
    db.flush()

    for span in entities.evidence_spans[:5]:
        db.add(ReportEntity(analysis_id=analysis.id, entity_type="EXPOSURE_EVIDENCE",
                             entity_text=span, evidence_span=span, confidence=0.8))
    if entities.hazard_label:
        db.add(ReportEntity(analysis_id=analysis.id, entity_type="HAZARD",
                             entity_text=entities.hazard_label, confidence=0.8))
    if entities.activity_guess:
        db.add(ReportEntity(analysis_id=analysis.id, entity_type="ACTIVITY",
                             entity_text=entities.activity_guess, confidence=0.6))
    if entities.location_guess:
        db.add(ReportEntity(analysis_id=analysis.id, entity_type="LOCATION",
                             entity_text=entities.location_guess, confidence=0.5))

    for finding in barrier_findings:
        db.add(ReportBarrier(
            analysis_id=analysis.id,
            barrier_type=finding.barrier_type,
            status=finding.status,
            evidence_text=finding.evidence_text,
            confidence=finding.confidence,
        ))

    barrier_dicts = [{"name": bf.barrier_type, "status": bf.status, "evidence": bf.evidence_text} for bf in barrier_findings]
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
        # Incremental insert for new reports; existing ids stay until rebuild_from_db
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

    return analysis


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


# Keep a private alias used by older imports/tests if any
_analyze_report_body = analyze_report_impl
