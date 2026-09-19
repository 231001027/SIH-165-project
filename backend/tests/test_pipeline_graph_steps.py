"""Regression guards: LangGraph steps produce real intermediate payloads; RAG works on first analyze."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from app.ml import faiss_index
from app.ml.embeddings import TfidfSvdEmbeddingProvider, reset_embedding_provider
from app.models.analysis import PrecursorFingerprint
from app.models.report import Report, ReportSource, ReportType
from app.services.pipeline_graph import run_steps_collecting_states
from app.services.similarity_service import find_similar_by_embedding


LOTO_NARRATIVE = (
    "Technician opened a flange before confirming isolation. "
    "Residual pressure was released. No injury occurred."
)
SIMILAR_CORPUS = (
    "Line opened before confirming isolation and residual pressure released "
    "onto the maintenance crew standing at the flange."
)


@pytest.fixture()
def tfidf_provider(monkeypatch):
    """Force local TF-IDF for fast, offline pipeline tests."""
    reset_embedding_provider()
    provider = TfidfSvdEmbeddingProvider()
    provider.fit(
        [
            LOTO_NARRATIVE,
            SIMILAR_CORPUS,
            "Office stationery inventory was updated after the quarterly audit.",
            "Scaffold work at height without a harness on the elevated platform.",
        ],
        persist=False,
    )

    def _get():
        return provider

    monkeypatch.setattr("app.ml.embeddings.get_embedding_provider", _get)
    monkeypatch.setattr("app.services.analysis_service.get_embedding_provider", _get)
    yield provider
    reset_embedding_provider()


@pytest.fixture()
def clean_faiss(tmp_path, monkeypatch):
    monkeypatch.setattr(faiss_index, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(faiss_index, "_INDEX_PATH", tmp_path / "faiss_index.bin")
    monkeypatch.setattr(faiss_index, "_IDS_PATH", tmp_path / "faiss_report_ids.npy")
    faiss_index._index = None
    faiss_index._report_ids = []
    yield
    faiss_index._index = None
    faiss_index._report_ids = []


def _add_report(db, narrative: str, code: str) -> Report:
    r = Report(
        report_code=code,
        report_type=ReportType.NEAR_MISS,
        title="Test",
        narrative=narrative,
        source=ReportSource.MANUAL,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_each_pipeline_node_produces_distinct_real_output(db_session, tfidf_provider, clean_faiss):
    report = _add_report(db_session, LOTO_NARRATIVE, "PIPE-NODE-1")
    snapshots, analysis = run_steps_collecting_states(db_session, report)

    by_node = {s["node"]: s for s in snapshots}
    assert set(by_node) >= {"preprocess", "extract", "barriers_lsr", "ml_fuse", "retrieve", "explain_persist"}

    assert by_node["preprocess"]["language_supported"] is True
    assert by_node["preprocess"]["halt"] is False
    assert "preprocess" in by_node["preprocess"]["stages"]

    assert by_node["extract"]["has_entities"] is True
    assert by_node["extract"]["hazard_label"]  # real extraction, not just a stage name
    assert "PRESSURE" in by_node["extract"]["energy_categories"] or by_node["extract"]["hazard_label"]

    assert "Isolation / LOTO" in by_node["barriers_lsr"]["barrier_types"]
    assert by_node["barriers_lsr"]["lsr_primary"] == "Energy Isolation"

    assert by_node["ml_fuse"]["final_classification"] in {"HIGH", "MEDIUM", "LOW", "NON_SIF", "REVIEW"}
    assert by_node["ml_fuse"]["embedding_dim"] and by_node["ml_fuse"]["embedding_dim"] > 0
    assert by_node["ml_fuse"]["confidence"] is not None

    # retrieve may be empty if no other FPS exist yet — still must set similar_count key
    assert "similar_count" in by_node["retrieve"]
    assert "faiss_retrieve" in by_node["retrieve"]["stages"]

    assert by_node["explain_persist"]["analysis_id"] == analysis.id
    assert analysis.sif_classification.value == by_node["ml_fuse"]["final_classification"]


def test_first_analysis_retrieval_nonempty_when_corpus_exists(db_session, tfidf_provider, clean_faiss):
    """Fingerprint-timing fix: retrieve uses embedding before this report's FP is persisted."""
    corpus = _add_report(db_session, SIMILAR_CORPUS, "PIPE-CORPUS-1")
    emb = tfidf_provider.embed_single(SIMILAR_CORPUS)
    db_session.add(PrecursorFingerprint(
        report_id=corpus.id,
        fingerprint_json={"sif_potential": "HIGH", "life_saving_rule": "Energy Isolation"},
        embedding=emb,
    ))
    db_session.commit()
    faiss_index.rebuild_index([corpus.id], np.asarray([emb], dtype=np.float32))

    query = _add_report(db_session, LOTO_NARRATIVE, "PIPE-QUERY-1")
    # No fingerprint for query yet — retrieve-by-embedding must still find corpus
    hits = find_similar_by_embedding(
        db_session, tfidf_provider.embed_single(LOTO_NARRATIVE), LOTO_NARRATIVE,
        exclude_id=query.id, top_k=3,
    )
    assert hits, "expected non-empty similar hits against existing corpus fingerprint"
    assert hits[0]["report_id"] == corpus.id

    snapshots, analysis = run_steps_collecting_states(db_session, query)
    retrieve_snap = next(s for s in snapshots if s["node"] == "retrieve")
    assert retrieve_snap["similar_count"] >= 1
    assert analysis.id is not None
