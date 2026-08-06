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


class AntiBotError(FetchError):
    """Raised when a fetch is blocked by a WAF / anti-bot challenge (CF, AWS WAF, …).

    Carries the URL, HTTP status, and the response headers that triggered the
    classification so callers can branch and surface a paste-fallback UX.
    """

    def __init__(
        self,
        url: str,
        status: int,
        markers: tuple[str, ...]) -> None:
        marker_blob = ", ".join(markers)
        super().__init__(f"Anti-bot challenge for {url}: HTTP {status} (markers: {marker_blob})")
        self.url = url
        self.status = status
        self.markers = markers


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
