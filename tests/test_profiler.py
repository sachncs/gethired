"""Tests for the voice profiler."""

from __future__ import annotations

from gethired.profiler import build
from gethired.parser import parse_tex


def test_voice_profile_computes_average_bullet_length(master_resume) -> None:
    profile = build(master_resume)
    assert profile.avg_bullet_length > 0


def test_voice_profile_extracts_opening_verbs(master_resume) -> None:
    profile = build(master_resume)
    assert any(v in {"designed", "built", "developed"} for v in profile.opening_verbs)


def test_voice_profile_punctuation_density_is_normalised(master_resume) -> None:
    profile = build(master_resume)
    assert all(0.0 <= density <= 1.0 for density in profile.punctuation_density.values())


def test_voice_profile_deterministic(master_resume) -> None:
    profile_a = build(master_resume)
    profile_b = build(master_resume)
    assert profile_a == profile_b
