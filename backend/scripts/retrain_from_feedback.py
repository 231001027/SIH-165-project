#!/usr/bin/env python3
"""Manual/scheduled batch retrain from Feedback corrections.

Usage (from backend/, venv active):
    python scripts/retrain_from_feedback.py

Reads Feedback rows (sif_classification), joins report features, retrains the
LogisticRegression SIF classifier, and writes metadata including
training_row_count / feedback to app/ml/artifacts/last_retrain.json.
PUBLIC_CORPUS rows are excluded.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.services.retrain_service import retrain_classifier_from_feedback

ARTIFACT = ROOT / "app" / "ml" / "artifacts" / "last_retrain.json"


def main() -> int:
    db = SessionLocal()
    try:
        result = retrain_classifier_from_feedback(db)
        result["retrained_at"] = datetime.now(timezone.utc).isoformat()
        result["training_row_count"] = result.get("n_train", 0)
        result["model_version_note"] = (
            f"feedback-augmented-{result.get('feedback_overrides', 0)}-overrides"
        )
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0 if result.get("trained") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
