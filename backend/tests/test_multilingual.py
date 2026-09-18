"""Language diagnostics vs English-only pipeline gate."""
from app.nlp.preprocess import (
    detect_language_support,
    is_pipeline_supported_language,
    normalize_for_matching,
)


def test_chinese_only_abstains():
    lang = detect_language_support("完全是中文没有拉丁字母")
    assert lang.supported is False
    assert lang.reason
    assert is_pipeline_supported_language("完全是中文没有拉丁字母") is False


def test_hindi_devanagari_not_pipeline_supported():
    """Devanagari fails the English rule-pipeline gate (honest UNSUPPORTED_LANGUAGE).
    Lexicon gloss helpers may still normalize for experimental use."""
    text = "बिना लोटो अनुमति के काम शुरू किया गया"
    assert is_pipeline_supported_language(text) is False
    lang = detect_language_support(text)
    assert lang.supported is False
    assert lang.script == "devanagari"
    norm = normalize_for_matching(text)
    assert "loto" in norm


def test_latin_still_supported():
    lang = detect_language_support("Worker opened flange before LOTO was verified.")
    assert lang.supported is True
    assert lang.script == "latin"
    assert is_pipeline_supported_language("Worker opened flange before LOTO was verified.") is True
