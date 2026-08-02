"""Grader registry.

Maps grader names (referenced by name in task YAML) to callables. Tasks
use this indirection so graders can be swapped without touching the
task definitions.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evals.graders.code import (
    code_equal,
    code_field_length,
    code_field_present,
    code_json_round_trip,
    code_no_banned_words,
    code_no_jd_plagiarism,
    code_numbers_in_master,
    code_text_contains,
    code_text_not_contains,
)


class GraderRegistry:
    """Maps grader names to callables.

    Each grader signature: ``(*args, **kwargs) -> GraderResult``.

    Built-in code-based graders are pre-registered. Model-based
    graders (``model.grade``) can be registered at startup time.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Callable[..., Any]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        self._registry.update(
            {
                "code.equal": code_equal,
                "code.field_present": code_field_present,
                "code.field_length": code_field_length,
                "code.text_contains": code_text_contains,
                "code.text_not_contains": code_text_not_contains,
                "code.no_banned_words": code_no_banned_words,
                "code.no_jd_plagiarism": code_no_jd_plagiarism,
                "code.numbers_in_master": code_numbers_in_master,
                "code.json_round_trip": code_json_round_trip,
            }
        )

    def register(self, name: str, grader: Callable[..., Any]) -> None:
        """Register a grader by name."""
        self._registry[name] = grader

    def get(self, name: str) -> Callable[..., Any]:
        """Look up a grader by name; raises ``KeyError`` if missing."""
        if name not in self._registry:
            raise KeyError(
                f"Unknown grader {name!r}. Registered: {sorted(self._registry)}"
            )
        return self._registry[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._registry))

    def __contains__(self, name: str) -> bool:
        return name in self._registry


__all__ = ["GraderRegistry"]
