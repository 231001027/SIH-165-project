"""Cross-lingual retrieval + FAISS dimension validation (Phase 2).

Rule NLP stays English-only; these tests cover retrieval embeddings only.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from app.core.config import Settings, get_settings
from app.ml import faiss_index
from app.ml.embeddings import (
    DEFAULT_ST_MODEL,
    SentenceTransformerEmbeddingProvider,
    TfidfSvdEmbeddingProvider,
    load_provider,
    reset_embedding_provider,
    resolve_embedding_model_name,
)


EN_LOTO = (
    "Worker opened a flange on a pressurized hydrocarbon line without "
    "verifying lock-out tag-out isolation. Energy isolation was bypassed."
)
HI_LOTO = (
    "कर्मचारी ने लॉक-आउट टैग-आउट अलगाव सत्यापित किए बिना दबाव वाली "
    "हाइड्रोकार्बन लाइन पर फ्लैंज खोला। ऊर्जा अलगाव बाईपास किया गया।"
)
UNRELATED = (
    "Office stationery inventory was updated after the quarterly audit of "
    "printer toner cartridges and desk supplies."
)


@pytest.fixture()
def clean_faiss(tmp_path, monkeypatch):
    """Isolate FAISS artifacts so tests do not touch the real index."""
    monkeypatch.setattr(faiss_index, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(faiss_index, "_INDEX_PATH", tmp_path / "faiss_index.bin")
    monkeypatch.setattr(faiss_index, "_IDS_PATH", tmp_path / "faiss_report_ids.npy")
    faiss_index._index = None
    faiss_index._report_ids = []
    yield
    faiss_index._index = None
    faiss_index._report_ids = []


def test_faiss_rejects_dimension_mismatch(clean_faiss):
    faiss_index.rebuild_index([1, 2], np.random.randn(2, 8).astype(np.float32))
    with pytest.raises(faiss_index.DimensionMismatchError):
        faiss_index.add_vectors([3], np.random.randn(1, 4).astype(np.float32))
    with pytest.raises(faiss_index.DimensionMismatchError):
        faiss_index.search(np.random.randn(4).astype(np.float32), top_k=1)


def test_faiss_incremental_add(clean_faiss):
    faiss_index.rebuild_index([10], np.ones((1, 4), dtype=np.float32))
    faiss_index.add_vectors([20], np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32))
    hits = faiss_index.search([1.0, 0.0, 0.0, 0.0], top_k=2)
    assert any(rid == 20 for rid, _ in hits)
    assert faiss_index.expected_dimension() == 4


def test_tfidf_provider_embed_shape():
    provider = TfidfSvdEmbeddingProvider()
    provider.fit([EN_LOTO, UNRELATED, "Scaffold work at height without harness."])
    vec = provider.embed_single(EN_LOTO)
    assert len(vec) == provider.dimension
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-5


def test_default_embedding_model_is_multilingual_minilm():
    """Regression guard: Settings default must be multilingual ST, not TF-IDF."""
    # Field default on the Settings class (independent of process env).
    field_default = Settings.model_fields["EMBEDDING_MODEL"].default
    assert field_default == DEFAULT_ST_MODEL, (
        f"EMBEDDING_MODEL default drifted to {field_default!r}; expected {DEFAULT_ST_MODEL!r}"
    )


def test_cross_lingual_loto_beats_unrelated_against_configured_default(monkeypatch):
    """EN ↔ Devanagari LOTO should outrank EN ↔ unrelated using the *default* backend.

    Clears EMBEDDING_MODEL env so resolve_embedding_model_name() reflects the
    Settings default (multilingual MiniLM). A silent revert to tfidf-svd-local
    would fail the default assertion and/or this cosine ranking.
    """
    pytest.importorskip("sentence_transformers")
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    get_settings.cache_clear()
    reset_embedding_provider()

    configured = resolve_embedding_model_name()
    assert configured == DEFAULT_ST_MODEL, (
        f"resolve_embedding_model_name()={configured!r}; expected default {DEFAULT_ST_MODEL!r}"
    )

    provider = load_provider(configured)
    assert isinstance(provider, SentenceTransformerEmbeddingProvider)

    en_vec = np.asarray(provider.embed_single(EN_LOTO))
    hi_vec = np.asarray(provider.embed_single(HI_LOTO))
    un_vec = np.asarray(provider.embed_single(UNRELATED))

    cross = float(en_vec @ hi_vec)
    baseline = float(en_vec @ un_vec)
    assert cross > baseline, (
        f"Expected EN↔HI LOTO cosine ({cross:.4f}) > EN↔unrelated ({baseline:.4f})"
    )

    # Restore test-suite offline default
    monkeypatch.setenv("EMBEDDING_MODEL", "tfidf-svd-local")
    get_settings.cache_clear()
    reset_embedding_provider()
