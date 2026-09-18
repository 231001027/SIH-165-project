"""
Seeds the database with demo users and the synthetic dataset, then trains the
local embedding + classifier artifacts and computes clusters -- everything
needed for a fully working demo in one command.

Usage (from backend/, with the venv activated):
    python seed_data.py            # seed only if DB is currently empty
    python seed_data.py --reset    # drop and recreate all tables first
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.base import init_db
from app.db.session import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.catalog import Site, Activity
from app.models.report import Report, ReportType, ReportSource
from app.models.audit import EvaluationCase, ModelVersion
from app.ml.embeddings import get_embedding_provider
from app.ml.classifier import reload_classifier, build_feature_vector, SifClassifier
from app.services.analysis_service import analyze_report, MODEL_VERSION, _RISK_CONFIG
from app.services.clustering_service import recompute_clusters

DATA_CSV = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "reports.csv"
REFERENCE_CORPUS_JSON = Path(__file__).resolve().parent.parent / "data" / "reference_corpus" / "incidents.json"

DEMO_USERS = [
    {"email": "admin@sifguard-oil.com", "full_name": "OIL HSE Admin", "role": UserRole.ADMIN, "password": "Admin@12345"},
    {"email": "analyst@sifguard-oil.com", "full_name": "HSE Analyst (Demo)", "role": UserRole.HSE_ANALYST, "password": "Analyst@12345"},
    {"email": "viewer@sifguard-oil.com", "full_name": "Site Viewer (Demo)", "role": UserRole.VIEWER, "password": "Viewer@12345"},
]


def reset_db():
    print("Dropping and recreating all tables...")
    import app.models  # noqa: F401  ensure metadata populated
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_users(db):
    created = 0
    for u in DEMO_USERS:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if existing:
            continue
        db.add(User(
            email=u["email"], full_name=u["full_name"], role=u["role"],
            hashed_password=hash_password(u["password"]),
        ))
        created += 1
    db.commit()
    print(f"Seeded {created} demo user(s) (skipped {len(DEMO_USERS) - created} already present).")


def _get_or_create_site(db, name):
    site = db.query(Site).filter(Site.name == name).first()
    if not site:
        site = Site(name=name)
        db.add(site)
        db.flush()
    return site


def _get_or_create_activity(db, name):
    activity = db.query(Activity).filter(Activity.name == name).first()
    if not activity:
        activity = Activity(name=name)
        db.add(activity)
        db.flush()
    return activity


def load_synthetic_reports(db) -> dict[int, dict]:
    """Creates Report rows from the synthetic CSV (in occurred_at order, so
    repeat-precursor counting during analysis sees earlier reports first).
    Returns {report_id: {"gold_sif":..., "gold_lsr":..., "split":...}}."""
    if not DATA_CSV.exists():
        print(f"ERROR: {DATA_CSV} not found. Run data/synthetic/generate_synthetic_data.py first.")
        sys.exit(1)

    if db.query(Report).filter(Report.source == ReportSource.SYNTHETIC_SEED).count() > 0:
        print("Synthetic reports already seeded -- skipping report creation.")
        rows = db.query(Report).filter(Report.source == ReportSource.SYNTHETIC_SEED).all()
        # No gold metadata available on re-run without re-reading the CSV; re-read and match by narrative.
        gold_by_narrative = {}
        with open(DATA_CSV, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                gold_by_narrative[row["narrative"]] = row
        meta = {}
        for r in rows:
            g = gold_by_narrative.get(r.narrative)
            if g:
                meta[r.id] = {"gold_sif": g["gold_sif"], "gold_lsr": g["gold_lsr"], "split": g["split"]}
        return meta

    with open(DATA_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: r["occurred_at"])

    meta: dict[int, dict] = {}
    for i, row in enumerate(rows):
        site = _get_or_create_site(db, row["site"])
        activity = _get_or_create_activity(db, row["activity"])
        report = Report(
            report_code=f"OIL-{10000 + i + 1}",
            report_type=ReportType(row["report_type"]),
            title=row["title"],
            narrative=row["narrative"],
            site_id=site.id,
            activity_id=activity.id,
            location=row["location"],
            reporter_name=row["reporter_name"],
            source=ReportSource.SYNTHETIC_SEED,
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
        )
        db.add(report)
        db.flush()
        meta[report.id] = {"gold_sif": row["gold_sif"], "gold_lsr": row["gold_lsr"], "split": row["split"]}
    db.commit()
    print(f"Created {len(meta)} synthetic Report rows.")
    return meta


def load_reference_corpus(db) -> list[int]:
    """Loads a small, real, publicly-cited reference corpus of historical
    severe-injury/fatality incidents (data/reference_corpus/incidents.json --
    see the file's own citation_url per entry) used ONLY to ground similar-
    precursor retrieval against genuine documented incidents, never as OIL
    data. Excluded from every KPI/trend/ranking/cluster/gold-set computation
    (see the ReportSource.PUBLIC_CORPUS filters throughout app/services/)."""
    if not REFERENCE_CORPUS_JSON.exists():
        print(f"NOTE: {REFERENCE_CORPUS_JSON} not found -- skipping reference-corpus grounding "
              f"(similarity search will still work over the synthetic/OIL corpus alone).")
        return []
    if db.query(Report).filter(Report.source == ReportSource.PUBLIC_CORPUS).count() > 0:
        print("Reference corpus already seeded -- skipping.")
        return [r.id for r in db.query(Report).filter(Report.source == ReportSource.PUBLIC_CORPUS).all()]

    with open(REFERENCE_CORPUS_JSON, "r", encoding="utf-8") as f:
        entries = json.load(f)

    ids = []
    for i, entry in enumerate(entries):
        year = entry.get("occurred_year") or 2020
        report = Report(
            report_code=f"REF-{1000 + i + 1}",
            report_type=ReportType.INCIDENT,
            title=entry["citation_label"],
            narrative=entry["narrative"],
            location=None,
            reporter_name=None,
            source=ReportSource.PUBLIC_CORPUS,
            citation_label=entry["citation_label"],
            citation_url=entry["citation_url"],
            occurred_at=datetime(year, 1, 1),
        )
        db.add(report)
        db.flush()
        ids.append(report.id)
    db.commit()
    print(f"Loaded {len(ids)} real, cited reference-corpus incidents for similarity grounding.")
    return ids


def fit_embeddings_train_only(db, meta: dict[int, dict]) -> None:
    """Prepare embedding provider. TF-IDF+SVD is fit on train-split only;
    Sentence-Transformers loads the pretrained model (no corpus fit / no leakage)."""
    from app.ml.embeddings import (
        TFIDF_SVD_LOCAL,
        TfidfSvdEmbeddingProvider,
        load_provider,
        reset_embedding_provider,
        resolve_embedding_model_name,
    )
    import app.ml.embeddings as emb_mod

    model_name = resolve_embedding_model_name()
    train_ids = [rid for rid, info in meta.items() if info.get("split") == "train"]
    narratives = [
        r.narrative for r in db.query(Report).filter(Report.id.in_(train_ids)).all() if r.narrative
    ]

    reset_embedding_provider()
    if model_name == TFIDF_SVD_LOCAL:
        if len(narratives) < 3:
            print(f"  Too few train narratives ({len(narratives)}) to fit embeddings.")
            return
        provider = TfidfSvdEmbeddingProvider()
        provider.fit(narratives)
        emb_mod._provider_singleton = provider
        print(
            f"  Fitted TF-IDF+SVD embeddings on {len(narratives)} train-split narratives "
            f"only (test held out)."
        )
        return

    provider = load_provider(model_name)
    emb_mod._provider_singleton = provider
    print(
        f"  Loaded Sentence-Transformers provider {model_name!r} "
        f"(dim={getattr(provider, 'dimension', '?')}; no train-corpus fit)."
    )


def run_rule_only_pass(db, report_ids: list[int]):
    print("Pass 1/2: rule-engine-only analysis (baseline classification; embeddings already train-fit)...")
    reports = db.query(Report).filter(Report.id.in_(report_ids)).order_by(Report.occurred_at.asc()).all()
    for report in reports:
        analyze_report(db, report)
    print(f"  Analyzed {len(reports)} reports with the deterministic rule engine.")


def train_classifier_from_db(db, meta: dict[int, dict]) -> dict:
    from app.models.analysis import AnalysisResult, PrecursorFingerprint
    import numpy as np

    weights = _RISK_CONFIG["weights"]

    X, y = [], []
    for report_id, info in meta.items():
        if info["gold_sif"] == "REVIEW":
            continue  # REVIEW is an abstention outcome, never a classifier training target
        if info["split"] != "train":
            continue
        analysis = db.query(AnalysisResult).filter(AnalysisResult.report_id == report_id).first()
        fp = db.query(PrecursorFingerprint).filter(PrecursorFingerprint.report_id == report_id).first()
        if not analysis or not fp:
            continue
        rb = analysis.risk_breakdown
        components = {
            "hazard_energy_component": rb.get("hazard_energy", 0) / weights["hazard_energy"],
            "worker_exposure_component": rb.get("worker_exposure", 0) / weights["worker_exposure"],
            "barrier_failure_component": rb.get("barrier_failure", 0) / weights["barrier_failure"],
            "activity_criticality_component": rb.get("activity_criticality", 0) / weights["activity_criticality"],
            "repeat_precursor_component": rb.get("repeat_precursor", 0) / weights["repeat_precursor"],
        }
        X.append(build_feature_vector(fp.embedding, components))
        y.append(info["gold_sif"])

    if len(X) < 10:
        print(f"  Only {len(X)} labelled training rows available -- skipping classifier training "
              f"(rule engine remains the sole SIF authority, which is a supported fallback mode).")
        return {"trained": False, "n_train": len(X)}

    classifier = SifClassifier()
    metrics = classifier.train(np.array(X), y)
    reload_classifier()
    print(f"  Trained SIF classifier on {len(X)} labelled reports. Train accuracy: {metrics['train_accuracy']:.3f}")
    return {"trained": True, "n_train": len(X), **metrics}


def run_hybrid_pass(db, report_ids: list[int]):
    print("Pass 2/2: re-running full pipeline now that the ML classifier is available (hybrid fusion)...")
    reports = db.query(Report).filter(Report.id.in_(report_ids)).order_by(Report.occurred_at.asc()).all()
    for report in reports:
        analyze_report(db, report)
    print(f"  Re-analyzed {len(reports)} reports with rule engine + ML classifier fusion.")


def load_gold_evaluation_cases(db, meta: dict[int, dict]):
    existing = db.query(EvaluationCase).count()
    if existing > 0:
        print(f"EvaluationCase table already has {existing} rows -- skipping.")
        return
    count = 0
    for report_id, info in meta.items():
        if info["split"] != "test":
            continue
        gold_lsr = info["gold_lsr"] if info["gold_lsr"] != "No applicable rule" else "No applicable rule"
        db.add(EvaluationCase(
            report_id=report_id, gold_sif=info["gold_sif"], gold_lsr=gold_lsr,
            gold_barrier_status=None, split="test",
        ))
        count += 1
    db.commit()
    print(f"Loaded {count} held-out gold-set evaluation cases (split=test).")


def record_model_version(db, classifier_metrics: dict):
    existing = db.query(ModelVersion).filter(ModelVersion.version == MODEL_VERSION).first()
    if existing:
        return
    db.add(ModelVersion(
        version=MODEL_VERSION, component="sif_classifier+rule_engine+lsr_engine+barrier_engine",
        description="Hackathon prototype: deterministic rule engine + TF-IDF/SVD embeddings + "
                     "logistic-regression classifier, fused with confidence-banded abstention.",
        metrics=classifier_metrics,
    ))
    db.commit()


def main():
    reset = "--reset" in sys.argv
    if reset:
        reset_db()
    else:
        init_db()

    db = SessionLocal()
    try:
        seed_users(db)
        meta = load_synthetic_reports(db)
        reference_ids = load_reference_corpus(db)
        # Reference-corpus reports are analyzed through both passes exactly like
        # synthetic ones (so they get real hazard/LSR/barrier tags and an
        # embedding for similarity search) but are absent from `meta`, so they
        # are automatically excluded from classifier training and the gold-set
        # evaluation -- see the PUBLIC_CORPUS filters in app/services/ for the
        # rest of the exclusion (KPIs, trends, rankings, clustering).
        report_ids = list(meta.keys()) + reference_ids

        print("Fitting embedding provider on train split only (no test leakage)...")
        fit_embeddings_train_only(db, meta)
        run_rule_only_pass(db, report_ids)
        classifier_metrics = train_classifier_from_db(db, meta)
        run_hybrid_pass(db, report_ids)
        load_gold_evaluation_cases(db, meta)
        record_model_version(db, classifier_metrics)

        print("Rebuilding FAISS similarity index...")
        try:
            from app.ml import faiss_index
            n = faiss_index.rebuild_from_db(db)
            print(f"  FAISS index built with {n} vectors.")
        except Exception as exc:
            print(f"  FAISS rebuild skipped: {exc}")

        print("Computing precursor clusters...")
        clusters = recompute_clusters(db)
        print(f"  Created {len(clusters)} clusters.")

        print("\nSeed complete.")
        print(f"Demo users: {', '.join(u['email'] + ' / ' + u['password'] for u in DEMO_USERS)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
