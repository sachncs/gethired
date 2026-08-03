"""Tests for the job description fetcher's retry policy."""

from __future__ import annotations

import httpx
import pytest

from gethired.exceptions import JobDescriptionRetrievalError
from gethired.fetcher import JobDescriptionRetriever


def test_fetch_failure_retries_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Each retry attempt sleeps with exponential backoff before re-fetching."""
    sleep_calls: list[int] = []

    def fail_all(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    real_client_class = httpx.Client
    transport = httpx.MockTransport(fail_all)
    monkeypatch.setattr(
        "gethired.fetcher.httpx.Client",
        lambda **_unused: real_client_class(transport=transport),
    )
    monkeypatch.setattr("gethired.fetcher.time.sleep", sleep_calls.append)

    retriever = JobDescriptionRetriever(cache_dir=tmp_path, max_attempts=3)
    with pytest.raises(JobDescriptionRetrievalError):
        retriever.retrieve("https://example.com/jd")

    assert sleep_calls == [1, 2]


def test_fetch_recovers_after_first_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A transient failure is retried and the run succeeds."""
    sleep_calls: list[int] = []
    attempts = 0

    def fail_once(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, request=request)
        return httpx.Response(
            200,
            text="<html><body><h1>Job Title</h1></body></html>",
            request=request,
        )

    transport = httpx.MockTransport(fail_once)
    real_client_class = httpx.Client
    monkeypatch.setattr(
        "gethired.fetcher.httpx.Client",
        lambda **_unused: real_client_class(transport=transport),
    )
    monkeypatch.setattr("gethired.fetcher.time.sleep", sleep_calls.append)

    retriever = JobDescriptionRetriever(cache_dir=tmp_path, max_attempts=3)
    job_description = retriever.retrieve("https://example.com/jd")

    assert attempts == 2
    assert sleep_calls == [1]
    assert job_description.url == "https://example.com/jd"
