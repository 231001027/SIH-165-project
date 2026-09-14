"""
Evaluation harness (blueprint Part 8.1-8.3).

Computes metrics ONLY against the held-out `evaluation_cases` gold set,
which is never touched by the training/feedback loop (blueprint Part 3.3).
Every number returned here is clearly labelled as computed on the
synthetic/demo dataset -- never presented as production accuracy, per the
project's source-discipline rules. Where there is not enough labelled data
for a metric, the API returns an explicit "insufficient_data" flag rather
than a fabricated number.
"""
from __future__ import annotations

from sqlalchemy.orm import Session
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

from app.models.analysis import AnalysisResult
from app.models.audit import EvaluationCase
from app.models.review import HumanReview, Feedback

LABELS = ["NON_SIF", "LOW", "MEDIUM", "HIGH", "REVIEW"]
HIGH_RISK_LABELS = {"HIGH", "MEDIUM"}


def evaluate_sif_classification(db: Session) -> dict:
    cases = db.query(EvaluationCase).filter(EvaluationCase.split == "test").all()
    if len(cases) < 5:
        return {"insufficient_data": True, "message": "Not enough labelled gold-set test cases yet."}

    y_true, y_pred = [], []
    for case in cases:
        analysis = db.query(AnalysisResult).filter(AnalysisResult.report_id == case.report_id).first()
        if not analysis:
            continue
        y_true.append(case.gold_sif)
        y_pred.append(analysis.sif_classification.value)

    if not y_true:
        return {"insufficient_data": True, "message": "Gold-set reports have not been analyzed yet."}

    labels_present = sorted(set(y_true) | set(y_pred))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels_present, zero_division=0
    )
    per_class = {
        label: {"precision": round(float(p), 3), "recall": round(float(r), 3),
                 "f1": round(float(f), 3), "support": int(s)}
        for label, p, r, f, s in zip(labels_present, precision, recall, f1, support)
    }

    # False-negative rate on HIGH/MEDIUM ("genuine SIF precursor silently missed"):
    # a gold HIGH/MEDIUM case predicted as LOW/NON_SIF (REVIEW is *not* counted as a
    # miss -- routing an uncertain HIGH/MEDIUM case to human review is the system
    # working as intended, not a silent failure).
    fn = sum(1 for t, p in zip(y_true, y_pred) if t in HIGH_RISK_LABELS and p in ("LOW", "NON_SIF"))
    total_high_risk = sum(1 for t in y_true if t in HIGH_RISK_LABELS)
    false_negative_rate = round(fn / total_high_risk, 3) if total_high_risk else None

    cm = confusion_matrix(y_true, y_pred, labels=labels_present).tolist()

    return {
        "insufficient_data": False,
        "dataset_note": "Computed on the synthetic/demo gold-set evaluation split -- NOT production OIL data.",
        "n_cases": len(y_true),
        "per_class": per_class,
        "macro_f1": round(float(sum(f1) / len(f1)), 3) if len(f1) else None,
        "false_negative_rate_high_medium": false_negative_rate,
        "false_negative_count": fn,
        "confusion_matrix": {"labels": labels_present, "matrix": cm},
    }


def evaluate_lsr_mapping(db: Session) -> dict:
    cases = db.query(EvaluationCase).filter(
        EvaluationCase.split == "test", EvaluationCase.gold_lsr.isnot(None)
    ).all()
    if len(cases) < 5:
        return {"insufficient_data": True, "message": "Not enough labelled LSR gold-set cases yet."}

    correct_top1 = 0
    total = 0
    per_rule: dict[str, dict[str, int]] = {}
    for case in cases:
        analysis = db.query(AnalysisResult).filter(AnalysisResult.report_id == case.report_id).first()
        if not analysis:
            continue
        total += 1
        gold = case.gold_lsr
        per_rule.setdefault(gold, {"correct": 0, "total": 0})
        per_rule[gold]["total"] += 1
        top1_hit = analysis.primary_lsr == gold
        top2_hit = top1_hit or analysis.secondary_lsr == gold
        if top1_hit:
            correct_top1 += 1
            per_rule[gold]["correct"] += 1

    if total == 0:
        return {"insufficient_data": True, "message": "Gold-set LSR reports have not been analyzed yet."}

    return {
        "insufficient_data": False,
        "dataset_note": "Computed on the synthetic/demo gold-set evaluation split -- NOT production OIL data.",
        "n_cases": total,
        "top1_accuracy": round(correct_top1 / total, 3),
        "per_rule": {
            rule: {"accuracy": round(v["correct"] / v["total"], 3) if v["total"] else 0, "support": v["total"]}
            for rule, v in per_rule.items()
        },
    }


def evaluate_human_review(db: Session) -> dict:
    total_reviews = db.query(HumanReview).count()
    if total_reviews == 0:
        return {"insufficient_data": True, "message": "No human review actions recorded yet."}
    modify_count = db.query(HumanReview).filter(HumanReview.action == "MODIFY").count()
    escalate_count = db.query(HumanReview).filter(HumanReview.action == "ESCALATE").count()
    feedback_count = db.query(Feedback).count()
    return {
        "insufficient_data": False,
        "total_reviews": total_reviews,
        "correction_rate": round(modify_count / total_reviews, 3),
        "escalation_rate": round(escalate_count / total_reviews, 3),
        "fields_corrected_total": feedback_count,
    }


def evaluate_similarity_and_clustering(db: Session) -> dict:
    from app.models.analysis import PrecursorFingerprint, PrecursorCluster
    n_fingerprints = db.query(PrecursorFingerprint).count()
    n_clusters = db.query(PrecursorCluster).count()
    if n_fingerprints < 4:
        return {"insufficient_data": True, "message": "Not enough analyzed reports for a similarity/clustering evaluation."}
    return {
        "insufficient_data": False,
        "note": "Cluster coherence is spot-checked qualitatively via top distinctive terms per cluster "
                "(see /api/dashboard/clusters); no held-out clustering ground truth exists for this prototype.",
        "n_fingerprints": n_fingerprints,
        "n_clusters": n_clusters,
    }


def full_evaluation_report(db: Session) -> dict:
    return {
        "sif_classification": evaluate_sif_classification(db),
        "lsr_mapping": evaluate_lsr_mapping(db),
        "human_review": evaluate_human_review(db),
        "similarity_and_clustering": evaluate_similarity_and_clustering(db),
        "disclaimer": (
            "All metrics on this page are computed against a team-authored synthetic/demo gold set "
            "(data/gold/gold_set.csv), not real OIL production data. They demonstrate the evaluation "
            "methodology, not claimed production accuracy."
        ),
    }
