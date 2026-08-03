"""Tests for the streaming event emitter."""

from __future__ import annotations

from gethired.streaming import ProgressEvent, reporter


def test_progress_reporter_invokes_callback() -> None:
    """reporter yields the callback so the caller can invoke it."""
    received: list[ProgressEvent] = []

    def callback(event: ProgressEvent) -> None:
        received.append(event)

    with reporter(callback) as emit:
        emit(ProgressEvent(step="writer", message="start"))
        emit(ProgressEvent(step="writer", message="done", job_id="abc"))

    assert len(received) == 2
    assert received[0].step == "writer"
    assert received[1].job_id == "abc"


def test_progress_reporter_without_callback_runs() -> None:
    """When no callback is supplied, emits are silently dropped."""
    with reporter() as emit:
        emit(ProgressEvent(step="writer", message="noop"))
