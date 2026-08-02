"""Tests for the rubric rules."""

from __future__ import annotations

from gethired.rubric import (
    ACTION_VERBS,
    ANTI_AI_RULES,
    BANNED_CONSTRUCTIONS,
    BANNED_WORDS,
    CHECKLIST_RUBRIC,
    GROUNDING_RULES,
    PLAGIARISM_RULES,
    REQUIRED_SECTION_HEADINGS,
    TECHNICAL_NGRAMS_ALLOWLIST,
)


def test_banned_words_is_frozenset() -> None:
    assert isinstance(BANNED_WORDS, frozenset)
    assert "leverage" in BANNED_WORDS
    assert "robust" in BANNED_WORDS


def test_banned_words_has_at_least_50_entries() -> None:
    assert len(BANNED_WORDS) >= 50


def test_banned_constructions_is_frozenset() -> None:
    assert isinstance(BANNED_CONSTRUCTIONS, frozenset)
    assert "in order to" in BANNED_CONSTRUCTIONS


def test_technical_ngrams_allowlist_is_frozenset() -> None:
    assert isinstance(TECHNICAL_NGRAMS_ALLOWLIST, frozenset)
    assert "machine learning" in TECHNICAL_NGRAMS_ALLOWLIST


def test_required_section_headings() -> None:
    assert "Summary" in REQUIRED_SECTION_HEADINGS
    assert "Experience" in REQUIRED_SECTION_HEADINGS
    assert "Education" in REQUIRED_SECTION_HEADINGS


def test_action_verbs_is_frozenset() -> None:
    assert isinstance(ACTION_VERBS, frozenset)
    assert "built" in ACTION_VERBS
    assert "designed" in ACTION_VERBS
    assert "led" in ACTION_VERBS


def test_action_verbs_has_at_least_100_entries() -> None:
    assert len(ACTION_VERBS) >= 100


def test_checklist_rubric_has_entries_from_all_three_sources() -> None:
    """Each of the three checklists contributes at least 10 items."""
    entries = " ".join(CHECKLIST_RUBRIC)
    # Indeed: structure
    assert "structure" in entries
    # Bridgewater: list_company
    assert "list_company" in entries
    # UIowa: first_impression
    assert "first_impression" in entries


def test_grounding_rules_has_no_invent_rule() -> None:
    rules = " ".join(GROUNDING_RULES)
    assert "never_invent" in rules


def test_anti_ai_rules_has_banned_words_rule() -> None:
    rules = " ".join(ANTI_AI_RULES)
    assert "no_banned_words" in rules


def test_plagiarism_rules_has_5_gram_rule() -> None:
    rules = " ".join(PLAGIARISM_RULES)
    assert "5_grams" in rules
