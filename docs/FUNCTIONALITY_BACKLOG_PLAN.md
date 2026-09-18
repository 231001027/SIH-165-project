# SIFGuard-OIL Functionality Backlog Plan

Audit date: 2026-09-18. Prior Option-3 work (Ollama, FAISS-over-TF-IDF, LangGraph, Hindi lexicon fail-safe, review 9 fields + retrain endpoint, standards_tags, DGMS portal stubs, train-only TF-IDF fit) is treated as **partial** wherever it does not meet the newer prompt acceptance criteria.

## Conflict reconciliation (canonical)

| Concern | Rule NLP pipeline | Retrieval / RAG |
|--------|-------------------|-----------------|
| Language | **English-only honesty** via `is_pipeline_supported_language` → `UNSUPPORTED_LANGUAGE` (no silent empty analysis) | Later: multilingual sentence-transformers + FAISS for cross-lingual similarity |
| Hindi / Devanagari | **Fail closed** for rule extraction (not lexicon-gloss “supported”) | May still retrieve if multilingual embeddings land (Phase 2) |
| ISO / PSM | Kind-3 team tags only; never claim Kind-1 derivation without citations | N/A |

Document this split in README / About whenever either side changes.

---

## Gap matrix

| # | Prompt area | Status | Evidence / gap |
|---|-------------|--------|----------------|
| 1 | Language/script guard (`is_pipeline_supported_language`, `UNSUPPORTED_LANGUAGE`, UI banners, About) | **PARTIAL → Phase 1** | `detect_language_support` + Hindi lexicon can mark Devanagari **supported** (`preprocess.py`); abstention uses generic `LANGUAGE_UNSUPPORTED` + `REVIEW` (`analysis_service._persist_language_abstention`). No `is_pipeline_supported_language`, no distinct UI banner, About omits English-only limit. |
| 2 | Multilingual sentence-transformers + FAISS incremental + cross-lingual test | **PARTIAL** | Still TF-IDF+SVD (`embeddings.py`); `EMBEDDING_MODEL` unread. FAISS exists (`faiss_index.py`) but full rebuild each analyze, no incremental insert, no dim validation, no cross-lingual ST test. |
| 3 | Cited-excerpt side-by-side (`PrecursorComparisonView`, shared fields, narrative highlights) | **PARTIAL** | Service returns `excerpt` (`similarity_service.py`) but `SimilarReportOut` has no narrative/excerpt/comparison schema (`schemas/report.py`). No comparison endpoint, no `PrecursorComparisonView`, Report Detail does not highlight `lsr_evidence` / entity spans. |
| 4 | Honest precursor taxonomy (Kind-1 vs Kind-3, version, fix ISO/PSM claims) | **PARTIAL** | `lsr_knowledge_base.json` has Kind-1/3 honesty; `standards_tags.py` adds ISO/PSM-inspired overlays without a unified `precursor_taxonomy.json` + version. README/About still soft-claim secondary ISO/PSM. |
| 5 | Feedback loop (`original_prediction`, retrain script, VIEWER gate, 9 fields) | **PARTIAL** | 9 fields UI + `/api/review/retrain` exist. Missing: `original_prediction` snapshot column; CLI `scripts/retrain_from_feedback.py` + artifact-version test; `/review` not role-gated in `App.jsx` (VIEWER can open page). |
| 6 | Synthetic duplication + genuine DGMS | **PARTIAL** | Generator still appends `(follow-up observation #N)` (`generate_synthetic_data.py`). DGMS entries exist but are **team-authored** portal-grounded stubs (`incidents.json` → `dgms.gov.in` homepage), not genuine annual-report narratives — need honest limitation or real cites. |
| 7 | Eval leakage (group-by-base-narrative), README metrics, confusion matrix UI, leakage test | **PARTIAL** | Train-only TF-IDF fit reduces embedding leakage; **split still row-shuffles duplicates across splits**. README HIGH recall ~0.48 / FN ~0.18 likely stale. Confusion matrix in API but **not rendered** on `EvaluationPage.jsx`. No `test_no_data_leakage.py`. |

---

## Phased plan

### Phase 1 — Language/script guard (DONE 2026-09-18)

**Goal:** Honest English-only rule-pipeline gate; Devanagari never looks like a successful SIF analysis.

**Files touched:**
- `backend/app/core/config.py` — `PIPELINE_LATIN_TOKEN_RATIO_MIN` (default `0.70`)
- `backend/app/nlp/preprocess.py` — `is_pipeline_supported_language()`, `latin_token_ratio()`; Devanagari no longer pipeline-supported
- `backend/app/models/analysis.py` — `SifClassification.UNSUPPORTED_LANGUAGE`
- `backend/app/services/analysis_service.py` — gate before extract/barrier/LSR; persist unsupported status
- `backend/app/services/pipeline_graph.py` — aligned preprocess gate
- `frontend/src/pages/ReportDetailPage.jsx`, `NewReportPage.jsx`, `ReviewQueuePage.jsx`, `AboutPage.jsx`, `components/Badges.jsx`
- `backend/tests/test_language_guard.py` (new) + `test_multilingual.py` / `test_sif_classifier.py` updates

**Acceptance checks:**
- [x] Pure English → analysis runs as today
- [x] Pure Devanagari → `UNSUPPORTED_LANGUAGE`, no fabricated entities/LSR/SIF band
- [x] Romanized Hindi → still **passes** ASCII gate (documented limitation)
- [x] Code-mixed at threshold boundary covered by unit tests
- [x] UI banner on detail (and New Report notice) is visually distinct
- [x] About lists English-only rule-pipeline limitation
- [x] Full pytest suite green (54 passed)

---

### Phase 2 — Multilingual retrieval (embeddings + FAISS incremental)

**Files:** `embeddings.py`, `config.py` (`EMBEDDING_MODEL` wiring), `faiss_index.py` (incremental `add`), `similarity_service.py`, `requirements.txt`, `seed_data.py` re-embed, `tests/test_cross_lingual_similarity.py`, README Retrieval section.

**Acceptance:** Cross-lingual cosine test (EN ↔ Devanagari LOTO scenario) beats unrelated baseline; dim mismatch rejected.

**Note:** Does **not** reopen Devanagari for rule NLP; retrieval-only until a dedicated multilingual rule phase.

---

### Phase 3 — Cited-excerpt comparison UX

**Files:** `schemas/report.py`, similarity/comparison route, new comparison service, `PrecursorComparisonView.jsx`, `ReportDetailPage.jsx` (highlights for `lsr_evidence` + entity spans), tests for shared-field evidence spans.

**Acceptance:** Select similar incident → side-by-side narratives + shared/non-shared table with locatable excerpts; works offline without LLM.

---

### Phase 4 — Honest precursor taxonomy

**Files:** new `app/data/precursor_taxonomy.json` (version + Kind-1/3), slim/reframe `standards_tags.py`, README + About claim sweep.

**Acceptance:** Grep-backed standards claims; taxonomy version field present.

---

### Phase 5 — Feedback loop completion

**Files:** `AnalysisResult.original_prediction` (JSON), MODIFY path snapshot, `scripts/retrain_from_feedback.py`, retrain test, `App.jsx` `/review` roles `ADMIN|HSE_ANALYST`, optional nav hide for VIEWER.

**Acceptance:** MODIFY + script updates classifier artifact metadata; VIEWER cannot use review actions UI.

---

### Phase 6 — Synthetic diversity + DGMS honesty

**Files:** `generate_synthetic_data.py` (paraphrase or 1× scenarios), regenerate CSV, `incidents.json` (real DGMS text **or** documented limitation; remove fabricated attribution), README.

**Acceptance:** Retrieval not dominated by near-duplicate clones; DGMS claim is citable or explicitly limited.

---

### Phase 7 — Eval leakage + honest metrics UI

**Files:** group-by-base-narrative split in generator, `tests/test_no_data_leakage.py`, re-seed + capture metrics → README, `EvaluationPage.jsx` confusion matrix.

**Acceptance:** 0% base-narrative train/test overlap; README numbers match live evaluation; matrix visible.

---

## Suggested priority order

1 → 3 → 7 → 5 → 6 → 4 → 2  

Rationale: Phase 1 removes the highest-risk silent false-negative. Phase 3 delivers the “citation you can check” UVP. Phase 7 restores metric honesty. Phase 5 closes learning loop. Phase 6 cleans demo data. Phase 4 documentation integrity. Phase 2 is heaviest (model download / dims / re-seed).

---

## Phase 1 implementation notes (reconciliation)

- Prefer new prompt: Devanagari **fails** English pipeline guard with `UNSUPPORTED_LANGUAGE`.
- Retain Hindi lexicon helpers for optional future / Romanized gloss experiments, but **do not** mark Devanagari as supported for `analyze_report`.
- Multilingual retrieval remains Phase 2 and must not imply rule-pipeline multilingualism in UI copy.

## Implemented this session (fast pass)

Shipped into the tree: language guard + UI banner; `/compare` + `PrecursorComparisonView`; `precursor_taxonomy.json`; `original_prediction` + `scripts/retrain_from_feedback.py` + VIEWER review gate; synthetic paraphrase + group-by-base split + `test_no_data_leakage.py`; honest DGMS limitation labels; evaluation confusion matrix UI. **Still open:** multilingual sentence-transformers provider + FAISS incremental dim validation + cross-lingual ST test (Phase 2).
