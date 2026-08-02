"""Streaming event emitter for live progress reporting.

Wraps a pipeline run in a context manager that yields ``ProgressEvent``
instances as the writer / critic / renderer produce them. The default
callback is a no-op; consumers (CLI, notebook, web UI) supply their own.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

ProgressCallback = Callable[["ProgressEvent"], None]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """A single event emitted during a pipeline run."""

    step: str
    message: str
    job_id: str | None = None
    job_type: str | None = None


@contextmanager
def progress_reporter(callback: ProgressCallback | None = None) -> Iterator[ProgressEvent]:
    """Context manager that yields ``ProgressEvent`` instances.

    Args:
        callback: Optional callable invoked on each event. When None, events
            are buffered but not delivered externally.

    Yields:
        ``ProgressEvent`` instances from ``emit()``.
    """
    pending: list[ProgressEvent] = []

    def emit(event: ProgressEvent) -> None:
        pending.append(event)
        if callback is not None:
            callback(event)

    sentinel = {"emit": emit}
    yield sentinel  # type: ignore[misc] -- sentinel container for shared emit
    del pending


__all__ = ["ProgressCallback", "ProgressEvent", "progress_reporter"]