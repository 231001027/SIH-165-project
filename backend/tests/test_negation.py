"""Negation-aware barrier engine tests (blueprint Part 3.7's central example:
'LOTO was correctly applied' must NOT be a failure; 'LOTO was not applied'
must be)."""
from app.nlp.negation import analyze_barriers


def _status_for(narrative: str, barrier_type: str) -> str | None:
    findings = analyze_barriers(narrative)
    for f in findings:
        if f.barrier_type == barrier_type:
            return f.status
    return None


def test_loto_correctly_applied_is_not_a_failure():
    status = _status_for("The technician confirmed LOTO was correctly applied before starting work.",
                          "Isolation / LOTO")
    assert status == "PRESENT_EFFECTIVE"


def test_loto_not_applied_is_missing():
    status = _status_for("LOTO was not applied before the technician began work on the panel.",
                          "Isolation / LOTO")
    assert status in ("MISSING", "FAILED")


def test_proceeded_before_confirming_isolation_is_not_verified():
    status = _status_for(
        "Technician opened a flange before confirming isolation. Residual pressure was released.",
        "Isolation / LOTO",
    )
    assert status == "NOT_VERIFIED"


def test_proceeded_before_gas_test_completed_is_not_verified_or_missing():
    status = _status_for(
        "Contractor entered a tank for inspection before the gas test was completed and the permit was signed.",
        "Gas Detection",
    )
    assert status in ("NOT_VERIFIED", "MISSING")


def test_ppe_worn_correctly_is_effective():
    status = _status_for("Worker wore full PPE including a harness and gloves throughout the task.", "PPE")
    assert status == "PRESENT_EFFECTIVE"


def test_bypass_is_detected():
    status = _status_for("The interlock was bypassed to allow the pump to keep running.", "Isolation / LOTO") \
        or _status_for("Operator bypassed the high-pressure trip alarm to keep the unit running.", "Isolation / LOTO")
    # bypass language without a specific barrier keyword may not tag "Isolation / LOTO";
    # test the general bypass detection against a barrier-bearing sentence instead:
    status2 = _status_for("The isolation was bypassed during the emergency repair.", "Isolation / LOTO")
    assert status2 == "BYPASSED"


def test_but_clause_splits_negative_and_affirmative_correctly():
    """'X was not complete, but LOTO was applied' -- the affirmative clause about
    LOTO must not be contaminated by the earlier negative clause about isolation
    completeness in general (blueprint Part 3.7's 'not... but' example)."""
    status = _status_for(
        "The isolation checklist was not fully complete, but LOTO was correctly applied and verified before work began.",
        "Isolation / LOTO",
    )
    assert status == "PRESENT_EFFECTIVE"


def test_no_barrier_mention_returns_no_findings_for_that_type():
    findings = analyze_barriers("A minor housekeeping issue was noted near the warehouse.")
    assert all(f.barrier_type != "Isolation / LOTO" for f in findings)


def test_unclear_barrier_mention_defaults_to_not_verified_not_a_guess():
    """When a barrier is mentioned with no polarity cue nearby, the engine must
    default to NOT_VERIFIED rather than assuming failure or success."""
    status = _status_for("The permit for the job was discussed during the shift handover.", "Permit-to-Work")
    assert status == "NOT_VERIFIED"
