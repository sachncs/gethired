"""gethired — multi-agent CV tailoring system.

Public surface (intentionally small):

* :class:`Tailor` — orchestrator
* :class:`Master` — parsed master resume
* :class:`Tailored` — produced tailored resume
* :class:`Job` — job description (the JD)
* :func:`parse` — convenience: parse a master resume from any supported format
* :func:`fetch` — convenience: fetch a JD with caching + retry
"""

from __future__ import annotations

from gethired.exceptions import (
    AtsError,
    CompileError,
    ConfigError,
    FetchError,
    GroundingError,
    ParseError,
    PlagiarismError,
    StyleError,
    TailorError,
)
from gethired.models import (
    Citation,
    Contact,
    Job,
    Master,
    Tailored,
)
from gethired.parse import parse
from gethired.fetch import fetch
from gethired.tailor import Tailor
from gethired.version import __version__

__version__: str

__all__ = [
    "AtsError",
    "Citation",
    "CompileError",
    "ConfigError",
    "Contact",
    "FetchError",
    "GroundingError",
    "Job",
    "Master",
    "ParseError",
    "PlagiarismError",
    "StyleError",
    "Tailor",
    "TailorError",
    "Tailored",
    "__version__",
    "fetch",
    "dispatch",
]
