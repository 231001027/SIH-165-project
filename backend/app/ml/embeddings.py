"""
Sentence-embedding backbone (blueprint Part 5.4 "Embedding + classifier (ML)").

Design decision (documented per source-discipline rules): the blueprint's
preferred choice is a Sentence-Transformer model. That pulls a multi-hundred-
MB PyTorch + transformer-weights download, which is a poor fit for a
hackathon environment that must install and run reliably offline in minutes.
We instead use a TF-IDF + Truncated-SVD ("latent semantic") embedding fit
locally on the report corpus in seconds with no network dependency. It plays
the same architectural role -- a dense vector per report used for similarity
search, clustering and as classifier input -- and the EmbeddingProvider
interface below is intentionally the only thing the rest of the app talks
to, so a real Sentence-Transformer backend can be swapped in later (set
EMBEDDING_MODEL in .env and extend `load_provider`) without touching
similarity/clustering/classification call sites.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
_VECTORIZER_PATH = ARTIFACT_DIR / "tfidf_vectorizer.joblib"
_SVD_PATH = ARTIFACT_DIR / "svd_model.joblib"


class EmbeddingProvider:
    def __init__(self):
        self.vectorizer: TfidfVectorizer | None = None
        self.svd: TruncatedSVD | None = None
        # Kept deliberately small relative to the hackathon-scale gold set
        # (~100-200 rows): a high-dimensional embedding concatenated with the
        # 5 rule-engine components would badly overfit the SIF classifier
        # (see app/ml/classifier.py) on so few training rows.
        self._n_components = 20

    def fit(self, corpus: list[str]) -> None:
        n_components = min(self._n_components, max(2, len(corpus) - 1))
        self.vectorizer = TfidfVectorizer(
            max_features=4000, ngram_range=(1, 2), stop_words="english", min_df=1
        )
        tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.svd = TruncatedSVD(n_components=n_components, random_state=42)
        self.svd.fit(tfidf_matrix)
        joblib.dump(self.vectorizer, _VECTORIZER_PATH)
        joblib.dump(self.svd, _SVD_PATH)

    def load(self) -> bool:
        if _VECTORIZER_PATH.exists() and _SVD_PATH.exists():
            self.vectorizer = joblib.load(_VECTORIZER_PATH)
            self.svd = joblib.load(_SVD_PATH)
            return True
        return False

    def is_ready(self) -> bool:
        return self.vectorizer is not None and self.svd is not None

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self.is_ready():
            raise RuntimeError("EmbeddingProvider not fitted/loaded yet.")
        tfidf_matrix = self.vectorizer.transform(texts)
        vectors = self.svd.transform(tfidf_matrix)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def embed_single(self, text: str) -> list[float]:
        return self.embed([text])[0].tolist()

    def tfidf_features(self, texts: list[str]):
        if not self.is_ready():
            raise RuntimeError("EmbeddingProvider not fitted/loaded yet.")
        return self.vectorizer.transform(texts)


_provider_singleton: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider_singleton
    if _provider_singleton is None:
        _provider_singleton = EmbeddingProvider()
        _provider_singleton.load()
    return _provider_singleton


def cosine_similarity_matrix(query_vec: np.ndarray, corpus_vecs: np.ndarray) -> np.ndarray:
    """Vectors from EmbeddingProvider.embed are already L2-normalized, so
    cosine similarity reduces to a dot product."""
    if corpus_vecs.size == 0:
        return np.array([])
    return corpus_vecs @ query_vec
