"""Multilingual fail-safe and Hindi lexicon overlay checks."""
from app.nlp.preprocess import detect_language_support, normalize_for_matching


def test_chinese_only_abstains():
    lang = detect_language_support("完全是中文没有拉丁字母")
    assert lang.supported is False
    assert lang.reason


def test_hindi_loto_normalizes_to_english_glosses():
    text = "बिना लोटो अनुमति के काम शुरू किया गया"
    lang = detect_language_support(text)
    assert lang.supported is True
    assert lang.script == "devanagari"
    norm = normalize_for_matching(text)
    assert "loto" in norm
    assert "permit" in norm or "without" in norm


def test_latin_still_supported():
    lang = detect_language_support("Worker opened flange before LOTO was verified.")
    assert lang.supported is True
    assert lang.script == "latin"
