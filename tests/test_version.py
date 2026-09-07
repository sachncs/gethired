"""Tests for the gethired.version module."""

from __future__ import annotations

import re

import gethired
from gethired import version


def test_version_constant_exists() -> None:
    """version module exports a __version__ string."""
    assert isinstance(version.__version__, str)
    assert version.__version__, "__version__ must be non-empty"


def test_version_constant_is_semver_like() -> None:
    """The version string follows major.minor.patch semantics."""
    assert re.match(r"^\d+\.\d+\.\d+", version.__version__), (
        f"version {version.__version__!r} is not semver-like"
    )


def test_gethired_reexports_version() -> None:
    """The package __version__ matches the version module's __version__."""
    assert gethired.__version__ == version.__version__
