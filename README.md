# SIFGuard-OIL — OIL SIF Precursor Intelligence

**SIH26165** · Oil India Limited (OIL) · Software / Smart Automation

An explainable SIF-precursor intelligence platform that converts free-text Unsafe-Act / Unsafe-Condition,
near-miss and incident reports into structured, evidence-linked fatality-prevention intelligence: SIF
potential, the relevant IOGP Life-Saving Rule, hazard/energy/exposure, barrier status, a transparent risk
score, similar historical precursors, recurring patterns, and site/activity risk ranking — all reviewable
by an HSE analyst, never fully autonomous.

> **Source discipline.** This project distinguishes official/sourced facts (e.g. the 9 IOGP Life-Saving
> Rules) from our own prototype design decisions (e.g. risk-score weights, confidence thresholds) and from
> synthetic demo data. Anything in this codebase that is a design decision rather than a verified fact is
> commented as such, and the UI labels synthetic data everywhere it appears. **Nothing in this repository
> should be presented as OIL's real data or as an official IOGP scoring formula.**

---

## 1. Problem Statement

OIL's HSSE platform collects large volumes of UA/UC, near-miss and incident reports, triaged manually on a
periodic (monthly/quarterly) cycle. The ask is not a chatbot — it is: automatically separate the small
minority of reports carrying genuine fatal potential from the much larger volume of low-consequence noise,
map each to the correct IOGP Life-Saving Rule, identify failed/missing safety barriers, and surface
recurring precursor patterns on a dashboard so HSE can target interventions.

A SIF precursor is *"a high-risk situation in which management controls are either absent, ineffective, or
not complied with, and which will result in a severe or fatal injury if allowed to continue"* (Martin &
Black, 2015 / DEKRA). **"No injury occurred" does not mean "low risk"** — the system classifies on
*potential* severity, not actual outcome.

---

## 2. Architecture

```
Safety Report (free text)
   -> Report Ingestion (single form / CSV batch)
   -> Text Preprocessing (sentence split, tokenize, clean)
   -> Safety Terminology Normalization (LOTO/PTW/SIMOPS lexicon)
   -> Entity / Risk Extraction (hazard, energy, exposure, activity, location)
   -> Barrier Failure Detection (negation-aware: "LOTO applied" vs "LOTO not applied")
   -> IOGP Life-Saving Rule Classification (9-rule knowledge base + evidence gating)
   -> SIF Classification (deterministic rule engine + local ML classifier, fused)
   -> Transparent Risk Scoring (0-100, weighted, prototype formula)
   -> Explainable "Why flagged?" (template, optionally LLM-polished)
   -> SIF Precursor Fingerprint (structured record)
   -> Similarity Search + Clustering (local embeddings)
   -> Trend / Pattern Engine + Site/Activity Ranking
   -> HSE Dashboard
   -> Human Review (Approve / Modify / Reject / Escalate)
   -> Feedback + Audit Trail
```

Every stage in the blueprint's 18-stage pipeline is represented here, implemented as focused Python
modules under `backend/app/{nlp,rules,ml,services}/` rather than 18 separate microservices — a single
FastAPI backend + one database is faster to build, easier to run, and easier to defend under questioning
than premature microservices for a project this size.

### Why a hybrid architecture, not a single LLM call

A pure "ask an LLM if this is SIF" design is explicitly rejected. The architecture is a genuine hybrid:

| Layer | Responsibility | Why |
|---|---|---|
| **Rule engine** (`app/nlp`, `app/rules`) | Negation-aware barrier status, hazard/energy/exposure extraction, LSR knowledge-base scoring, deterministic risk components | Auditable, inspectable code — not prompt-dependent behaviour. Runs with **zero external dependency**, so the core SIF/LSR/barrier path keeps working even if the LLM API is down. |
| **ML classifier** (`app/ml`) | SIF label probability, trained on the gold set; also powers similarity search & clustering | Generalizes across phrasing the rule engine hasn't seen |
| **Bounded LLM** (`app/services/llm_client.py`) | *Optional* explanation smoothing only | Never the sole SIF authority, never asked to "decide" anything — only to rephrase an already-computed, evidence-based explanation |
| **Human** | Final sign-off on REVIEW/low-confidence items | Never bypassed for a consequential safety decision |

The rule engine and ML layer are fused with a confidence-banded **abstention policy** (see §5): when
evidence is weak or the two layers conflict sharply, the system returns `REVIEW` — *"insufficient evidence,
human HSE review required"* — instead of forcing a confident answer.

---

## 3. AI/NLP Pipeline — what is actually running, and why

A few pragmatic engineering decisions were made deliberately, and are disclosed here rather than glossed
over:

- **Embeddings are TF-IDF + Truncated-SVD (local, `scikit-learn`), not Sentence-Transformers.**
  A transformer embedding model is a multi-hundred-MB download with a PyTorch dependency — a poor fit for
  a hackathon environment that must install and run reliably in minutes, fully offline. TF-IDF+SVD plays
  the same architectural role (a dense vector per report, used for similarity search, clustering, and as
  classifier input) and is fit locally on the report corpus in seconds. The `EmbeddingProvider` interface
  (`app/ml/embeddings.py`) is the only thing the rest of the app talks to, so a real transformer backend
  could be swapped in later without touching similarity/clustering/classification call sites.
- **No spaCy dependency.** Tokenization, sentence-splitting and clause-splitting are pure-Python/regex
  (`app/nlp/preprocess.py`). This avoids a model-download dependency and keeps the negation engine fully
  deterministic and unit-testable.
- **Negation-aware barrier detection is pattern/clause-based, not a full dependency parse**
  (`app/nlp/negation.py`). Sentences are split into clauses on contrastive conjunctions ("but", "however",
  ...) so an affirmative clause about one barrier cannot be contaminated by a negative clause about
  something else in the same sentence — this is what correctly separates *"the isolation checklist was not
  fully complete, **but** LOTO was correctly applied"* into two independently-scored clauses. When no
  polarity cue is found near a barrier mention, status defaults to `NOT_VERIFIED` rather than guessing.
- **Clustering uses KMeans, not HDBSCAN** — HDBSCAN's compiled C-extension is a real install-risk on a bare
  Windows machine; KMeans is the blueprint's own documented fallback. Cluster labels are generated
  automatically from each cluster's top distinctive TF-IDF terms, never hardcoded.
- **The SIF classifier is deliberately, heavily regularized** (`LogisticRegression(C=0.35)`,
  20-dimensional embeddings). With only ~150 hackathon-scale labelled rows, an unregularized model on a
  larger embedding overfits almost perfectly (we measured ~98% train accuracy) and then disagrees
  erratically with the rule engine on unseen reports. This is disclosed, not hidden — see §8 Evaluation and
  §11 Limitations.

---

## 4. Key Features

| Feature | Where |
|---|---|
| Single-report + CSV batch ingestion, with per-row validation results | `/reports/new`, `/upload` |
| SIF classification: `HIGH / MEDIUM / LOW / NON_SIF / REVIEW` + confidence + reason codes | `app/services/analysis_service.py` |
| IOGP Life-Saving Rule mapping (9 rules + "No applicable rule"), with evidence | `app/rules/lsr_engine.py` |
| Hazard / energy-source / exposure extraction | `app/nlp/entity_extraction.py` |
| Negation-aware barrier status: `PRESENT_EFFECTIVE / MISSING / FAILED / BYPASSED / NOT_VERIFIED / UNKNOWN` | `app/nlp/negation.py` |
| Transparent, configurable 0-100 risk score with component breakdown | `app/services/analysis_service.py`, `app/core/risk_weights.json` |
| Evidence-based "Why flagged?" explanation, optional bounded LLM polish | `app/services/explanation_service.py`, `llm_client.py` |
| SIF Precursor Fingerprint (the reusable structured unit) | `app/services/fingerprint_service.py` |
| Similar-report semantic search, grounded against a real, cited incident corpus | `app/services/similarity_service.py`, `data/reference_corpus/` |
| Precursor clustering with auto-generated labels | `app/ml/clustering.py`, `app/services/clustering_service.py` |
| Trend engine + "what changed" period-over-period statements | `app/services/trend_service.py` |
| Site / activity SIF-precursor density ranking + heatmap (with denominator caveat shown) | `app/services/ranking_service.py`, `/dashboard/heatmap` |
| Cross-site IOGP Life-Saving Rule comparison | `trend_service.lsr_distribution_by_site`, `/dashboard/lsr-by-site` |
| HSE Dashboard: KPIs, charts, filters (site/activity/LSR/barrier/date range), drill-down | `frontend/src/pages/DashboardPage.jsx` |
| Human review workflow: Approve / Modify / Reject / Escalate, feedback stored per field | `/review`, `app/api/routes/review.py` |
| Append-only audit trail (admin) | `/audit` |
| Evaluation harness against a held-out gold set, honest "insufficient data" states | `/evaluation`, `app/services/evaluation_service.py` |
| Role-based access: `ADMIN / HSE_ANALYST / VIEWER` | `app/api/deps.py` |

---

## 5. How the SIF Decision Works

The system **never** collapses to a binary SIF=YES/NO. Output is always one of five bands, each with a
0–100% confidence and a list of machine-readable reason codes
(`HIGH_ENERGY_SOURCE`, `WORKER_EXPOSURE`, `CRITICAL_BARRIER_FAILURE`, `REPEAT_PRECURSOR`, ...):

| Band | Meaning |
|---|---|
| `HIGH` | Strong evidence of serious/fatal potential |
| `MEDIUM` | Meaningful risk indicators, evidence incomplete |
| `LOW` | Some risk signal, weak evidence |
| `NON_SIF` | No meaningful high-energy hazard/exposure evidence found |
| `REVIEW` | The system abstains — evidence is weak or the rule engine and ML classifier conflict sharply |

**Fusion & abstention** (`app/services/analysis_service.py::_fuse_and_decide`): the deterministic rule
engine is the primary, always-available confidence driver (per the blueprint's "rule engine = safety
baseline" principle); the ML classifier acts as a *modifier* — a confirming bonus when it agrees, a
discount when it disagrees, and only forces `REVIEW` on a *sharp* disagreement (≥2 severity bands apart)
combined with the rule engine itself not being highly confident. This is a deliberate design choice: with
so few training rows, the ML layer's probabilities are naturally flatter (see §3), and a naive 50/50
average with the rule engine would trigger REVIEW far too often — an earlier iteration of this exact
codebase did that (37% of all reports routed to REVIEW) before the fusion logic was corrected; the current
version sits around 15–20% for the synthetic demo set, which is a genuinely useful review-queue size rather
than the queue swallowing the whole dataset.

---

## 6. SIF Precursor Fingerprint

Every analyzed report produces one structured fingerprint record — the reusable "unit of intelligence"
that similarity search, clustering, trends, and ranking all operate on:

```json
{
  "report_id": 42, "sif_potential": "HIGH", "confidence": 91.6,
  "life_saving_rule": "Energy Isolation",
  "hazard": "Stored / pressurized energy", "energy_source": "Pressurized fluid",
  "worker_exposure": "...", "exposure_proximity": "HIGH",
  "activity": "Pipeline Maintenance", "location": "flange near separator unit 3", "site": "Site B",
  "barriers": [{"name": "Isolation / LOTO", "status": "NOT_VERIFIED", "evidence": "..."}],
  "potential_consequence": "Serious injury / fatality",
  "reason_codes": ["HIGH_ENERGY_SOURCE", "WORKER_EXPOSURE", "CRITICAL_BARRIER_FAILURE", "UNCONTROLLED_RELEASE"],
  "risk_score": 60.5
}
```

## 7. Barrier Failure Engine — negation-aware

`"LOTO was correctly applied"` → `PRESENT_EFFECTIVE`. `"LOTO was not applied"` → `MISSING`.
`"opened a flange **before confirming** isolation"` → `NOT_VERIFIED`. `"the isolation checklist was not
fully complete, **but** LOTO was correctly applied"` → clause-split correctly to `PRESENT_EFFECTIVE`. When
no polarity cue is found, the engine returns `NOT_VERIFIED` / `UNKNOWN` rather than guessing — see
`backend/tests/test_negation.py` for the full test suite proving this behaviour, including the exact
false-positive/false-negative edge cases from the project brief.

---

## 8. Evaluation

The `/evaluation` page and `app/services/evaluation_service.py` compute Precision/Recall/F1/false-negative
rate for SIF classification, top-1/per-rule accuracy for LSR mapping, and review-queue correction rate —
**always against the held-out gold-set `evaluation_cases` table** (never touched by training), and always
labelled `"Computed on the synthetic/demo gold-set evaluation split — NOT real OIL production data."` Where
support is too small for a metric to mean anything (e.g. `MEDIUM` class with only 3 test-set examples), the
API returns the raw numbers rather than hiding them, and the UI shows them plainly — no number is
fabricated or hidden, per the project's evaluation principle: **recall and false-negative rate on
HIGH/MEDIUM are treated as the primary safety metric, not overall accuracy**, because a missed SIF
precursor is a worse failure mode than a false alarm.

Snapshot from the seeded demo dataset (315 synthetic reports, 63 held-out test cases) — regenerate with
`python seed_data.py --reset` to reproduce (deterministic, fixed random seed):

- HIGH-class recall ≈ 0.48 (precision ≈ 0.80), false-negative rate on HIGH/MEDIUM ≈ 0.18
- LSR top-1 accuracy ≈ 0.84
- Full per-class breakdown, confusion matrix and LSR per-rule accuracy: `GET /api/evaluation` or the
  Evaluation page in the UI.

**Reading the HIGH-class recall honestly.** Raw recall looks lower than an earlier, smaller (155-row)
version of this dataset reported — that is the expected and correct effect of deliberately tripling the
MEDIUM/borderline-case content in the gold set (see §9) rather than a regression. Inspecting the actual
misses shows why: of the gold HIGH cases the system does not classify HIGH, the large majority land in
`REVIEW` or `MEDIUM` — i.e. the abstention/trust-layer policy correctly recognising a genuinely harder,
more ambiguous narrative and declining to force a confident HIGH rather than silently dropping it. The
false-negative rate on HIGH/MEDIUM (a *silent* drop to LOW/NON_SIF) is the metric this project treats as
the real safety signal, and it improved as the rule engine's keyword/lexicon coverage was broadened against
this harder set — see the per-report breakdown via `GET /api/evaluation` to inspect this directly rather
than taking the summary number alone.

These are prototype-methodology numbers on a small, team-authored synthetic set — not a claim about
production accuracy on real OIL data.

---

## 9. Dataset

**No real OIL data is used or claimed.** `data/synthetic/generate_synthetic_data.py` deterministically
(fixed seed) generates 315 team-authored, IOGP/DEKRA-grounded narratives covering all 9 Life-Saving Rules,
good-practice (NON_SIF) examples, low-severity housekeeping items, and the project's required edge cases —
expanded from an original 155-row set specifically to give the MEDIUM class (previously only ~3 held-out
test examples) meaningfully more support, per the blueprint's own 300-500 row target (Part 5.3):

- **False positives**: *"the word 'fall' ... describing a decline in safety scores"* → correctly `NON_SIF`
  (guards against naive keyword matching); *"Confined-space entry ... valid permit, verified gas test, full
  PPE"* → correctly not flagged as a barrier failure.
- **False-negative challenges**: *"Minor slip on a wet floor near a stairwell railing"* — deliberately
  terse phrasing that should not be waved through as confidently NON_SIF.
- **Ambiguous / REVIEW cases**: *"Unusual noise heard near rotating equipment; area was cleared"*, *"Near
  miss reported but activity and location are unclear"*.

Every synthetic report is tagged `source=SYNTHETIC_SEED` in the database and shown with a **"Synthetic demo
data"** badge in the UI wherever it appears (report detail page). Reports created through the app itself
(manual form or CSV upload) are tagged `MANUAL` / `CSV_UPLOAD` and carry no such badge — the ingestion
pipeline is schema-ready to accept OIL's real report data on day one if it is ever provided, with no code
changes required.

### 9.1 Real-incident reference corpus (similarity grounding)

`data/reference_corpus/incidents.json` holds 12 **real, independently verifiable** severe-injury/fatality
incident summaries, each carrying an actual OSHA citation (a FatalFacts bulletin number or a regional news
release) with the exact URL the content was retrieved from — none of these are synthetic, and none are
invented. They cover 9 of the 9 IOGP Life-Saving Rule categories. `seed_data.py::load_reference_corpus`
loads them as `Report` rows tagged `source=PUBLIC_CORPUS`, runs them through the same
extraction/LSR/barrier pipeline as every other report (so they get a real fingerprint and embedding), and
`app/services/similarity_service.py` lets them surface as "similar precursor" matches for a submitted
report — each shown with its citation, not as an internal report link. This directly answers the "your
similarity search only ever compares against your own synthetic data" critique: it can now surface a match
against a real, named, historical incident.

**PUBLIC_CORPUS rows are strictly grounding-only** — they are excluded from every KPI, trend, site/activity
ranking, precursor cluster and the evaluation gold set (see the `Report.source != ReportSource.PUBLIC_CORPUS`
filters in `app/services/trend_service.py`, `ranking_service.py`, `clustering_service.py` and
`app/api/routes/dashboard.py`/`reports.py`), and they are never listed on the main Reports page. They exist
for exactly one purpose: giving a submitted report something real and checkable to be compared against.

---

## 10. Security

- JWT auth (`python-jose`), bcrypt password hashing (`passlib`), role-based access control:
  `ADMIN` (full access, audit trail, user/model administration) / `HSE_ANALYST` (create, review, analyze) /
  `VIEWER` (read-only dashboard).
- Every report-mutating and review action is written to an append-only `audit_logs` table
  (`app/services/audit_service.py`) — **full narrative text is never written to the audit log**, only
  structured metadata.
- CORS is restricted to the configured frontend origin.
- CSV upload only accepts `.csv`, validates every row, and never executes uploaded content.
- The bounded LLM prompt only ever includes already-extracted structured fields — report free text is
  never forwarded as an instruction the model could be manipulated by (prompt-injection mitigation).
- **LLM output is validated, not trusted on its word** (`app/services/llm_client.py::_validate_llm_output`):
  every LLM-polished explanation is checked against the full known vocabulary of hazard labels, barrier
  types and LSR names (the same lists the deterministic pipeline itself uses) — if the model's rephrased
  text names a hazard/barrier/LSR that was not already part of THIS report's own extracted evidence, the
  output is rejected and the system falls back to the template explanation instead of showing an
  unsupported safety claim. See `backend/tests/test_llm_guardrail.py`.
- `.env` files are git-ignored; only `.env.example` (no secrets) is committed.

---

## 11. Known Limitations (stated honestly, not glossed over)

- **Rule-based NLP, not trained NER**: entity/hazard/energy/exposure extraction and the LSR/barrier engines
  are deterministic keyword+pattern systems, not trained span models — there is no labelled OIL entity-span
  corpus to train one on. This is fully disclosed in-code and in the About page.
- **Gold set (315 rows)**: within the blueprint's 300–500 row target, up from an original 155; category
  balance was actively tuned so `MEDIUM` now has ~13 held-out test examples (was 3), though per-class metrics
  on the smallest classes (`LOW`, `MEDIUM`) still carry real sampling noise and should be read as directional,
  not precise.
- **LLM layer** is optional (Ollama via Docker Compose by default in compose; Anthropic also supported).
  It only polishes an already-computed explanation using structured fields + retrieved excerpts; it is never
  a classification authority. If Ollama is down, the API falls back to the template explanation.
- **Multilingual**: Devanagari tokenization + a small Hindi/Romanized safety lexicon are supported; dense
  unsupported script still abstains to `REVIEW` (never a silent empty analysis). Full Assamese NER and
  production multilingual models remain future work.
- **Retrieval**: FAISS over local TF-IDF+SVD embeddings with cited excerpts on similar matches. Native
  `pgvector` ANN and Sentence-Transformers remain optional upgrades.
- **Evaluation metrics** on the synthetic gold set are directional. Embeddings are fit on the **train
  split only** during seed to reduce test leakage into the vector space. Per-class scores on small
  classes (`LOW` / `MEDIUM`) still carry sampling noise — do not treat them as production OIL KPIs.
- **No exposure-hours data**: site/activity ranking is report-volume-normalized, not a true
  exposure-normalized risk rate — the UI states this caveat next to every ranking.
- **Gold set (~315 synthetic rows)** plus a small public reference corpus (OSHA + DGMS-style portal
  grounding incidents). Not real OIL production data.

## 12. Future Enhancements

Swap in a real Sentence-Transformer embedding backend behind the existing `EmbeddingProvider` interface;
wire native `pgvector` ANN search on Postgres; grow the gold set with multi-annotator agreement; expand
the public reference corpus further; deepen Hindi/Assamese coverage; private/on-prem LLM hosting for an
OIL pilot. ISO 45001 / PSM tags are secondary overlays today — a full standards ontology rewrite is not
in scope for this prototype.

---

## 13. Project Structure

```
sifguard-oil/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # auth, reports, dashboard, review, evaluation, clusters, audit, catalog
│   │   ├── core/             # config, security, risk_weights.json
│   │   ├── db/                # SQLAlchemy session/base
│   │   ├── models/            # ORM models
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── nlp/               # preprocessing, lexicon, negation engine, entity extraction
│   │   ├── rules/              # LSR engine, SIF rule engine, barrier scoring
│   │   ├── ml/                 # embeddings, classifier, clustering
│   │   ├── services/           # analysis orchestration, explanation, fingerprint, similarity,
│   │   │                       # trend, ranking, clustering, evaluation, audit, LLM client
│   │   ├── data/lsr_knowledge_base.json
│   │   └── main.py
│   ├── tests/                  # pytest: negation, LSR mapping, barrier engine, SIF classifier, API
│   ├── seed_data.py            # users + synthetic dataset + training + clustering, one command
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # React + Vite + Tailwind + Recharts
│   └── src/{pages,components,context,layouts,services}
├── data/synthetic/generate_synthetic_data.py
├── docker-compose.yml          # optional Postgres/pgvector pilot path
└── README.md
```

---

## 14. Installation & Running (Windows PowerShell)

### A. First-time setup

```powershell
# Backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env

# Frontend (separate terminal)
cd frontend
npm install
copy .env.example .env
```

### B. Seed demo data (users, ~155 synthetic reports, train the classifier, compute clusters)

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python seed_data.py --reset
```

This single command creates the SQLite database, 3 demo users, seeds and analyzes the synthetic dataset
(rule engine first, then trains and re-applies the ML classifier), computes precursor clusters, and loads
the held-out evaluation gold set. It is idempotent without `--reset` (safe to re-run; `--reset` drops and
rebuilds all tables first).

### C. Start backend

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Backend: **http://localhost:8000** · API docs (OpenAPI/Swagger): **http://localhost:8000/docs**

### D. Start frontend

```powershell
cd frontend
npm run dev
```

Frontend: **http://localhost:5173**

### E. Run tests

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```

### F. Docker method (optional — Postgres/pgvector pilot path)

```powershell
docker compose up --build
# then, in another terminal, seed the Postgres-backed database:
docker compose exec backend python seed_data.py --reset
```

### G. Stop

```powershell
# Ctrl+C in each terminal (backend/frontend). Docker:
docker compose down
```

---

## Installation & Running (macOS / Linux, bash)

```bash
# Backend (use Python 3.11 or 3.12 — not 3.14)
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed_data.py --reset
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env
npm run dev

# Optional: full stack + local Ollama via Docker
docker compose up --build
# (ollama-init pulls llama3.2; backend LLM_PROVIDER=ollama)

# Tests
cd backend && source venv/bin/activate && python -m pytest tests/ -v
```

---

## 15. Demo Login

| Role | Email | Password |
|---|---|---|
| Admin | `admin@sifguard-oil.com` | `Admin@12345` |
| HSE Analyst | `analyst@sifguard-oil.com` | `Analyst@12345` |
| Viewer | `viewer@sifguard-oil.com` | `Viewer@12345` |

## 16. Demo Flow

1. Log in as **HSE Analyst**.
2. **New Report** → click "Use flagship demo scenario" → Submit and Analyze. Watch the full chain appear:
   SIF `HIGH` @ ~92% confidence → `Energy Isolation` LSR → hazard/energy/exposure → `Isolation / LOTO:
   NOT_VERIFIED` → evidence-based explanation → similar precursor reports.
3. **Dashboard** → KPIs, SIF trend, LSR distribution, barrier-failure chart, site ranking — all real data
   from the seeded set, clearly badged as synthetic.
4. **Review Queue** → submit an ambiguous report (e.g. *"Unusual noise heard near rotating equipment; area
   was cleared as a precaution."*) and show it land in `REVIEW` with an explicit abstain reason — this is
   the human-in-the-loop trust layer working as designed, not a gap.
5. **Clusters** → recurring precursor patterns, auto-labelled.
6. **Evaluation** → gold-set metrics, explicitly labelled as synthetic-data methodology, not production
   accuracy.

---

*Built for Smart India Hackathon 2026, problem statement SIH26165 (Oil India Limited). This is a hackathon
prototype demonstrating an explainable SIF-precursor intelligence architecture — see §11 for what is and
is not yet production-ready.*
