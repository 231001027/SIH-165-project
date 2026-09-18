"""Assert feedback retrain writes last_retrain.json artifact metadata."""
from __future__ import annotations

import json
import uuid

import pytest

from app.ml.embeddings import TfidfSvdEmbeddingProvider
import app.ml.embeddings as emb_mod
import app.ml.classifier as clf_mod
from app.models.analysis import AnalysisResult, PrecursorFingerprint, SifClassification
from app.models.report import Report, ReportSource
from app.models.review import Feedback, HumanReview, ReviewAction
from app.services.retrain_service import retrain_classifier_from_feedback


@pytest.fixture()
def fitted_provider(tmp_path, monkeypatch):
    """Isolate TF-IDF artifacts and fit a tiny provider for the test DB."""
    art = tmp_path / "emb_art"
    art.mkdir()
    monkeypatch.setattr(emb_mod, "ARTIFACT_DIR", art)
    monkeypatch.setattr(emb_mod, "_VECTORIZER_PATH", art / "tfidf_vectorizer.joblib")
    monkeypatch.setattr(emb_mod, "_SVD_PATH", art / "svd_model.joblib")
    provider = TfidfSvdEmbeddingProvider()
    corpus = [
        f"Energy isolation bypass on pressurized line case {i}" for i in range(12)
    ] + [
        f"Office stationery audit toner case {i}" for i in range(12)
    ]
    provider.fit(corpus, persist=True)
    emb_mod.reset_embedding_provider()
    emb_mod._provider_singleton = provider
    yield provider
    emb_mod.reset_embedding_provider()


def test_retrain_writes_last_retrain_artifact(
    db_session, admin_user, fitted_provider, tmp_path, monkeypatch
):
    clf_art = tmp_path / "clf_art"
    clf_art.mkdir()
    monkeypatch.setattr(clf_mod, "ARTIFACT_DIR", clf_art)
    monkeypatch.setattr(clf_mod, "_MODEL_PATH", clf_art / "sif_classifier.joblib")
    monkeypatch.setattr("app.services.retrain_service.ARTIFACT_DIR", clf_art)
    monkeypatch.setattr(
        "app.services.retrain_service._RETRAIN_META", clf_art / "last_retrain.json"
    )
    clf_mod._classifier_singleton = None

    suffix = uuid.uuid4().hex[:8]
    labels = ["HIGH", "MEDIUM", "LOW", "NON_SIF"] * 3
    first_report = None
    for i, lab in enumerate(labels):
        report = Report(
            report_code=f"RT-{suffix}-{i:03d}",
            title=f"Retrain case {i}",
            narrative=f"Energy isolation bypass on pressurized line case {i}",
            source=ReportSource.SYNTHETIC_SEED,
        )
        db_session.add(report)
        db_session.flush()
        if first_report is None:
            first_report = report
        emb = fitted_provider.embed_single(report.narrative)
        db_session.add(
            AnalysisResult(
                report_id=report.id,
                model_version="test",
                sif_classification=SifClassification[lab],
                confidence=70.0,
                review_required=False,
                risk_score=50.0,
                risk_breakdown={
                    "hazard_energy": 20,
                    "worker_exposure": 10,
                    "barrier_failure": 10,
                    "activity_criticality": 5,
                    "repeat_precursor": 0,
                },
                reason_codes=[],
                primary_lsr="Energy Isolation",
                primary_lsr_confidence=0.8,
                explanation_text="test",
            )
        )
        db_session.add(
            PrecursorFingerprint(
                report_id=report.id,
                fingerprint_json={"sif_potential": lab},
                embedding=emb,
            )
        )

    review = HumanReview(
        report_id=first_report.id,
        reviewer_id=admin_user.id,
        action=ReviewAction.MODIFY,
        reason="correct SIF",
        corrected_fields={"sif_classification": "LOW"},
    )
    db_session.add(review)
    db_session.flush()
    db_session.add(
        Feedback(
            report_id=first_report.id,
            review_id=review.id,
            field_name="sif_classification",
            old_value="HIGH",
            new_value="LOW",
            reviewer_id=admin_user.id,
        )
    )
    db_session.commit()

    emb_mod._provider_singleton = fitted_provider
    result = retrain_classifier_from_feedback(db_session)
    assert result.get("trained") is True, result
    assert result.get("n_train", 0) >= 10
    assert "artifact_version" in result
    assert result["feedback_overrides"] >= 1

    meta_path = clf_art / "last_retrain.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["trained"] is True
    assert meta["artifact_version"] == result["artifact_version"]
    assert meta["n_train"] == result["n_train"]
    assert (clf_art / "sif_classifier.joblib").exists()
