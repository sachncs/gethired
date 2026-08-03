"""Shared text-cleaning and contact-pattern primitives.

The TeX parser and the plain-text parser both need to recognise contact
information and normalise inline text. Keeping those primitives here, with
no dependency on the parsers themselves, avoids an import cycle.
"""

from __future__ import annotations

import re
from typing import Final

from gethired.exceptions import ParseError

__all__ = [
    "EMAIL_RE",
    "GITHUB_BARE_RE",
    "GITHUB_RE",
    "HREF_RE",
    "LINKEDIN_BARE_RE",
    "LINKEDIN_RE",
    "MATH_OP_RE",
    "PHONE_RE",
    "clean",
    "require_contact",
]

PHONE_RE: Final[re.Pattern[str]] = re.compile(r"(\+?\(?\d[\d\s().-]{7,}\d)")
EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{mailto:([^}]+)\}\{[^}]*\}|(?<![\w@.])([\w.+-]+@[\w-]+\.[\w.-]+)"
)
GITHUB_RE: Final[re.Pattern[str]] = re.compile(r"\\href\{(https?://github\.com/[^}]+)\}\{[^}]*\}")
GITHUB_BARE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w/])(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9._-]+"
)
LINKEDIN_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{(https?://(?:www\.)?linkedin\.com/[^}]+)\}\{[^}]*\}"
)
LINKEDIN_BARE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w/])(?:https?://)?(?:www\.)?linkedin\.com/[A-Za-z0-9._/-]+"
)
HREF_RE: Final[re.Pattern[str]] = re.compile(r"\\href\{([^}]+)\}\{((?:[^{}]|\{[^}]*\})*)\}")
MATH_OP_RE: Final[re.Pattern[str]] = re.compile(r"\\(log|ln|exp|sin|cos|tan|lim|min|max)\b")


def clean(text: str) -> str:
    """Strip residual LaTeX wrappers and normalise whitespace."""
    cleaned = HREF_RE.sub(lambda m: m.group(2), text)
    cleaned = re.sub(r"\\textbf\{([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\\textsc\{([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\\emph\{([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\\?[$]([^$]*?)\\?[$]", r"\1", cleaned)
    cleaned = re.sub(r"\\&", "&", cleaned)
    cleaned = re.sub(r"\\([\"%$#_{}~^])", r"\1", cleaned)
    cleaned = re.sub(r'\\"', '"', cleaned)
    cleaned = re.sub(r"\\vspace\{[^}]*\}", "", cleaned)
    cleaned = re.sub(r"\\,", " ", cleaned)
    cleaned = re.sub(r"\\cdot", "·", cleaned)
    cleaned = re.sub(r"\\[`'^~=.]([A-Za-z])", r"\1", cleaned)
    cleaned = MATH_OP_RE.sub(r"\1", cleaned)
    cleaned = re.sub(r"\\[A-Za-z]+", "", cleaned)
    cleaned = re.sub(r"[{}]", "", cleaned)
    cleaned = re.sub(r"~", " ", cleaned)
    cleaned = re.sub(r"\\\\", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def require_contact(name: str, city: str, phone: str, email: str) -> None:
    """Fail fast when any required contact field is missing.

    Raises:
        ParseError: When name, city, phone, or email is empty.
    """
    missing = [
        label
        for label, value in (
            ("name", name),
            ("city", city),
            ("phone", phone),
            ("email", email),
        )
        if not value
    ]
    if missing:
        raise ParseError(f"Resume is missing required contact fields: {', '.join(missing)}")
