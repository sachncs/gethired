"""Tests for the OpenTelemetry-compatible tracing module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from gethired.tracing import (
    Tracer,
    TraceSpan,
    span_id,
    tracer,
)


def test_span_id_is_hex_uuid4() -> None:
    """Span IDs are 32-char hex (UUID4 without dashes)."""
    sid = span_id()
    assert len(sid) == 32
    int(sid, 16)


def test_tracer_writes_jsonl_with_span_kind_and_attributes(tmp_path: Path) -> None:
    """Each span end writes one JSONL line with kind, attributes, duration."""
    path = tmp_path / "trace.jsonl"
    tracer = Tracer(path=path)
    try:
        with tracer.span("llm_call", "llm", model="test-model") as span:
            span.set_attribute("input_tokens", 42)
        lines = path.read_text().splitlines()
    finally:
        tracer.close()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["name"] == "llm_call"
    assert record["kind"] == "llm"
    assert record["attributes"]["model"] == "test-model"
    assert record["attributes"]["input_tokens"] == 42
    assert record["duration_ms"] >= 0
    assert record["span_id"] != record["parent_id"]


def test_tracer_nested_spans_track_parent_id(tmp_path: Path) -> None:
    """A child span carries the parent's span_id."""
    path = tmp_path / "trace.jsonl"
    tracer = Tracer(path=path)
    try:
        with tracer.span("root", "agent") as outer:
            outer_id = outer.span_id
            with tracer.span("child", "tool"):
                pass
    finally:
        tracer.close()
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 2
    child_record = next(r for r in records if r["name"] == "child")
    assert child_record["parent_id"] == outer_id


def test_tracer_noop_when_path_is_none(tmp_path: Path) -> None:
    """Tracer(path=None) accepts spans but writes nothing."""
    tracer: Tracer = Tracer(path=None)
    with tracer.span("agent", "agent"):
        pass
    assert list(tmp_path.iterdir()) == []


def test_tracer_for_run_writes_under_run_directory() -> None:
    """tracer creates tailored/<run-id>/trace.jsonl."""
    with tempfile.TemporaryDirectory() as d:
        output_dir = Path(d)
        t = tracer("abc123", output_dir)
        try:
            with t.span("init", "agent", run_id="abc123"):
                pass
        finally:
            t.close()
        trace_file = output_dir / "abc123" / "trace.jsonl"
        assert trace_file.exists()
        assert "init" in trace_file.read_text()


def test_trace_span_to_jsonl_is_single_line() -> None:
    """to_jsonl produces one line with no embedded newlines (JSONL-safe)."""
    span = TraceSpan(
        name="x",
        kind="tool",
        started_at="2026-01-01T00:00:00Z",
        ended_at="2026-01-01T00:00:00Z",
        duration_ms=1.0,
        attributes={"k": "v"},
    )
    line = span.to_jsonl()
    assert "\n" not in line
    json.loads(line)
