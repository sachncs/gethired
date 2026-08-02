"""Central logging configuration using loguru.

All modules import the same logger from here. Per-step events are emitted as
structured records via ``logger.bind`` so they can be ingested by Logfire or
other OpenTelemetry-compatible backends.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger as default_logger
from loguru._logger import Logger

from gethired.constants import LOGFIRE_TOKEN_ENV_VAR

_configured: bool = False


def utcnow_iso() -> str:
    """Return current UTC time as ISO-8601 string with millisecond precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def configure_logging(
    debug: bool = False,
    log_file: Path | None = None,
    run_id: str | None = None,
) -> Logger:
    """Configure the global loguru logger.

    Args:
        debug: When ``True``, sets the console level to DEBUG; otherwise INFO.
        log_file: Optional path to a JSON-structured log file.
        run_id: Optional run identifier bound to every log record.

    Returns:
        The configured ``loguru`` ``Logger`` instance.
    """
    global _configured
    default_logger.remove()

    level = "DEBUG" if debug else "INFO"
    default_logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> | "
            "<level>{message}</level>"
        ),
        serialize=False,
        backtrace=True,
        diagnose=debug,
    )

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        default_logger.add(
            log_file,
            level="DEBUG",
            serialize=True,
            rotation="10 MB",
            retention="7 days",
            enqueue=True,
        )

    if run_id is not None:
        default_logger.configure(extra={"run_id": run_id})

    _configure_logfire_if_available(run_id)

    _configured = True
    return default_logger


def _configure_logfire_if_available(run_id: str | None) -> None:
    """Initialise Logfire only when ``LOGFIRE_TOKEN`` is set in the environment."""
    import os

    if not os.environ.get(LOGFIRE_TOKEN_ENV_VAR):
        return

    try:
        import logfire  # type: ignore[import-not-found]
    except ImportError:
        return

    logfire.configure()
    logfire.instrument_pydantic_ai()
    if run_id is not None:
        logfire.configure(tags={"run_id": run_id})


def step_logger(step_name: str, run_id: str | None = None, **fields: Any) -> Logger:
    """Return a logger bound to the step name and optional run id.

    Args:
        step_name: Stable identifier for the step (e.g. ``"fetch_jd"``).
        run_id: Optional run identifier.
        **fields: Additional context fields to bind.

    Returns:
        A ``Logger`` with bound context.
    """
    if not _configured:
        configure_logging(run_id=run_id)
    bound: Logger = default_logger.bind(step=step_name)
    if run_id is not None:
        bound = bound.bind(run_id=run_id)
    for key, value in fields.items():
        bound = bound.bind(**{key: value})
    return bound


def emit_event(event_name: str, run_id: str | None = None, **fields: Any) -> None:
    """Emit a structured event via the global logger.

    Args:
        event_name: Stable event identifier (e.g. ``"tailor.step.complete"``).
        run_id: Optional run identifier for correlation.
        **fields: Arbitrary structured fields to attach.
    """
    bound = step_logger(event_name, run_id=run_id)
    bound.info(event_name, **fields)


__all__ = [
    "configure_logging",
    "emit_event",
    "step_logger",
    "utcnow_iso",
]
