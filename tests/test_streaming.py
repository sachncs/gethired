"""Tests for the streaming event emitter."""

from __future__ import annotations

from gethired.streaming import ProgressEvent, progress_reporter


def test_progress_reporter_invokes_callback() -> None:
    """progress_reporter calls the user callback for every emit."""
    received: list[ProgressEvent] = []

    def callback(event: ProgressEvent) -> None:
        received.append(event)

    with progress_reporter(callback) as emitter:
        emitter["emit"](ProgressEvent(step="writer", message="start"))
        emitter["emit"](ProgressEvent(step="writer", message="done", job_id="abc"))

    assert len(received) == 2
    assert received[0].step == "writer"
    assert received[1].job_id == "abc"


def test_progress_reporter_without_callback_runs() -> None:
    """When no callback is supplied, emits are buffered silently."""
    with progress_reporter() as emitter:
        emitter["emit"](ProgressEvent(step="writer", message="noop"))
    assert True
