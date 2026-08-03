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
  * ``tool`` spans — every read-only Writer tool call (experience, …)
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
from typing import Any
from uuid import uuid4

TRACE_VAR: str = "GETHIRED_TRACE_PATH"
"""Environment variable that, when set, enables span emission to the given JSONL file."""


def span_id() -> str:
    """Return a 32-char hex UUID4 suitable for an OpenTelemetry span_id."""
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
    span_id: str = field(default_factory=span_id)

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), default=str)


class ActiveSpan:
    """Mutable handle returned by ``start_span`` so callers can attach attributes."""

    def __init__(self, sink: JsonlSink | None, span: TraceSpan) -> None:
        self.sink = sink
        self.span = span
        self.ended = False

    def set_attribute(self, key: str, value: Any) -> None:
        object.__setattr__(
            self.span,
            "attributes",
            {**self.span.attributes, key: value},
        )

    def end(self) -> None:
        if self.ended:
            return
        self.ended = True
        if self.sink is not None:
            self.sink.write(self.span)

    @property
    def span_id(self) -> str:
        """Return the span_id of the underlying span (read-only)."""
        return self.span.span_id


class JsonlSink:
    """Append-only JSONL writer for trace spans."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file_handle = path.open("a", encoding="utf-8")

    def write(self, span: TraceSpan) -> None:
        self.file_handle.write(span.to_jsonl() + "\n")
        self.file_handle.flush()

    def close(self) -> None:
        self.file_handle.close()


class Tracer:
    """Per-run tracer that emits OpenTelemetry-compatible spans to JSONL."""

    def __init__(self, path: Path | None) -> None:
        self.sink = JsonlSink(path) if path is not None else None
        self.active_id: str | None = None

    def close(self) -> None:
        if self.sink is not None:
            self.sink.close()

    @contextmanager
    def span(
        self,
        name: str,
        kind: str,
        **attributes: Any,
    ) -> Iterator[ActiveSpan]:
        """Start a new span; auto-end on context exit.

        Yields a handle so callers can attach additional attributes.
        """
        started_perf = time.perf_counter()
        started_at = now()
        parent_id = self.active_id
        span = TraceSpan(
            name=name,
            kind=kind,
            started_at=started_at,
            ended_at=started_at,
            duration_ms=0.0,
            attributes=dict(attributes),
            parent_id=parent_id,
        )
        handle = ActiveSpan(self.sink, span)
        previous_id = self.active_id
        object.__setattr__(self, "active_id", span.span_id)
        try:
            yield handle
        finally:
            duration_ms = (time.perf_counter() - started_perf) * 1000.0
            ended_at = now()
            object.__setattr__(handle.span, "ended_at", ended_at)
            object.__setattr__(handle.span, "duration_ms", duration_ms)
            handle.end()
            object.__setattr__(self, "active_id", previous_id)


def now() -> str:
    """Return current UTC time as ISO-8601 string with millisecond precision."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def tracer(run_id: str, output_dir: Path) -> Tracer:
    """Build a tracer that writes to ``output_dir / run_id / trace.jsonl``.

    Returns a no-op tracer when ``GETHIRED_TRACE_PATH`` is explicitly set
    to ``"off"`` (used by unit tests that want predictable output).
    """
    if os.environ.get(TRACE_VAR, "").lower() == "off":
        return Tracer(path=None)
    path = Path(output_dir) / run_id / "trace.jsonl"
    return Tracer(path=path)


__all__ = [
    "ActiveSpan",
    "JsonlSink",
    "TraceSpan",
    "Tracer",
    "now",
    "span_id",
    "tracer",
]
