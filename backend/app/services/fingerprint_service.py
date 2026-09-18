"""SIF Precursor Fingerprint builder (blueprint Part 3.6 / Part 5 "Simple Project Plan").
The reusable structured 'unit of intelligence' behind similarity search,
clustering, trends and site/activity ranking."""
from __future__ import annotations


def build_fingerprint(report, analysis, barrier_findings: list[dict], standards_tags: list[str] | None = None) -> dict:
    return {
        "report_id": report.id,
        "report_code": report.report_code,
        "sif_potential": analysis.sif_classification,
        "confidence": analysis.confidence,
        "life_saving_rule": analysis.primary_lsr,
        "hazard": analysis.hazard,
        "energy_source": analysis.energy_source,
        "worker_exposure": analysis.exposure_description,
        "exposure_proximity": analysis.exposure_proximity,
        "activity": analysis.activity_extracted,
        "location": analysis.location_extracted,
        "site": report.site.name if report.site else None,
        "barriers": barrier_findings,
        "potential_consequence": analysis.potential_consequence,
        "reason_codes": analysis.reason_codes,
        "risk_score": analysis.risk_score,
        "standards_tags": standards_tags or [],
        "occurred_at": report.occurred_at.isoformat() if report.occurred_at else None,
    }
