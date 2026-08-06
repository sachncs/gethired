"""Convenience entry point: parse a master resume from any supported format.

Detects the input format by extension and routes to the right parser:

* ``.tex`` → :func:`gethired.parser.tex`
* ``.pdf`` → :func:`gethired.parser.pdf`
* ``.png``/``.jpg``/``.jpeg``/``.tiff``/``.bmp`` → :func:`gethired.parser.image`
* anything else → :func:`gethired.parser.tex` (treats as TeX text or file)

Args:
    source: Path to the resume file, or raw TeX text.

Returns:
    The parsed ``Master`` resume.

Raises:
    ParseError: When the source cannot be parsed into a resume.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gethired.models import Resume
from gethired.parser import (
    image as _image)
from gethired.parser import (
    pdf as _pdf)
from gethired.parser import (
    tex as _tex)
from gethired.plain_text import parse_plain_text as _plain_text

__all__ = ["parse"]


# Map file extension to parser function. Lookup avoids the chain of
# ``if suffix == ...: return ...`` branches in the dispatcher below.
EXTENSION_PARSERS: dict[str, Callable[..., Resume]] = {
    ".tex": _tex,
    ".pdf": _pdf,
}
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tiff", ".bmp"})


def dispatch_path(path: Path) -> Master:
    """Parse a master from an existing Path by inspecting its extension."""
    suffix = path.suffix.lower()
    if suffix in EXTENSION_PARSERS:
        return EXTENSION_PARSERS[suffix](path)
    if suffix in _IMAGE_EXTENSIONS:
        return _image(path)
    # Unknown extension: peek at the content to decide between TeX and plain text
    content = path.read_text()
    if "\\documentclass" in content or "\\begin{document}" in content:
        return _tex(content)
    return _plain_text(content)


def dispatch_string(source: str) -> Master:
    """Parse a master from a string by content sniffing.

    Strings with a TeX preamble are routed to the TeX parser; short
    strings without newlines are treated as file paths; everything else
    falls through to the plain-text parser.
    """
    if "\\documentclass" in source or "\\begin{document}" in source:
        return _tex(source)
    is_likely_path = "\n" not in source and len(source) < 4096
    if is_likely_path and Path(source).exists():
        return dispatch_path(Path(source))
    return _plain_text(source)


def parse(source: str | Path) -> Master:
    """Parse a master resume from any supported format.

    Dispatches by file extension when ``source`` is a path, and by content
    sniffing when ``source`` is a string (TeX vs plain text).
    """
    if isinstance(source, Path):
        return dispatch_path(source)
    return dispatch_string(source)
