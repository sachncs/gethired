"""Voice profile builder.

Computes a deterministic voice fingerprint from a MasterResume. Used by the
writer agent's instructions and by the validator to detect voice drift.
"""

from __future__ import annotations

import re
from collections import Counter
from statistics import mean, pstdev
from typing import Final

from gethired.models import Bullet, MasterResume, VoiceProfile

OPENING_VERB_RE: Final[re.Pattern[str]] = re.compile(r"\b([A-Z][a-z]+)\b")


def bullet_lengths(bullets: tuple[Bullet, ...]) -> list[int]:
    return [len(bullet.text) for bullet in bullets]


def opening_verbs(bullets: tuple[Bullet, ...]) -> tuple[str, ...]:
    counter: Counter[str] = Counter()
    for bullet in bullets:
        match = OPENING_VERB_RE.match(bullet.text)
        if match:
            counter[match.group(1).lower()] += 1
    return tuple(verb for verb, _ in counter.most_common(10))


def punctuation_density(bullets: tuple[Bullet, ...]) -> dict[str, float]:
    if not bullets:
        return {",": 0.0, ";": 0.0, ".": 0.0, ":": 0.0}
    total_chars = sum(len(b.text) for b in bullets)
    if total_chars == 0:
        return {",": 0.0, ";": 0.0, ".": 0.0, ":": 0.0}
    counts = {",": 0, ";": 0, ".": 0, ":": 0}
    for bullet in bullets:
        for char in counts:
            counts[char] += bullet.text.count(char)
    return {k: v / total_chars for k, v in counts.items()}


def sentence_counts(bullets: tuple[Bullet, ...]) -> tuple[int, int]:
    if not bullets:
        return (0, 0)
    counts = [b.text.count(".") + b.text.count(";") + 1 for b in bullets]
    return (min(counts), max(counts))


def build(master: MasterResume) -> VoiceProfile:
    """Compute a voice profile from the master resume's bullets.

    Args:
        master: The canonical master resume.

    Returns:
        A ``VoiceProfile`` describing length, verbs, punctuation, sentence count.
    """
    all_bullets: list[Bullet] = []
    for experience in master.experiences:
        all_bullets.extend(experience.bullets)
    for project in master.projects:
        all_bullets.extend(project.bullets)

    lengths = bullet_lengths(tuple(all_bullets))
    avg = mean(lengths) if lengths else 0.0
    std = pstdev(lengths) if len(lengths) > 1 else 0.0

    return VoiceProfile(
        avg_bullet_length=avg,
        bullet_length_stddev=std,
        opening_verbs=opening_verbs(tuple(all_bullets)),
        punctuation_density=punctuation_density(tuple(all_bullets)),
        sentence_count_per_bullet=sentence_counts(tuple(all_bullets)),
    )


__all__ = ["build"]
