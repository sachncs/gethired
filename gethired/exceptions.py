"""Exception hierarchy for the gethired system.

All exceptions inherit from ``Exception`` and end with ``Error`` per AGENTS.md.
"""

from __future__ import annotations


class TailorError(Exception):
    """Base exception for all gethired errors.

    Catch this to handle any gethired-specific failure.
    """


class ConfigError(TailorError):
    """Raised when configuration is invalid or missing required values."""


class ParseError(TailorError):
    """Raised when the master resume cannot be parsed from its source format."""


class FetchError(TailorError):
    """Raised when a job description URL cannot be retrieved or extracted."""


class GroundingError(TailorError):
    """Raised when the tailored resume contains a fact not grounded in master."""


class StyleError(TailorError):
    """Raised when the tailored resume fails style checks (banned words, parallelism)."""


class PlagiarismError(TailorError):
    """Raised when the tailored resume contains unacceptably long JD phrase overlap."""


class AtsError(TailorError):
    """Raised when one or more ATS gates fail.

    Attributes:
        failed_gates: Tuple of ``AtsGate`` enum values that failed.
    """

    def __init__(self, message: str, failed_gates: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.failed_gates: tuple[str, ...] = failed_gates


class CompileError(TailorError):
    """Raised when the LaTeX-to-PDF compilation step fails or the engine is missing."""
