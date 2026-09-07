"""Public consent API for gethired.

Separates consent tracking from the CLI surface so that:

- The CLI (``gethired.cli``) prompts for consent before running a tailoring pass
- Library users (``from gethired import ...``) can check or grant consent
  programmatically without going through the interactive prompt
- Test code can bypass the prompt by monkey-patching ``require``

The on-disk format is a single JSON object: ``{"timestamp": ISO-8601}``.
After 90 days the user is re-prompted.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from gethired.constants import CONSENT, CONSENT_DAYS, CONSENT_PATH

__all__ = ["current", "require", "reset", "set_path"]

# Module-level mutable container avoids the PLW0603 'global' warning.
consent_path_override: list[str | None] = [None]


def consent_path() -> str:
    """Return the active consent file path (override or default)."""
    override = consent_path_override[0]
    if override is not None:
        return override
    return CONSENT_PATH


def set_path(path: str) -> None:
    """Override the default consent file location (used by tests).

    Pass ``None`` to restore the default.
    """
    consent_path_override[0] = path


def current() -> bool:
    """Return True if a valid, unexpired consent record exists on disk."""
    consent_file = Path(consent_path()).expanduser()
    if not consent_file.exists():
        return False
    try:
        data = json.loads(consent_file.read_text())
        timestamp = datetime.fromisoformat(data["timestamp"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return (datetime.now(UTC) - timestamp).days < CONSENT_DAYS


def record() -> None:
    """Persist a fresh consent timestamp to disk."""
    consent_file = Path(consent_path()).expanduser()
    consent_file.parent.mkdir(parents=True, exist_ok=True)
    consent_file.write_text(json.dumps({"timestamp": datetime.now(UTC).isoformat()}))


def reset() -> None:
    """Remove any persisted consent record (used by tests)."""
    consent_file = Path(consent_path()).expanduser()
    if consent_file.exists():
        consent_file.unlink()


def require(force: bool = False) -> None:
    """Ensure consent is recorded; prompt the user if not.

    Args:
        force: When True, re-prompt even if a valid consent record exists.

    Raises:
        typer.Exit: When the user declines.
    """
    if not force and current():
        return

    typer.echo(CONSENT, err=True)
    if not typer.confirm("Continue?", default=False):
        raise typer.Exit(code=1)
    record()
