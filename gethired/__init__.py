"""gethired — multi-agent CV tailoring system.

Public surface (intentionally small):

* :class:`Tailor` — orchestrator
* :class:`Resume` — parsed master resume
* :class:`Tailored` — produced tailored resume
* :class:`Job` — job description (the JD)
* :func:`parse` — convenience: parse a master resume from any supported format
* :func:`fetch` — convenience: fetch a JD with caching + retry

Submodules are imported lazily so that ``import gethired`` does not require
``trafilatura``, ``pymupdf``, ``pydantic_ai``, etc. Users who only need
:func:`parse` or :class:`Resume` can do ``from gethired import parse, Resume``
without triggering the full dependency chain.
"""

from __future__ import annotations

import importlib
import warnings
from typing import TYPE_CHECKING, Any

# PyMuPDF's SWIG-generated C extension sets ``__module__`` on builtin types
# (``SwigPyPacked``, ``SwigPyObject``, ``swigvarlink``) at import time. Python
# 3.12+ emits a ``DeprecationWarning`` for each. Silence the noise here so the
# filter is in effect before ``gethired.parser`` or ``gethired.validator``
# imports ``pymupdf``.
warnings.filterwarnings(
    "ignore",
    message=r"builtin type .* has no __module__ attribute",
    category=DeprecationWarning)

if TYPE_CHECKING:
    from gethired.exceptions import (
        AtsError,
        CompileError,
        ConfigError,
        FetchError,
        GroundingError,
        ParseError,
        PlagiarismError,
        StyleError,
        TailorError)
    from gethired.fetch import fetch
    from gethired.models import (
        Citation,
        Contact,
        Job,
Resume,
        Tailored)
    from gethired.parse import parse
    from gethired.tailor import Tailor
    from gethired.version import __version__


def __getattr__(name: str) -> Any:
    """Lazy attribute access for the public API.

    Defers heavy imports (pydantic_ai, trafilatura, pymupdf) until the
    user actually accesses a public symbol. This makes ``import gethired``
    cheap and side-effect free.
    """
    lazy_loads = {
        "Tailor": "gethired.tailor",
        "Resume": "gethired.models",
        "Tailored": "gethired.models",
        "Job": "gethired.models",
        "Contact": "gethired.models",
        "Citation": "gethired.models",
        "parse": "gethired.parse",
        "fetch": "gethired.fetch",
        "TailorError": "gethired.exceptions",
        "ParseError": "gethired.exceptions",
        "ConfigError": "gethired.exceptions",
        "FetchError": "gethired.exceptions",
        "GroundingError": "gethired.exceptions",
        "StyleError": "gethired.exceptions",
        "PlagiarismError": "gethired.exceptions",
        "AtsError": "gethired.exceptions",
        "CompileError": "gethired.exceptions",
        "__version__": "gethired.version",
    }
    if name in lazy_loads:
        module = importlib.import_module(lazy_loads[name])
        attr = getattr(module, name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module 'gethired' has no attribute {name!r}")


__all__ = [
    "AtsError",
    "Citation",
    "CompileError",
    "ConfigError",
    "Contact",
    "FetchError",
    "GroundingError",
    "Job",
    "Resume",
    "ParseError",
    "PlagiarismError",
    "StyleError",
    "Tailor",
    "TailorError",
    "Tailored",
    "__version__",
    "fetch",
    "parse",
]
