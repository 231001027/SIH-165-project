"""Precursor clustering orchestration (blueprint Part 1.3 Stage 13). Clusters
only SIF-positive (HIGH/MEDIUM) fingerprints -- clustering NON_SIF/LOW noise
together is not useful HSE intelligence."""
from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.models.analysis import AnalysisResult, PrecursorFingerprint, PrecursorCluster, SifClassification
from app.models.report import Report, ReportSource
from app.ml.clustering import cluster_reports


def recompute_clusters(db: Session) -> list[PrecursorCluster]:
    rows = (
        db.query(PrecursorFingerprint, Report.narrative)
        .join(Report, Report.id == PrecursorFingerprint.report_id)
        .join(AnalysisResult, AnalysisResult.report_id == Report.id)
        .filter(
            AnalysisResult.sif_classification.in_([SifClassification.HIGH, SifClassification.MEDIUM]),
            # PUBLIC_CORPUS rows are real external incidents used only to ground
            # similarity search -- clustering surfaces recurring patterns within
            # OIL's OWN report stream, so they must not be mixed in here.
            Report.source != ReportSource.PUBLIC_CORPUS,
        )
        .all()
    )
    if len(rows) < 4:
        return []

    fingerprints = [r[0] for r in rows]
    narratives = [r[1] for r in rows]
    embeddings = np.array([fp.embedding for fp in fingerprints])

    assignments, cluster_meta = cluster_reports(narratives, embeddings)

    db.query(PrecursorCluster).delete()
    db.flush()

    cluster_id_map: dict[int, PrecursorCluster] = {}
    for local_id, meta in cluster_meta.items():
        member_fps = [fp for fp, a in zip(fingerprints, assignments) if a == local_id]
        lsr_counts: dict[str, int] = {}
        site_counts: dict[str, int] = {}
        for fp in member_fps:
            lsr = fp.fingerprint_json.get("life_saving_rule")
            site = fp.fingerprint_json.get("site")
            if lsr:
                lsr_counts[lsr] = lsr_counts.get(lsr, 0) + 1
            if site:
                site_counts[site] = site_counts.get(site, 0) + 1
        dominant_lsr = max(lsr_counts, key=lsr_counts.get) if lsr_counts else None
        dominant_site = max(site_counts, key=site_counts.get) if site_counts else None

        cluster_row = PrecursorCluster(
            label=meta["label"],
            method="kmeans",
            member_count=meta["size"],
            top_terms=meta["top_terms"],
            dominant_lsr=dominant_lsr,
            dominant_site=dominant_site,
        )
        db.add(cluster_row)
        db.flush()
        cluster_id_map[local_id] = cluster_row

    for fp, assignment in zip(fingerprints, assignments):
        fp.cluster_id = cluster_id_map[assignment].id

    db.commit()
    return list(cluster_id_map.values())
