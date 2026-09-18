"""
Precursor clustering (blueprint Part 1.3 Stage 13, Part 4.2).

Uses KMeans over the same TF-IDF+SVD embedding used for similarity search.
The blueprint's preferred method is HDBSCAN; we use KMeans (its own
documented fallback, Part 6/Stage 13 table) to avoid HDBSCAN's compiled
C-extension install risk on a bare Windows machine. Cluster labels are
generated automatically from each cluster's top distinctive TF-IDF terms
rather than hardcoded, per the "no arbitrary hardcoded cluster names"
requirement.
"""
from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans

from app.ml.embeddings import get_embedding_provider


def choose_k(n_samples: int) -> int:
    if n_samples < 6:
        return max(1, n_samples)
    return max(2, min(8, n_samples // 6))


def cluster_reports(narratives: list[str], embeddings: np.ndarray) -> tuple[list[int], dict[int, dict]]:
    """Returns (assignment per report, cluster_id -> {label, top_terms, size})."""
    n = len(narratives)
    if n == 0:
        return [], {}

    k = choose_k(n)
    if k <= 1:
        labels = [0] * n
    else:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(embeddings).tolist()

    provider = get_embedding_provider()
    cluster_meta: dict[int, dict] = {}
    unique_clusters = sorted(set(labels))
    for cluster_id in unique_clusters:
        member_idxs = [i for i, l in enumerate(labels) if l == cluster_id]
        member_texts = [narratives[i] for i in member_idxs]
        top_terms = _top_terms_for_cluster(provider, member_texts)
        cluster_meta[cluster_id] = {
            "label": _label_from_terms(top_terms),
            "top_terms": top_terms,
            "size": len(member_idxs),
        }
    return labels, cluster_meta


def _top_terms_for_cluster(provider, texts: list[str], top_n: int = 5) -> list[str]:
    if not texts or not provider.is_ready():
        return []
    # Sentence-Transformers backend has no TF-IDF vocabulary — fall back to
    # simple token frequency so cluster labels still render.
    if not hasattr(provider, "tfidf_features") or getattr(provider, "vectorizer", None) is None:
        from collections import Counter
        from app.nlp.preprocess import tokenize
        counts: Counter[str] = Counter()
        for t in texts:
            counts.update(tok.lower() for tok in tokenize(t) if len(tok) > 3)
        return [w for w, _ in counts.most_common(top_n)]
    try:
        tfidf_matrix = provider.tfidf_features(texts)
    except (AttributeError, RuntimeError):
        return []
    mean_scores = np.asarray(tfidf_matrix.mean(axis=0)).ravel()
    feature_names = provider.vectorizer.get_feature_names_out()
    top_idx = mean_scores.argsort()[::-1][:top_n]
    return [feature_names[i] for i in top_idx if mean_scores[i] > 0]


def _label_from_terms(top_terms: list[str]) -> str:
    if not top_terms:
        return "Unlabelled precursor cluster"
    words = [t.replace("_", " ") for t in top_terms[:3]]
    return " / ".join(w.title() for w in words) + " precursors"
