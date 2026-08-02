"""Streaming event emitter for live progress reporting.

Wraps a pipeline run in a context manager that exposes an ``emit`` callable.
Consumers (CLI, notebook, web UI) supply their own callback to receive
``ProgressEvent`` instances as the writer / critic / renderer produce them.
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
def progress_reporter(
    callback: ProgressCallback | None = None,
) -> Iterator[ProgressCallback]:
    """Context manager that yields the emit callable.

    Args:
        callback: Optional callable invoked on each event. When ``None``,
            events are silently dropped.

    Yields:
        A ``ProgressCallback`` accepting ``ProgressEvent`` instances.
    """
    if callback is None:

        def emit(_event: ProgressEvent) -> None:
            return None

        yield emit
        return

    yield callback


__all__ = ["ProgressCallback", "ProgressEvent", "progress_reporter"]
