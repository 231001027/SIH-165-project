# SIFGuard-OIL Functionality Backlog Plan

Audit date: 2026-09-18. Updated after Phase 2 multilingual retrieval landing.

## Conflict reconciliation (canonical)

| Concern | Rule NLP pipeline | Retrieval / RAG |
|--------|-------------------|-----------------|
| Language | **English-only honesty** via `is_pipeline_supported_language` → `UNSUPPORTED_LANGUAGE` (no silent empty analysis) | Multilingual sentence-transformers when `EMBEDDING_MODEL` ≠ `tfidf-svd-local` |
| Hindi / Devanagari | **Fail closed** for rule extraction (not lexicon-gloss “supported”) | May retrieve via ST embeddings (Phase 2) |
| ISO / PSM | Kind-3 team tags only; never claim Kind-1 derivation without citations | N/A |

Document this split in README / About whenever either side changes.

---

## Gap matrix

| # | Prompt area | Status | Evidence / gap |
|---|-------------|--------|----------------|
| 1 | Language/script guard | **DONE** | `is_pipeline_supported_language`, `UNSUPPORTED_LANGUAGE`, UI banners, About English-only |
| 2 | Multilingual sentence-transformers + FAISS incremental + cross-lingual test | **DONE** | `load_provider` / `EMBEDDING_MODEL`; ST provider; FAISS `add_vectors` + dim check; `test_cross_lingual_similarity.py` |
| 3 | Cited-excerpt side-by-side | **DONE** | `/compare` + `PrecursorComparisonView` + schemas |
| 4 | Honest precursor taxonomy | **DONE** | `precursor_taxonomy.json` + Kind-3 UI disclaimer |
| 5 | Feedback loop | **DONE** | `original_prediction`, `scripts/retrain_from_feedback.py`, VIEWER gate; retrain artifact test |
| 6 | Synthetic diversity + DGMS honesty | **DONE** | Paraphrase generator + DGMS LIMITATION labels |
| 7 | Eval leakage + metrics UI | **DONE** | Group-by-base split, `test_no_data_leakage.py`, confusion matrix UI |

---

## Phased plan

### Phase 1 — Language/script guard (DONE)

### Phase 2 — Multilingual retrieval (DONE)

**Files:** `embeddings.py`, `config.py` (`EMBEDDING_MODEL` wiring), `faiss_index.py` (incremental `add`), `similarity_service.py` / `analysis_service.py`, `requirements.txt`, `seed_data.py`, `tests/test_cross_lingual_similarity.py`, README Retrieval section.

**Acceptance:** Cross-lingual cosine test (EN ↔ Devanagari LOTO scenario) beats unrelated baseline; dim mismatch rejected.

**Note:** Does **not** reopen Devanagari for rule NLP; retrieval-only.

### Phase 3 — Cited-excerpt comparison UX (DONE)

### Phase 4 — Honest precursor taxonomy (DONE)

### Phase 5 — Feedback loop completion (DONE)

### Phase 6 — Synthetic diversity + DGMS honesty (DONE)

### Phase 7 — Eval leakage + honest metrics UI (DONE)

---

## Intentionally deferred (not backlog blockers)

- Assamese NER / full Indic **rule** NLP
- Verbatim DGMS annual-report PDF extracts
- Native `pgvector` ANN (Compose Postgres path exists; runtime uses FAISS)
- Real OIL production data / multi-annotator gold
- Production hardening (JWT secret, SQLite default)
