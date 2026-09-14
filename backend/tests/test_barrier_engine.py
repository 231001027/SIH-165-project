"""Barrier-failure risk-component scoring, plus the project's required edge
cases: false positives, false-negative challenges and ambiguous reports
(blueprint Part 10.3 edge-case demo set)."""
from app.nlp.negation import analyze_barriers
from app.rules.barrier_rules import barrier_failure_component, STATUS_SEVERITY


def test_present_effective_scores_zero():
    findings = analyze_barriers("Isolation was correctly applied and verified before work began.")
    component, worst = barrier_failure_component(findings)
    assert component == 0.0


def test_failed_barrier_scores_high():
    findings = analyze_barriers("The pressure relief valve failed and did not work as intended.")
    component, worst = barrier_failure_component(findings)
    assert component >= STATUS_SEVERITY["FAILED"] - 0.01


def test_no_barrier_mentioned_scores_mild_uncertainty_not_zero_or_max():
    component, worst = barrier_failure_component([])
    assert 0.0 < component < 0.5


def test_multiple_barriers_worst_status_wins():
    findings = analyze_barriers(
        "PPE was worn correctly throughout the task, but the exclusion zone was not established."
    )
    component, worst = barrier_failure_component(findings)
    assert worst == "Exclusion Zone"
    assert component >= 0.75


# --- Required edge cases (blueprint Part 10.3) -----------------------------

def test_false_positive_confined_space_all_barriers_present():
    """'Confined-space entry was completed with a valid permit, verified gas
    test, and full PPE. No issues noted.' must NOT show barrier failures."""
    findings = analyze_barriers(
        "Confined-space entry was completed with a valid permit, verified gas test, and full PPE. No issues noted."
    )
    failure_statuses = {"MISSING", "FAILED", "BYPASSED"}
    assert not any(f.status in failure_statuses for f in findings)


def test_false_positive_word_fall_in_unrelated_context():
    from app.nlp.entity_extraction import extract_entities
    entities = extract_entities(
        "Employee mentioned the word 'fall' while describing a decline in the site's monthly safety scores."
    )
    assert "GRAVITY" not in entities.energy_categories
