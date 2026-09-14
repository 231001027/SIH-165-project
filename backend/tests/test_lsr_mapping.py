"""IOGP Life-Saving Rule mapping tests, including the explicit
naive-keyword-matching guard-rail from blueprint Part 3.4 ('height' alone
must not trigger Working at Height)."""
from app.nlp.entity_extraction import extract_entities
from app.rules.lsr_engine import classify_lsr, NO_APPLICABLE_RULE


def _classify(narrative: str):
    entities = extract_entities(narrative)
    return classify_lsr(narrative, entities)


def test_flagship_energy_isolation_scenario():
    result = _classify(
        "Technician opened a flange before confirming isolation. Residual pressure was released. No injury occurred."
    )
    assert result.primary == "Energy Isolation"


def test_bare_height_word_does_not_force_working_at_height():
    """'the pressure gauge reads a height of...' style incidental use of 'height'
    must not, by itself, be treated as a Working at Height precursor."""
    result = _classify("The pressure gauge reads a height of 15 on the dial, which was noted in the log.")
    assert result.primary != "Working at Height"


def test_genuine_working_at_height_scenario_maps_correctly():
    result = _classify(
        "Worker leaned out from a scaffold platform to reach a valve without re-anchoring the fall-arrest lanyard."
    )
    assert result.primary == "Working at Height"


def test_confined_space_scenario():
    result = _classify(
        "Contractor entered a tank for inspection before the gas test was completed and the permit was signed."
    )
    assert result.primary == "Confined Space"


def test_no_applicable_rule_for_routine_administrative_report():
    result = _classify("Printer in the site office was out of toner; IT was notified to replace the cartridge.")
    assert result.primary == NO_APPLICABLE_RULE


def test_line_of_fire_scenario():
    result = _classify("Worker walked beneath a suspended load during a lifting operation to retrieve a dropped tool.")
    assert result.primary in ("Line of Fire", "Safe Mechanical Lifting")
