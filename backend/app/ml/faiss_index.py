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


class DimensionMismatchError(ValueError):
    """Raised when a query/add vector dim does not match the FAISS index."""


def _import_faiss():
    global _faiss
    if _faiss is None:
        import faiss  # type: ignore

        _faiss = faiss
    return _faiss


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def expected_dimension() -> int | None:
    """Return current FAISS index dimension, or None if empty/unloaded."""
    global _index
    if _index is None and not load_index():
        return None
    if _index is None:
        return None
    return int(_index.d)


def rebuild_index(report_ids: list[int], vectors: np.ndarray) -> None:
    """Rebuild and persist a cosine (inner-product on L2-normalized) FAISS index."""
    global _index, _report_ids
    faiss = _import_faiss()
    if vectors is None or len(report_ids) == 0 or vectors.size == 0:
        _index = None
        _report_ids = []
        if _INDEX_PATH.exists():
            _INDEX_PATH.unlink()
        if _IDS_PATH.exists():
            _IDS_PATH.unlink()
        return
    mat = np.asarray(vectors, dtype=np.float32)
    if mat.ndim != 2:
        raise ValueError("vectors must be 2-D")
    mat = _l2_normalize(mat)
    index = faiss.IndexFlatIP(mat.shape[1])
    index.add(mat)
    faiss.write_index(index, str(_INDEX_PATH))
    np.save(_IDS_PATH, np.asarray(report_ids, dtype=np.int64))
    _index = index
    _report_ids = list(report_ids)


def add_vectors(report_ids: list[int], vectors: np.ndarray) -> None:
    """Incrementally append *new* report vectors. Rejects dimension mismatches.

    If any report_id already exists in the index, raises RuntimeError —
    call ``rebuild_from_db`` to replace vectors for existing ids.
    """
    global _index, _report_ids
    faiss = _import_faiss()
    mat = np.asarray(vectors, dtype=np.float32)
    if mat.ndim == 1:
        mat = mat.reshape(1, -1)
    if mat.ndim != 2:
        raise ValueError("vectors must be 1-D or 2-D")
    if len(report_ids) != mat.shape[0]:
        raise ValueError("report_ids length must match vectors rows")
    if mat.size == 0:
        return

    mat = _l2_normalize(mat)

    if _index is None:
        load_index()

    if _index is None or not _report_ids:
        rebuild_index(list(report_ids), mat)
        return

    if mat.shape[1] != _index.d:
        raise DimensionMismatchError(
            f"Embedding dim {mat.shape[1]} does not match FAISS index dim {_index.d}"
        )

    existing = set(_report_ids)
    if any(rid in existing for rid in report_ids):
        raise RuntimeError(
            "FAISS add_vectors cannot replace existing report_ids; call rebuild_from_db"
        )

    _index.add(mat)
    _report_ids.extend(int(r) for r in report_ids)
    faiss.write_index(_index, str(_INDEX_PATH))
    np.save(_IDS_PATH, np.asarray(_report_ids, dtype=np.int64))


def upsert_vector(report_id: int, vector: list[float] | np.ndarray) -> None:
    """Incrementally add a new report vector; skip if id already indexed.

    Re-analysis of an existing report leaves a stale FAISS row until
    ``rebuild_from_db`` (called opportunistically by similarity fallback).
    """
    global _index, _report_ids
    if _index is None:
        load_index()
    vec = np.asarray(vector, dtype=np.float32).reshape(1, -1)
    if _index is not None and report_id in _report_ids:
        return
    if _index is None or not _report_ids:
        rebuild_index([report_id], vec)
        return
    if vec.shape[1] != _index.d:
        raise DimensionMismatchError(
            f"Embedding dim {vec.shape[1]} does not match FAISS index dim {_index.d}"
        )
    faiss = _import_faiss()
    vec = _l2_normalize(vec)
    _index.add(vec)
    _report_ids.append(int(report_id))
    faiss.write_index(_index, str(_INDEX_PATH))
    np.save(_IDS_PATH, np.asarray(_report_ids, dtype=np.int64))


def load_index() -> bool:
    global _index, _report_ids
    faiss = _import_faiss()
    if not _INDEX_PATH.exists() or not _IDS_PATH.exists():
        return False
    _index = faiss.read_index(str(_INDEX_PATH))
    _report_ids = np.load(_IDS_PATH).astype(int).tolist()
    return True


def search(
    query_vec: list[float] | np.ndarray,
    top_k: int = 5,
    exclude_id: int | None = None,
) -> list[tuple[int, float]]:
    """Return list of (report_id, similarity) sorted by descending score."""
    global _index, _report_ids
    if _index is None and not load_index():
        return []
    if _index is None or not _report_ids:
        return []
    faiss = _import_faiss()
    q = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)
    if q.shape[1] != _index.d:
        raise DimensionMismatchError(
            f"Query embedding dim {q.shape[1]} does not match FAISS index dim {_index.d}"
        )
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
    dims = {len(r.embedding) for r in rows if r.embedding is not None}
    if len(dims) > 1:
        raise DimensionMismatchError(f"Mixed embedding dimensions in DB: {dims}")
    ids = [r.report_id for r in rows]
    vecs = np.array([r.embedding for r in rows], dtype=np.float32)
    rebuild_index(ids, vecs)
    return len(ids)
