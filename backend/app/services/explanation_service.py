"""
Explainable "Why flagged?" generation (blueprint Part 3.1 step 4 / Part 6.1).

Always template-based first (never hidden model chain-of-thought), composed
strictly from already-extracted fields. May optionally be smoothed into more
natural prose by the bounded LLM layer -- see llm_client.py.
"""
from __future__ import annotations


def build_explanation(
    sif_classification: str,
    hazard_label: str | None,
    exposure_proximity: str,
    worst_barrier_type: str | None,
    worst_barrier_status: str | None,
    lsr_primary: str,
    reason_codes: list[str],
) -> str:
    if sif_classification == "REVIEW":
        return (
            "Insufficient or conflicting evidence for a confident automated SIF "
            "classification. This report has been routed to human HSE review "
            "rather than being force-classified."
        )

    if sif_classification == "NON_SIF":
        if not hazard_label:
            return (
                "No meaningful high-energy hazard or worker-exposure evidence was "
                "detected in the narrative, so this report is classified as NON-SIF."
            )
        return (
            f"A possible {hazard_label.lower()} reference was detected, but there is "
            "no evidence of worker exposure or a failed/missing safety barrier, so "
            "this report does not show SIF-precursor characteristics."
        )

    clauses = []
    if hazard_label:
        clauses.append(f"the report describes {hazard_label.lower()}")
    if exposure_proximity in ("HIGH", "MEDIUM"):
        clauses.append("direct or nearby worker exposure to that hazard")
    if worst_barrier_type and worst_barrier_status and worst_barrier_status != "PRESENT_EFFECTIVE":
        status_phrase = {
            "MISSING": f"a missing {worst_barrier_type.lower()} barrier",
            "FAILED": f"a failed {worst_barrier_type.lower()} barrier",
            "BYPASSED": f"a bypassed {worst_barrier_type.lower()} barrier",
            "NOT_VERIFIED": f"an unverified {worst_barrier_type.lower()} barrier",
            "UNKNOWN": f"an unclear status for the {worst_barrier_type.lower()} barrier",
        }.get(worst_barrier_status)
        if status_phrase:
            clauses.append(status_phrase)
    if "REPEAT_PRECURSOR" in reason_codes:
        clauses.append("a repeat precursor pattern at this site/activity")

    if not clauses:
        clauses.append("multiple weaker risk indicators combined")

    body = ", ".join(clauses[:-1])
    if body:
        body = f"{body} and {clauses[-1]}"
    else:
        body = clauses[0]

    lsr_clause = f" Mapped to the IOGP Life-Saving Rule: {lsr_primary}." if lsr_primary != "No applicable rule" else ""

    return f"Flagged as {sif_classification} because {body}.{lsr_clause}"
