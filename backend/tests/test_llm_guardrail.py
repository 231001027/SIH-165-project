"""Tests for the LLM output validation guardrail (blueprint Part 5.4 Trust Layer
safeguard: "reject/flag any LLM output that introduces a hazard/barrier/LSR not
present in the source text"). No network call is made here -- these test the
pure vocabulary-check function directly."""
from app.services.llm_client import _validate_llm_output


def test_accepts_text_that_only_restates_given_fields():
    fields = {"sif": "HIGH", "hazard": "Stored / pressurized energy",
              "lsr": "Energy Isolation", "barrier": "Isolation / LOTO",
              "barrier_status": "NOT_VERIFIED"}
    text = ("Flagged as HIGH because stored pressurized energy was released near a worker "
            "with an unverified isolation, mapped to the Energy Isolation Life-Saving Rule.")
    assert _validate_llm_output(text, fields) is True


def test_rejects_text_introducing_an_unsupported_lsr():
    fields = {"sif": "HIGH", "hazard": "Stored / pressurized energy",
              "lsr": "Energy Isolation", "barrier": "Isolation / LOTO",
              "barrier_status": "NOT_VERIFIED"}
    # The report was mapped to Energy Isolation -- the LLM must not invent a
    # second, unsupported rule mapping in its rephrased explanation.
    text = "This is also a Confined Space violation with a missing gas test."
    assert _validate_llm_output(text, fields) is False


def test_rejects_text_introducing_an_unsupported_barrier():
    fields = {"sif": "MEDIUM", "hazard": "Gravity / fall hazard",
              "lsr": "Working at Height", "barrier": "Fall Protection",
              "barrier_status": "NOT_VERIFIED"}
    text = "The worker also lacked proper PPE and gas detection equipment."
    assert _validate_llm_output(text, fields) is False


def test_rejects_text_introducing_an_unsupported_hazard():
    fields = {"sif": "LOW", "hazard": None, "lsr": "No applicable rule",
              "barrier": None, "barrier_status": None}
    text = "This report also describes electrical energy exposure near live wiring."
    assert _validate_llm_output(text, fields) is False


def test_accepts_text_with_no_known_vocabulary_terms_at_all():
    fields = {"sif": "NON_SIF", "hazard": None, "lsr": "No applicable rule",
              "barrier": None, "barrier_status": None}
    text = "No significant safety concern was identified in this observation."
    assert _validate_llm_output(text, fields) is True
