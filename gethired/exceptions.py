"""Exception hierarchy for the gethired system.

All exceptions inherit from ``Exception`` and end with ``Error`` per AGENTS.md.
"""

from __future__ import annotations


class ResumeTailoringError(Exception):
    """Base exception for all gethired errors.

    Catch this to handle any gethired-specific failure.
    """


class ConfigurationError(ResumeTailoringError):
    """Raised when configuration is invalid or missing required values."""


class MasterParsingError(ResumeTailoringError):
    """Raised when the master resume cannot be parsed from its source format."""


class JobDescriptionRetrievalError(ResumeTailoringError):
    """Raised when a job description URL cannot be retrieved or extracted."""


class GroundingViolationError(ResumeTailoringError):
    """Raised when the tailored resume contains a fact not grounded in master."""


class StyleViolationError(ResumeTailoringError):
    """Raised when the tailored resume fails style checks (banned words, parallelism)."""


class PlagiarismViolationError(ResumeTailoringError):
    """Raised when the tailored resume contains unacceptably long JD phrase overlap."""


class AtsGateFailureError(ResumeTailoringError):
    """Raised when one or more ATS gates fail.

    Attributes:
        failed_gates: Tuple of ``AtsGate`` enum values that failed.
    """

    def __init__(self, message: str, failed_gates: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.failed_gates: tuple[str, ...] = failed_gates
