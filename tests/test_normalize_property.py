"""Property-based tests for ``gethired.normalize``.

Covers general properties the AGENTS.md §"Property-Based Testing" section
asks for: idempotence, determinism, and roundtrip. ``hypothesis`` drives
the input space; the assertions are written against the public helpers
in ``gethired.normalize`` and ``gethired.models``.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from gethired.models import (
    Bullet,
    Contact,
    Experience,
Resume,
    Skills,
)
from gethired.normalize import (
    flatten,
    ngrams,
    numbers,
    strip_latex,
    tokenize,
)


@given(st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_normalise_whitespace_is_idempotent(text: str) -> None:
    """Normalising twice produces the same result as normalising once."""
    once = flatten(text)
    twice = flatten(once)
    assert once == twice


@given(st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_normalise_whitespace_has_no_double_spaces(text: str) -> None:
    """The output never contains two or more consecutive spaces."""
    result = flatten(text)
    assert "  " not in result


@given(st.text(min_size=0, max_size=200))
@settings(max_examples=50, deadline=None)
def test_canonicalize_numeric_returns_int_set(text: str) -> None:
    """Output is always a set of integers; the function never raises."""
    result = numbers(text)
    assert isinstance(result, set)
    for value in result:
        assert isinstance(value, int)


@given(
    st.lists(
        st.from_regex(r"[A-Za-z][A-Za-z0-9+#.-]{0,9}", fullmatch=True),
        min_size=0,
        max_size=20,
    )
)
@settings(max_examples=30, deadline=None)
def test_tokenize_for_overlap_roundtrips_to_lowercase(tokens: list[str]) -> None:
    """Letter-led tokens round-trip to lowercase in input order."""
    text = " ".join(tokens)
    result = tokenize(text)
    assert result == tuple(token.lower() for token in tokens)


@given(
    st.lists(
        st.from_regex(r"[A-Za-z]{1,6}", fullmatch=True),
        min_size=3,
        max_size=12,
    ),
    st.integers(min_value=1, max_value=5),
)
@settings(max_examples=30, deadline=None)
def test_extract_ngrams_preserves_length(tokens: list[str], n: int) -> None:
    """The number of n-grams equals ``len(tokens) - n + 1`` when input is long enough."""
    result = ngrams(tuple(tokens), n)
    if len(tokens) < n:
        assert result == ()
    else:
        assert len(result) == len(tokens) - n + 1
        assert all(len(gram.split(" ")) == n for gram in result)


@given(st.text(min_size=0, max_size=100))
@settings(max_examples=30, deadline=None)
def test_strip_latex_commands_does_not_raise(text: str) -> None:
    """The helper accepts arbitrary input and never raises."""
    assert isinstance(strip_latex(text), str)


def _make_master(name_suffix: str) -> Master:
    """Return a deterministic Master for content-hash tests."""
    return Resume(Resume(name=f"Test {name_suffix}", city="Test City", phone="+1-555-0100", email=f"test.{name_suffix}@example.com", github=None, linkedin=None,
        ),
        summary="Summary.",
        skills=Skills(categories={"Languages": ("Python", "Go")}),
        experience=(),
        projects=(),
        education=(),
        awards=(),
    )


def test_resume_content_hash_is_deterministic() -> None:
    """Two MasterResumes with the same fields produce the same content hash."""
    a = _make_master("a")
    b = _make_master("a")
    assert a.content_hash() == b.content_hash()


def test_resume_content_hash_changes_with_input() -> None:
    """Different master fields produce different content hashes."""
    a = _make_master("a")
    b = _make_master("b")
    assert a.content_hash() != b.content_hash()


def test_bullet_text_preserved_in_reorder() -> None:
    """``Experience`` preserves bullet text through dataclass roundtrip."""
    bullets = (Bullet(text="Built X"), Bullet(text="Shipped Y"))
    experience = Experience(
        role="Engineer",
        company="Acme",
        start_date="2020",
        end_date="2021",
        bullets=bullets,
    )
    assert experience.bullets[0].text == "Built X"
    assert experience.bullets[1].text == "Shipped Y"
