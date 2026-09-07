"""Capability eval tasks for the gethired framework.

These tasks target harder cases where agents may fail. They are
tagged ``capability`` (not ``regression``) so they signal a hill to
climb rather than a gate that must stay at 100%.

Each task probes a specific edge case:
- parser: special chars, missing sections, multiple URLs per bullet
- fetcher: malformed JSON-LD, empty HTML, redirects
- description: multi-role, implicit seniority, long JD
- writer: voice variance, quantification, keyword injection
- critic: subtle plagiarism, stem-match banned, parallelism, borderline quantification
- tailor: multi-JD, metrics preservation, ATS gates
"""

from __future__ import annotations

# Capability-eval YAMLs live alongside the regression suite.
