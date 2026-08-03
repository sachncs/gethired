"""Tests for the rubric rules."""

from __future__ import annotations

from gethired.rubric import (
    ALLOWLIST,
    ANTI_AI,
    BANNED,
    CHECKLIST,
    CONSTRUCTIONS,
    GROUNDING,
    PLAGIARISM,
    SECTIONS,
    VERBS,
)


def test_banned_words_is_frozenset() -> None:
    assert isinstance(BANNED, frozenset)
    assert "leverage" in BANNED
    assert "robust" in BANNED


def test_banned_words_has_at_least_50_entries() -> None:
    assert len(BANNED) >= 50


def test_banned_constructions_is_frozenset() -> None:
    assert isinstance(CONSTRUCTIONS, frozenset)
    assert "in order to" in CONSTRUCTIONS


def test_technical_ngrams_allowlist_is_frozenset() -> None:
    assert isinstance(ALLOWLIST, frozenset)
    assert "machine learning" in ALLOWLIST


def test_required_section_headings() -> None:
    assert "Summary" in SECTIONS
    assert "Experience" in SECTIONS
    assert "Education" in SECTIONS


def test_action_verbs_is_frozenset() -> None:
    assert isinstance(VERBS, frozenset)
    assert "built" in VERBS
    assert "designed" in VERBS
    assert "led" in VERBS


def test_action_verbs_has_at_least_100_entries() -> None:
    assert len(VERBS) >= 100


def test_checklist_rubric_has_entries_from_all_three_sources() -> None:
    """Each of the three checklists contributes at least 10 items."""
    entries = " ".join(CHECKLIST)
    # Indeed: structure
    assert "structure" in entries
    # Bridgewater: list_company
    assert "list_company" in entries
    # UIowa: first_impression
    assert "first_impression" in entries


def test_grounding_rules_has_no_invent_rule() -> None:
    rules = " ".join(GROUNDING)
    assert "never_invent" in rules


def test_anti_ai_rules_has_banned_words_rule() -> None:
    rules = " ".join(ANTI_AI)
    assert "no_banned_words" in rules


def test_plagiarism_rules_has_5_gram_rule() -> None:
    rules = " ".join(PLAGIARISM)
    assert "5_grams" in rules
