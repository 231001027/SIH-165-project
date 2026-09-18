"""FAISS index over precursor fingerprint embeddings for similarity / RAG retrieval."""
from __future__ import annotations

from pathlib import Path

import numpy as np

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
_INDEX_PATH = ARTIFACT_DIR / "faiss_index.bin"
_IDS_PATH = ARTIFACT_DIR / "faiss_report_ids.npy"

_faiss = None
_index = None
_report_ids: list[int] = []


def _import_faiss():
    global _faiss
    if _faiss is None:
        import faiss  # type: ignore

        _faiss = faiss
    return _faiss


def rebuild_index(report_ids: list[int], vectors: np.ndarray) -> None:
    """Rebuild and persist a cosine (inner-product on L2-normalized) FAISS index."""
    global _index, _report_ids
    faiss = _import_faiss()
    if vectors is None or len(report_ids) == 0 or vectors.size == 0:
        _index = None
        _report_ids = []
        return
    mat = np.asarray(vectors, dtype=np.float32)
    if mat.ndim != 2:
        raise ValueError("vectors must be 2-D")
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = mat / norms
    index = faiss.IndexFlatIP(mat.shape[1])
    index.add(mat)
    faiss.write_index(index, str(_INDEX_PATH))
    np.save(_IDS_PATH, np.asarray(report_ids, dtype=np.int64))
    _index = index
    _report_ids = list(report_ids)


def load_index() -> bool:
    global _index, _report_ids
    faiss = _import_faiss()
    if not _INDEX_PATH.exists() or not _IDS_PATH.exists():
        return False
    _index = faiss.read_index(str(_INDEX_PATH))
    _report_ids = np.load(_IDS_PATH).astype(int).tolist()
    return True


def search(query_vec: list[float] | np.ndarray, top_k: int = 5, exclude_id: int | None = None) -> list[tuple[int, float]]:
    """Return list of (report_id, similarity) sorted by descending score."""
    global _index, _report_ids
    if _index is None and not load_index():
        return []
    if _index is None or not _report_ids:
        return []
    faiss = _import_faiss()
    q = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)
    norm = np.linalg.norm(q)
    if norm > 0:
        q = q / norm
    k = min(top_k + (1 if exclude_id is not None else 0), len(_report_ids))
    if k <= 0:
        return []
    scores, indices = _index.search(q, k)
    out: list[tuple[int, float]] = []
    for idx, score in zip(indices[0], scores[0]):
        if idx < 0 or idx >= len(_report_ids):
            continue
        rid = int(_report_ids[idx])
        if exclude_id is not None and rid == exclude_id:
            continue
        out.append((rid, float(score)))
        if len(out) >= top_k:
            break
    return out


def rebuild_from_db(db) -> int:
    """Rebuild FAISS from all PrecursorFingerprint rows. Returns vector count."""
    from app.models.analysis import PrecursorFingerprint

    rows = db.query(PrecursorFingerprint).all()
    if not rows:
        rebuild_index([], np.zeros((0, 1), dtype=np.float32))
        return 0
    ids = [r.report_id for r in rows]
    vecs = np.array([r.embedding for r in rows], dtype=np.float32)
    rebuild_index(ids, vecs)
    return len(ids)
