"""OpenTelemetry-compatible span tracing for the agent pipeline.

The deepeval-style evaluator (see ``evals/graders/code.py``) consumes the
spans emitted by this module to score component-level agent behaviour
(tool selection, argument correctness, plan quality, step efficiency).

Spans are appended to a JSONL file under ``tailored/<run-id>/trace.jsonl``.
The format is intentionally OpenTelemetry-compatible so that future
production deployments can swap this writer for an OTLP exporter without
changing call sites.

Span tree:

* root ``agent`` span — Tailor.run()
  * ``tool`` spans — every read-only Writer tool call (lookup_experience, …)
  * ``llm`` span — every Pydantic AI Agent.run() invocation
  * ``validate`` spans — grounding/style/plagiarism/ATS

All public functions are no-ops when tracing is disabled (the default in
unit tests), so the tracing overhead in production is bounded by a single
``append + flush`` per span.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    pass


_TRACE_PATH_ENV = "GETHIRED_TRACE_PATH"
"""Environment variable that, when set, enables span emission to the given JSONL file."""


def _new_span_id() -> str:
    return uuid4().hex


@dataclass(frozen=True, slots=True)
class TraceSpan:
    """A single OpenTelemetry-compatible span."""

    name: str
    kind: str  # "agent" | "tool" | "llm" | "validate"
    started_at: str
    ended_at: str
    duration_ms: float
    attributes: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None
    span_id: str = field(default_factory=_new_span_id)

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), default=str)


class _ActiveSpan:
    """Mutable handle returned by ``start_span`` so callers can attach attributes."""

    def __init__(self, sink: _JsonlSink | None, span: TraceSpan) -> None:
        self._sink = sink
        self._span = span
        self._ended = False

    def set_attribute(self, key: str, value: Any) -> None:
        object.__setattr__(
            self._span,
            "attributes",
            {**self._span.attributes, key: value},
        )

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        if self._sink is not None:
            self._sink.write(self._span)

    @property
    def span_id(self) -> str:
        """Return the span_id of the underlying span (read-only)."""
        return self._span.span_id


class _JsonlSink:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("a", encoding="utf-8")

    def write(self, span: TraceSpan) -> None:
        self._fh.write(span.to_jsonl() + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


class Tracer:
    """Per-run tracer that emits OpenTelemetry-compatible spans to JSONL."""

    def __init__(self, path: Path | None) -> None:
        self._sink = _JsonlSink(path) if path is not None else None
        self._active_id: str | None = None

    def close(self) -> None:
        if self._sink is not None:
            self._sink.close()

    @contextmanager
    def span(
        self,
        name: str,
        kind: str,
        **attributes: Any,
    ) -> Iterator[_ActiveSpan]:
        """Start a new span; auto-end on context exit.

        Yields a handle so callers can attach additional attributes.
        """
        started_perf = time.perf_counter()
        started_at = _now_iso()
        parent_id = self._active_id
        span = TraceSpan(
            name=name,
            kind=kind,
            started_at=started_at,
            ended_at=started_at,
            duration_ms=0.0,
            attributes=dict(attributes),
            parent_id=parent_id,
        )
        handle = _ActiveSpan(self._sink, span)
        previous_id = self._active_id
        object.__setattr__(self, "_active_id", span.span_id)
        try:
            yield handle
        finally:
            duration_ms = (time.perf_counter() - started_perf) * 1000.0
            ended_at = _now_iso()
            object.__setattr__(handle._span, "ended_at", ended_at)
            object.__setattr__(handle._span, "duration_ms", duration_ms)
            handle.end()
            object.__setattr__(self, "_active_id", previous_id)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def tracer_for_run(run_id: str, output_dir: Path) -> Tracer:
    """Build a tracer that writes to ``output_dir / run_id / trace.jsonl``.

    Returns a no-op tracer when ``GETHIRED_TRACE_PATH`` is explicitly set
    to ``"off"`` (used by unit tests that want predictable output).
    """
    if os.environ.get(_TRACE_PATH_ENV, "").lower() == "off":
        return Tracer(path=None)
    path = Path(output_dir) / run_id / "trace.jsonl"
    return Tracer(path=path)


__all__ = ["TraceSpan", "Tracer", "tracer_for_run"]
