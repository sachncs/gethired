"""Tests for the text normalisation helpers."""

from __future__ import annotations

from gethired.normalize import (
    numbers,
    ngrams,
    verb,
    flatten,
    strip_latex,
    tokenize,
)


def test_canonicalize_numeric_handles_plain_digits() -> None:
    assert numbers("ran 10,000+ tests") >= {10_000}


def test_canonicalize_numeric_handles_k_suffix() -> None:
    assert numbers("10K users") >= {10_000}
    assert numbers("5k req/sec") >= {5_000}
    assert numbers("2.5M requests") >= {2_500_000}


def test_canonicalize_numeric_handles_percent_and_dollar() -> None:
    assert numbers("reduced by 30%") >= {30}
    assert numbers("saved $5000") >= {5000}


def test_canonicalize_numeric_handles_number_words() -> None:
    assert numbers("handled ten thousand requests") >= {10_000}
    assert numbers("trained twenty models") >= {20}


def test_canonicalize_numeric_returns_empty_for_no_numbers() -> None:
    assert numbers("no digits here") == set()


def test_canonicalize_numeric_empty_input() -> None:
    assert numbers("") == set()


def test_strip_latex_commands_removes_href() -> None:
    assert strip_latex(r"\href{https://x.com}{X}") == "X"


def test_strip_latex_commands_removes_textbf_and_math() -> None:
    assert strip_latex(r"\textbf{R\&D}") == "R&D"
    assert strip_latex(r"the $O(1)$ algorithm") == "the O(1) algorithm"


def test_strip_latex_commands_handles_escapes() -> None:
    assert strip_latex(r"R\&D team") == "R&D team"


def test_normalise_whitespace_collapses_and_lowers() -> None:
    assert flatten("Hello   World\n\t  Foo") == "hello world foo"


def test_normalise_whitespace_empty_input() -> None:
    assert flatten("") == ""


def test_tokenize_for_overlap_extracts_words() -> None:
    tokens = tokenize("Built serverless ML pipelines on Modal")
    assert "built" in tokens
    assert "modal" in tokens
    assert "ML" not in tokens  # uppercase normalised


def test_tokenize_for_overlap_skips_punctuation() -> None:
    tokens = tokenize("Hello, world!")
    assert "hello" in tokens
    assert "world" in tokens


def test_extract_ngrams_returns_correct_count() -> None:
    tokens = ("a", "b", "c", "d")
    assert ngrams(tokens, 2) == ("a b", "b c", "c d")


def test_extract_ngrams_returns_empty_for_short_input() -> None:
    assert ngrams(("a",), 3) == ()


def test_is_action_verb_recognises_common_verbs() -> None:
    assert verb("Built")
    assert verb("Designed")
    assert verb("Engineered")
    assert verb("Led")


def test_is_action_verb_rejects_non_verbs() -> None:
    assert not verb("the")
    assert not verb("responsible")
