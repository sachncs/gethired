"""HTTP fetcher for job description URLs.

Sync ``httpx.Client`` (per plan revision B5). Caches by URL hash with
content-hash invalidation (per plan revision B9). Retries with exponential
backoff on transient failures (per HP7).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
import trafilatura

from gethired.constants import CACHE_MAX_AGE_DAYS, JD_FETCH_MAX_ATTEMPTS
from gethired.exceptions import JobDescriptionRetrievalError
from gethired.models import JobDescription
from gethired.observability import step_logger

USER_AGENT: Final[str] = (
    "Mozilla/5.0 (compatible; gethired/0.1; +https://github.com/gethired)"
)
FETCH_TIMEOUT_SECONDS: Final[float] = 30.0


@dataclass(frozen=True, slots=True)
class CacheEntry:
    url: str
    url_hash: str
    content_hash: str
    fetched_at: str
    raw_html: str


class JobDescriptionRetriever:
    """Sync fetcher with on-disk cache and retry policy."""

    def __init__(self, cache_dir: Path, max_attempts: int = JD_FETCH_MAX_ATTEMPTS) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._max_attempts = max_attempts

    def retrieve(self, url: str) -> JobDescription:
        """Retrieve and parse a job description URL into a ``JobDescription``.

        Args:
            url: The job description URL.

        Returns:
            A populated ``JobDescription``.

        Raises:
            JobDescriptionRetrievalError: If retrieval fails after all retries.
        """
        logger = step_logger("fetch_jd")
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        cached = self.__load_cache(url_hash)
        if cached is not None and self.__is_cache_fresh(cached):
            logger.info("fetch cache hit", url=url, url_hash=url_hash)
            return self.__parse(cached.raw_html, url, cached.content_hash)

        raw_html = self.__fetch_with_retry(url, logger)
        content_hash = hashlib.sha256(raw_html.encode()).hexdigest()
        self.__save_cache(
            CacheEntry(
                url=url,
                url_hash=url_hash,
                content_hash=content_hash,
                fetched_at=datetime.now(UTC).isoformat(),
                raw_html=raw_html,
            )
        )
        return self.__parse(raw_html, url, content_hash)

    def __fetch_with_retry(self, url: str, logger) -> str:
        last_exc: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                with httpx.Client(
                    headers={"User-Agent": USER_AGENT},
                    timeout=FETCH_TIMEOUT_SECONDS,
                    follow_redirects=True,
                ) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    return response.text
            except (httpx.HTTPError, httpx.StreamError) as exc:
                last_exc = exc
                backoff_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "fetch attempt failed",
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                    backoff_seconds=backoff_seconds,
                )
        raise JobDescriptionRetrievalError(
            f"Failed to fetch {url} after {self._max_attempts} attempts: {last_exc}"
        )

    def __cache_path(self, url_hash: str) -> Path:
        return self._cache_dir / f"{url_hash}.json"

    def __load_cache(self, url_hash: str) -> CacheEntry | None:
        path = self.__cache_path(url_hash)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return CacheEntry(
                url=data["url"],
                url_hash=data["url_hash"],
                content_hash=data["content_hash"],
                fetched_at=data["fetched_at"],
                raw_html=data["raw_html"],
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def __save_cache(self, entry: CacheEntry) -> None:
        path = self.__cache_path(entry.url_hash)
        path.write_text(json.dumps(entry.__dict__, indent=2))

    def __is_cache_fresh(self, entry: CacheEntry) -> bool:
        try:
            fetched_at = datetime.fromisoformat(entry.fetched_at)
        except ValueError:
            return False
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        age = datetime.now(UTC) - fetched_at
        return age <= timedelta(days=CACHE_MAX_AGE_DAYS)

    def __parse(self, raw_html: str, url: str, content_hash: str) -> JobDescription:
        jsonld = extract_jsonld(raw_html)
        if jsonld is not None:
            return build_from_jsonld(jsonld, url, content_hash)

        text = extract_text_trafilatura(raw_html)
        if not text:
            raise JobDescriptionRetrievalError(f"No text extracted from {url}")
        return build_from_text(text, url, content_hash)


def extract_jsonld(html: str) -> dict | None:
    pattern = re.compile(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    return item
    return None


def extract_text_trafilatura(html: str) -> str:
    extracted = trafilatura.extract(html)
    return extracted or ""


def build_from_jsonld(data: dict, url: str, content_hash: str) -> JobDescription:
    title = str(data.get("title", ""))
    company = ""
    hiring_org = data.get("hiringOrganization") or data.get("organization")
    if isinstance(hiring_org, dict):
        company = str(hiring_org.get("name", ""))
    description = str(data.get("description", ""))
    full_text = f"{title}\n\n{description}".strip()
    keywords = extract_keywords(full_text)
    must_have, nice_to_have = categorize_keywords(data, full_text)
    return JobDescription(
        url=url,
        title=title,
        company=company,
        full_text=full_text,
        keywords=keywords,
        must_have_keywords=must_have,
        nice_to_have_keywords=nice_to_have,
        content_hash=content_hash,
    )


def build_from_text(text: str, url: str, content_hash: str) -> JobDescription:
    keywords = extract_keywords(text)
    return JobDescription(
        url=url,
        title="",
        company="",
        full_text=text,
        keywords=keywords,
        must_have_keywords=(),
        nice_to_have_keywords=keywords,
        content_hash=content_hash,
    )


KEYWORD_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "have", "in", "is", "it", "its", "of", "on", "or", "our",
        "that", "the", "their", "they", "this", "to", "was", "were", "will",
        "with", "you", "your", "we", "us", "i", "me", "my", "he", "she",
        "his", "her", "them", "these", "those", "any", "all", "can", "may",
        "should", "would", "could", "do", "does", "did", "been", "being",
        "also", "more", "most", "such", "than", "then", "into", "about",
        "over", "under", "between", "through", "during", "before", "after",
    }
)
KEYWORD_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]{1,}")


def extract_keywords(text: str) -> tuple[str, ...]:
    counter: Counter[str] = Counter()
    for match in KEYWORD_RE.finditer(text):
        token = match.group(0).lower()
        if token in KEYWORD_STOPWORDS:
            continue
        if len(token) < 3:
            continue
        counter[token] += 1
    return tuple(word for word, _ in counter.most_common(40))


def categorize_keywords(data: dict, text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Best-effort tier classification: required skills vs nice-to-have."""
    must_have: set[str] = set()
    nice_to_have: set[str] = set()
    skills_section = data.get("skills")
    if isinstance(skills_section, str):
        for token in KEYWORD_RE.finditer(skills_section):
            nice_to_have.add(token.group(0).lower())
    elif isinstance(skills_section, list):
        for skill in skills_section:
            if isinstance(skill, str):
                nice_to_have.add(skill.lower())
    requirements = data.get("experienceRequirements") or data.get("qualifications")
    if isinstance(requirements, str):
        for token in KEYWORD_RE.finditer(requirements):
            must_have.add(token.group(0).lower())
    if not must_have:
        for fallback_token in extract_keywords(text)[:15]:
            must_have.add(fallback_token)
    return tuple(must_have), tuple(nice_to_have)


__all__ = ["CacheEntry", "JobDescriptionRetriever"]
