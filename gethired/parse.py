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

from pathlib import Path

from gethired.models import Master
from gethired.parser import (
    image as _image,
)
from gethired.parser import (
    pdf as _pdf,
)
from gethired.parser import (
    tex as _tex,
)
from gethired.plain_text import parse_plain_text as _plain_text

__all__ = ["parse"]


def parse(source: str | Path) -> Master:
    """Parse a master resume from any supported format.

    Dispatches by file extension when ``source`` is a path, and by content
    sniffing when ``source`` is a string (TeX vs plain text).
    """
    # If source is already a Path, dispatch directly by extension
    if isinstance(source, Path):
        suffix = source.suffix.lower()
        if suffix == ".tex":
            return _tex(source)
        if suffix == ".pdf":
            return _pdf(source)
        if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
            return _image(source)
        return _tex(source.read_text())
    # source is a string
    is_tex = "\\documentclass" in source or "\\begin{document}" in source
    if is_tex:
        return _tex(source)
    is_likely_path = "\n" not in source and len(source) < 4096
    if is_likely_path:
        path = Path(source)
        if path.exists():
            suffix = path.suffix.lower()
            if suffix == ".tex":
                return _tex(path)
            if suffix == ".pdf":
                return _pdf(path)
            if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
                return _image(path)
            return _tex(path.read_text())
    return _plain_text(source)
