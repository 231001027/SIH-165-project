"""
Sentence-embedding backbone (blueprint Part 5.4).

Default: multilingual Sentence-Transformers (paraphrase-multilingual-MiniLM-L12-v2).
Tradeoff: cold-start is slower and requires either bundled/cached model weights
or internet access on first load (~120MB download). Pre-download before offline
demos:
  python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

Fallback: set EMBEDDING_MODEL=tfidf-svd-local for English TF-IDF + Truncated-SVD
(fully offline, not cross-lingual). Startup also falls back to TF-IDF with a
visible /health warning if the ST model cannot load.

Rule NLP stays English-only regardless of which embedding backend is active.
"""
from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
_VECTORIZER_PATH = ARTIFACT_DIR / "tfidf_vectorizer.joblib"
_SVD_PATH = ARTIFACT_DIR / "svd_model.joblib"
_ST_META_PATH = ARTIFACT_DIR / "st_provider_meta.joblib"

TFIDF_SVD_LOCAL = "tfidf-svd-local"
DEFAULT_ST_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Runtime visibility for /health (set by init_embedding_backend_at_startup).
_runtime: dict = {
    "configured_model": DEFAULT_ST_MODEL,
    "active_backend": DEFAULT_ST_MODEL,
    "fallback": False,
    "fallback_reason": None,
}


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class TfidfSvdEmbeddingProvider:
    """Local TF-IDF + Truncated-SVD dense embeddings."""

    backend_name = TFIDF_SVD_LOCAL

    def __init__(self):
        self.vectorizer: TfidfVectorizer | None = None
        self.svd: TruncatedSVD | None = None
        self._n_components = 20

    def fit(self, corpus: list[str], *, persist: bool = True) -> None:
        n_components = min(self._n_components, max(2, len(corpus) - 1))
        self.vectorizer = TfidfVectorizer(
            max_features=4000, ngram_range=(1, 2), stop_words="english", min_df=1
        )
        tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.svd = TruncatedSVD(n_components=n_components, random_state=42)
        self.svd.fit(tfidf_matrix)
        if persist:
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

    @property
    def dimension(self) -> int | None:
        if self.svd is None:
            return None
        return int(self.svd.n_components)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self.is_ready():
            raise RuntimeError("EmbeddingProvider not fitted/loaded yet.")
        tfidf_matrix = self.vectorizer.transform(texts)
        vectors = self.svd.transform(tfidf_matrix)
        return _normalize_rows(vectors)

    def embed_single(self, text: str) -> list[float]:
        return self.embed([text])[0].tolist()

    def tfidf_features(self, texts: list[str]):
        if not self.is_ready():
            raise RuntimeError("EmbeddingProvider not fitted/loaded yet.")
        return self.vectorizer.transform(texts)


class SentenceTransformerEmbeddingProvider:
    """Multilingual dense embeddings via sentence-transformers (retrieval only)."""

    def __init__(self, model_name: str = DEFAULT_ST_MODEL):
        self.model_name = model_name
        self.backend_name = model_name
        self._model = None
        self._dimension: int | None = None

    def fit(self, corpus: list[str], *, persist: bool = True) -> None:
        # Pretrained model — fit is a no-op load + optional metadata persist.
        self.load()
        if persist:
            joblib.dump({"model_name": self.model_name, "dimension": self._dimension}, _ST_META_PATH)

    def load(self) -> bool:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for EMBEDDING_MODEL="
                f"{self.model_name!r}. Install with: pip install sentence-transformers"
            ) from exc
        self._model = SentenceTransformer(self.model_name)
        # Probe dimension once
        probe = self._model.encode(["dimension probe"], normalize_embeddings=True)
        self._dimension = int(np.asarray(probe).shape[-1])
        return True

    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def dimension(self) -> int | None:
        return self._dimension

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self.is_ready():
            raise RuntimeError("SentenceTransformerEmbeddingProvider not loaded yet.")
        vectors = self._model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float64)

    def embed_single(self, text: str) -> list[float]:
        return self.embed([text])[0].tolist()

    def tfidf_features(self, texts: list[str]):
        """ST backend has no TF-IDF matrix — clustering falls back to empty terms."""
        raise AttributeError("tfidf_features not available on SentenceTransformerEmbeddingProvider")

    @property
    def vectorizer(self):
        return None


# Back-compat alias used by seed_data and older imports
EmbeddingProvider = TfidfSvdEmbeddingProvider

_provider_singleton = None


def resolve_embedding_model_name() -> str:
    try:
        from app.core.config import get_settings
        name = (get_settings().EMBEDDING_MODEL or DEFAULT_ST_MODEL).strip()
        return name or DEFAULT_ST_MODEL
    except Exception:
        return DEFAULT_ST_MODEL


def load_provider(model_name: str | None = None):
    """Construct and load the embedding provider for the given (or configured) model."""
    name = (model_name or resolve_embedding_model_name()).strip() or DEFAULT_ST_MODEL
    if name == TFIDF_SVD_LOCAL:
        provider = TfidfSvdEmbeddingProvider()
        provider.load()
        return provider
    provider = SentenceTransformerEmbeddingProvider(model_name=name)
    provider.load()
    return provider


def get_embedding_provider():
    global _provider_singleton
    if _provider_singleton is None:
        _provider_singleton = load_provider()
    return _provider_singleton


def reset_embedding_provider() -> None:
    """Clear singleton (tests / re-seed after EMBEDDING_MODEL change)."""
    global _provider_singleton
    _provider_singleton = None


def get_embedding_runtime_status() -> dict:
    """Snapshot for /health — never silently hide a TF-IDF fallback."""
    active = _runtime.get("active_backend") or resolve_embedding_model_name()
    if _runtime.get("fallback"):
        reason = _runtime.get("fallback_reason") or "multilingual model failed to load"
        return {
            "configured_model": _runtime.get("configured_model"),
            "embedding_backend": f"{TFIDF_SVD_LOCAL} (fallback — {reason})",
            "fallback": True,
            "fallback_reason": reason,
        }
    return {
        "configured_model": _runtime.get("configured_model") or active,
        "embedding_backend": active,
        "fallback": False,
        "fallback_reason": None,
    }


def init_embedding_backend_at_startup() -> dict:
    """Attempt to load the configured embedding model; fall back visibly to TF-IDF.

    Logs a WARNING (not silent) on failure. Call from FastAPI startup.
    """
    global _provider_singleton
    configured = resolve_embedding_model_name()
    _runtime["configured_model"] = configured
    _runtime["fallback"] = False
    _runtime["fallback_reason"] = None

    try:
        reset_embedding_provider()
        provider = load_provider(configured)
        _provider_singleton = provider
        _runtime["active_backend"] = getattr(provider, "backend_name", configured) or configured
        logger.info("Embedding backend ready: %s (dim=%s)", _runtime["active_backend"], getattr(provider, "dimension", "?"))
        return get_embedding_runtime_status()
    except Exception as exc:
        reason = f"multilingual model failed to load: {exc}"
        logger.warning(
            "EMBEDDING FALLBACK: could not load %r (%s). "
            "Falling back to %s. Pre-download weights before offline demos: "
            "python -c \"from sentence_transformers import SentenceTransformer; "
            "SentenceTransformer('%s')\"",
            configured,
            exc,
            TFIDF_SVD_LOCAL,
            DEFAULT_ST_MODEL,
        )
        _runtime["fallback"] = True
        _runtime["fallback_reason"] = reason
        _runtime["active_backend"] = TFIDF_SVD_LOCAL
        reset_embedding_provider()
        try:
            provider = TfidfSvdEmbeddingProvider()
            provider.load()  # may be unfitted until seed; still marks backend
            _provider_singleton = provider
        except Exception:
            _provider_singleton = TfidfSvdEmbeddingProvider()
        return get_embedding_runtime_status()


def cosine_similarity_matrix(query_vec: np.ndarray, corpus_vecs: np.ndarray) -> np.ndarray:
    """Vectors from providers are L2-normalized, so cosine reduces to a dot product."""
    if corpus_vecs.size == 0:
        return np.array([])
    return corpus_vecs @ query_vec
