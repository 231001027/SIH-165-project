"""English-only rule-pipeline language/script guard."""
from app.core.config import get_settings
from app.nlp.preprocess import (
    is_pipeline_supported_language,
    latin_token_ratio,
    UNSUPPORTED_LANGUAGE_MESSAGE,
)


def test_pure_english_passes():
    assert is_pipeline_supported_language(
        "Worker opened flange before LOTO was verified on the pump."
    ) is True


def test_pure_devanagari_fails():
    # Dense Hindi narrative — must fail the English pipeline gate.
    text = "बिना लोटो अनुमति के काम शुरू किया गया और फ्लैंज खोला गया"
    assert is_pipeline_supported_language(text) is False


def test_romanized_hindi_still_passes_ascii_gate():
    """Known limitation: Romanized Hindi uses Latin letters so the script gate
    passes even though keyword matching will not understand Hindi terms."""
    text = "bina loto anumati ke kaam shuru kiya gaya flange khola"
    assert is_pipeline_supported_language(text) is True


def test_code_mixed_at_threshold_boundary():
    """Construct a token mix that sits just below / at the configured threshold."""
    threshold = get_settings().PIPELINE_LATIN_TOKEN_RATIO_MIN
    # 7 Latin + 3 Devanagari = 0.70 exactly when threshold is 0.70
    at = "Worker opened flange before LOTO check done किया गया काम"
    # 4 Latin + 3 Devanagari ≈ 0.571 < 0.70
    below = "Worker opened flange LOTO किया गया काम"
    ratio_at = latin_token_ratio(at)
    ratio_below = latin_token_ratio(below)
    assert abs(threshold - 0.70) < 1e-9  # document expected default
    assert abs(ratio_at - 0.70) < 1e-9
    assert is_pipeline_supported_language(at) is True
    assert ratio_below < threshold
    assert is_pipeline_supported_language(below) is False


def test_chinese_fails():
    assert is_pipeline_supported_language("完全是中文没有拉丁字母") is False


def test_empty_fails():
    assert is_pipeline_supported_language("") is False
    assert is_pipeline_supported_language("   ") is False


def test_analyze_devanagari_returns_unsupported_language(db_session):
    from datetime import datetime, timezone
    from app.models.report import Report, ReportType, ReportSource
    from app.services.analysis_service import analyze_report

    report = Report(
        report_code="LANG-HI-1",
        report_type=ReportType.NEAR_MISS,
        title="Hindi narrative",
        narrative="बिना लोटो अनुमति के फ्लैंज खोला गया। कोई चोट नहीं हुई।",
        source=ReportSource.MANUAL,
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    analysis = analyze_report(db_session, report)
    assert analysis.sif_classification.value == "UNSUPPORTED_LANGUAGE"
    assert analysis.review_required is True
    assert analysis.hazard is None
    assert "UNSUPPORTED_LANGUAGE" in analysis.reason_codes
    assert UNSUPPORTED_LANGUAGE_MESSAGE in (analysis.abstain_reason or "")
    assert analysis.risk_breakdown.get("analysis_status") == "UNSUPPORTED_LANGUAGE"
