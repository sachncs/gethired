"""Tests for the job description fetcher's retry policy."""

from __future__ import annotations

import httpx
import pytest

from gethired.exceptions import AntiBotError, FetchError
from gethired.fetcher import Fetcher


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

    retriever = Fetcher(cache_dir=tmp_path, max_attempts=3)
    with pytest.raises(FetchError):
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

    retriever = Fetcher(cache_dir=tmp_path, max_attempts=3)
    job_description = retriever.retrieve("https://example.com/jd")

    assert attempts == 2
    assert sleep_calls == [1]
    assert job_description.url == "https://example.com/jd"


def test_fetch_raises_antibot_on_cloudflare_challenge(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """HTTP 403 with a Cloudflare header marker becomes ``AntiBotError``."""

    def cloudflare_block(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"server": "cloudflare", "cf-ray": "abc123"},
            text="<html>cf-mitigated</html>",
            request=request,
        )

    transport = httpx.MockTransport(cloudflare_block)
    real_client_class = httpx.Client
    monkeypatch.setattr(
        "gethired.fetcher.httpx.Client",
        lambda **_unused: real_client_class(transport=transport),
    )
    retriever = Fetcher(cache_dir=tmp_path, max_attempts=3)
    with pytest.raises(AntiBotError) as excinfo:
        retriever.retrieve("https://example.com/jd")
    assert excinfo.value.status == 403
    assert any("cloudflare" in m for m in excinfo.value.markers)


def test_fetch_raises_antibot_on_aws_waf_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """HTTP 403 with AWS WAF header markers becomes ``AntiBotError``."""

    def waf_block(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"x-amzn-waf-action": "challenge"},
            text="blocked",
            request=request,
        )

    transport = httpx.MockTransport(waf_block)
    real_client_class = httpx.Client
    monkeypatch.setattr(
        "gethired.fetcher.httpx.Client",
        lambda **_unused: real_client_class(transport=transport),
    )
    retriever = Fetcher(cache_dir=tmp_path, max_attempts=3)
    with pytest.raises(AntiBotError) as excinfo:
        retriever.retrieve("https://example.com/jd")
    assert excinfo.value.status == 403
    assert any("amzn" in m or "amz" in m for m in excinfo.value.markers)


def test_fetch_does_not_classify_plain_403_as_antibot(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """HTTP 403 without WAF markers stays a regular ``FetchError`` after retries."""

    def plain_403(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden", request=request)

    transport = httpx.MockTransport(plain_403)
    real_client_class = httpx.Client
    monkeypatch.setattr(
        "gethired.fetcher.httpx.Client",
        lambda **_unused: real_client_class(transport=transport),
    )
    retriever = Fetcher(cache_dir=tmp_path, max_attempts=2)
    with pytest.raises(FetchError):
        retriever.retrieve("https://example.com/jd")
