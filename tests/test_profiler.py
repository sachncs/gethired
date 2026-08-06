"""Tests for the voice profiler."""

from __future__ import annotations

from gethired.profiler import build


def test_voice_profile_computes_average_bullet_length(resume) -> None:
    profile = build(resume)
    assert profile.avg_bullet_length > 0


def test_voice_profile_extracts_opening_verbs(resume) -> None:
    profile = build(resume)
    assert any(v in {"designed", "built", "developed"} for v in profile.opening_verbs)


def test_voice_profile_punctuation_density_is_normalised(resume) -> None:
    profile = build(resume)
    assert all(0.0 <= density <= 1.0 for density in profile.punctuation_density.values())


def test_voice_profile_deterministic(resume) -> None:
    profile_a = build(resume)
    profile_b = build(resume)
    assert profile_a == profile_b
