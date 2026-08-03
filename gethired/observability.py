"""Central logging configuration using loguru.

All modules import the same logger from here. Per-step events are emitted as
structured records via ``logger.bind``.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any  # Any: structured-log fields are arbitrary typed values

from loguru import logger as default_logger

if TYPE_CHECKING:
    # loguru does not export ``Logger`` as a runtime attribute; the type is
    # only available to static type checkers. Callers import ``Logger`` from
    # this module and annotate parameters with it.
    from loguru import Logger as Logger
else:
    Logger = type(default_logger)  # alias usable as a runtime annotation

__all__ = [
    "Logger",
    "configure",
    "emit",
    "logger",
    "now",
]


def now() -> str:
    """Return current UTC time as ISO-8601 string with millisecond precision."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def configure(
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

    return default_logger


def logger(step_name: str, run_id: str | None = None, **fields: Any) -> Logger:
    """Return a logger bound to the step name and optional run id.

    Assumes ``configure()`` has been called at process entry.

    Args:
        step_name: Stable identifier for the step (e.g. ``"fetch_jd"``).
        run_id: Optional run identifier.
        **fields: Additional context fields to bind.

    Returns:
        A ``Logger`` with bound context.
    """
    bound: Logger = default_logger.bind(step=step_name)
    if run_id is not None:
        bound = bound.bind(run_id=run_id)
    for key, value in fields.items():
        bound = bound.bind(**{key: value})
    return bound


def emit(event_name: str, run_id: str | None = None, **fields: Any) -> None:
    """Emit a structured event via the global logger.

    Args:
        event_name: Stable event identifier (e.g. ``"tailor.step.complete"``).
        run_id: Optional run identifier for correlation.
        **fields: Arbitrary structured fields to attach.
    """
    bound = logger(event_name, run_id=run_id)
    bound.info(event_name, **fields)
