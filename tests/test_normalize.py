"""Tests for the text normalisation helpers."""

from __future__ import annotations

from gethired.normalize import (
    canonicalize_numeric,
    extract_ngrams,
    is_action_verb,
    normalise_whitespace,
    strip_latex_commands,
    tokenize_for_overlap,
)


def test_canonicalize_numeric_handles_plain_digits() -> None:
    assert canonicalize_numeric("ran 10,000+ tests") >= {10_000}


def test_canonicalize_numeric_handles_k_suffix() -> None:
    assert canonicalize_numeric("10K users") >= {10_000}
    assert canonicalize_numeric("5k req/sec") >= {5_000}
    assert canonicalize_numeric("2.5M requests") >= {2_500_000}


def test_canonicalize_numeric_handles_percent_and_dollar() -> None:
    assert canonicalize_numeric("reduced by 30%") >= {30}
    assert canonicalize_numeric("saved $5000") >= {5000}


def test_canonicalize_numeric_handles_number_words() -> None:
    assert canonicalize_numeric("handled ten thousand requests") >= {10_000}
    assert canonicalize_numeric("trained twenty models") >= {20}


def test_canonicalize_numeric_returns_empty_for_no_numbers() -> None:
    assert canonicalize_numeric("no digits here") == set()


def test_canonicalize_numeric_empty_input() -> None:
    assert canonicalize_numeric("") == set()


def test_strip_latex_commands_removes_href() -> None:
    assert strip_latex_commands(r"\href{https://x.com}{X}") == "X"


def test_strip_latex_commands_removes_textbf_and_math() -> None:
    assert strip_latex_commands(r"\textbf{R\&D}") == "R&D"
    assert strip_latex_commands(r"the $O(1)$ algorithm") == "the O(1) algorithm"


def test_strip_latex_commands_handles_escapes() -> None:
    assert strip_latex_commands(r"R\&D team") == "R&D team"


def test_normalise_whitespace_collapses_and_lowers() -> None:
    assert normalise_whitespace("Hello   World\n\t  Foo") == "hello world foo"


def test_normalise_whitespace_empty_input() -> None:
    assert normalise_whitespace("") == ""


def test_tokenize_for_overlap_extracts_words() -> None:
    tokens = tokenize_for_overlap("Built serverless ML pipelines on Modal")
    assert "built" in tokens
    assert "modal" in tokens
    assert "ML" not in tokens  # uppercase normalised


def test_tokenize_for_overlap_skips_punctuation() -> None:
    tokens = tokenize_for_overlap("Hello, world!")
    assert "hello" in tokens
    assert "world" in tokens


def test_extract_ngrams_returns_correct_count() -> None:
    tokens = ("a", "b", "c", "d")
    assert extract_ngrams(tokens, 2) == ("a b", "b c", "c d")


def test_extract_ngrams_returns_empty_for_short_input() -> None:
    assert extract_ngrams(("a",), 3) == ()


def test_is_action_verb_recognises_common_verbs() -> None:
    assert is_action_verb("Built")
    assert is_action_verb("Designed")
    assert is_action_verb("Engineered")
    assert is_action_verb("Led")


def test_is_action_verb_rejects_non_verbs() -> None:
    assert not is_action_verb("the")
    assert not is_action_verb("responsible")
