"""Retrain SIF classifier from gold train labels + human Feedback corrections.

PUBLIC_CORPUS rows are never used for training.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from app.ml.classifier import SifClassifier, build_feature_vector, reload_classifier, LABELS
from app.ml.embeddings import get_embedding_provider
from app.models.analysis import AnalysisResult, PrecursorFingerprint
from app.models.report import Report, ReportSource
from app.models.review import Feedback
from app.services.analysis_service import _RISK_CONFIG

_WEIGHTS = _RISK_CONFIG["weights"]
ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "ml" / "artifacts"
_RETRAIN_META = ARTIFACT_DIR / "last_retrain.json"


def _components_from_analysis(analysis: AnalysisResult) -> dict[str, float]:
    rb = analysis.risk_breakdown or {}
    return {
        "hazard_energy_component": rb.get("hazard_energy", 0) / max(_WEIGHTS["hazard_energy"], 1e-6),
        "worker_exposure_component": rb.get("worker_exposure", 0) / max(_WEIGHTS["worker_exposure"], 1e-6),
        "barrier_failure_component": rb.get("barrier_failure", 0) / max(_WEIGHTS["barrier_failure"], 1e-6),
        "activity_criticality_component": rb.get("activity_criticality", 0) / max(_WEIGHTS["activity_criticality"], 1e-6),
        "repeat_precursor_component": rb.get("repeat_precursor", 0) / max(_WEIGHTS["repeat_precursor"], 1e-6),
    }


def retrain_classifier_from_feedback(db: Session) -> dict:
    """Build training set from current AnalysisResult labels (post-review) for
    non-PUBLIC_CORPUS reports that have a fingerprint, preferring Feedback
    corrections for sif_classification when present."""
    provider = get_embedding_provider()
    if not provider.is_ready():
        return {"trained": False, "reason": "Embedding provider not ready."}

    # Latest sif correction per report from Feedback
    feedback_rows = (
        db.query(Feedback)
        .filter(Feedback.field_name == "sif_classification")
        .order_by(Feedback.created_at.asc())
        .all()
    )
    sif_overrides: dict[int, str] = {}
    for fb in feedback_rows:
        if fb.new_value in LABELS:
            sif_overrides[fb.report_id] = fb.new_value

    rows = (
        db.query(Report, AnalysisResult, PrecursorFingerprint)
        .join(AnalysisResult, AnalysisResult.report_id == Report.id)
        .join(PrecursorFingerprint, PrecursorFingerprint.report_id == Report.id)
        .filter(Report.source != ReportSource.PUBLIC_CORPUS)
        .all()
    )

    X, y = [], []
    used_feedback = 0
    expected_dim = getattr(provider, "dimension", None)
    for report, analysis, fp in rows:
        if not fp.embedding:
            continue
        if expected_dim is not None and len(fp.embedding) != expected_dim:
            continue
        label = sif_overrides.get(report.id)
        if label:
            used_feedback += 1
        else:
            raw = analysis.sif_classification.value if hasattr(analysis.sif_classification, "value") else str(analysis.sif_classification)
            if raw not in LABELS:
                continue  # skip REVIEW
            label = raw
        X.append(build_feature_vector(fp.embedding, _components_from_analysis(analysis)))
        y.append(label)

    if len(X) < 10:
        return {"trained": False, "n_train": len(X), "feedback_overrides": used_feedback,
                "reason": "Need at least 10 labelled rows."}

    classifier = SifClassifier()
    metrics = classifier.train(np.array(X), y)
    reload_classifier()
    meta = {
        "trained": True,
        "n_train": len(X),
        "feedback_overrides": used_feedback,
        "artifact_version": f"feedback-retrain-{len(X)}-{used_feedback}",
        **metrics,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    _RETRAIN_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
