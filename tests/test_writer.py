"""Tests for the writer agent (LLM path with TestModel)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic_ai.models.test import TestModel

from gethired.description import Analysis
from gethired.exceptions import ConfigError
from gethired.profiler import build as build_profile
from gethired.tailor import Tailor
from gethired.writer import (
    RephraseBatch,
    Writer,
    WriterOutput,
    apply,
    enumerate_bullet_paths,
    lookup_bullet_text,
    rephrase_missing_bullets,
)


def _sample_analysis() -> Analysis:
    return Analysis(
        role="Senior ML Engineer",
        seniority="senior",
        must_have=("python", "kubernetes"),
        nice_to_have=("distributed",),
        keywords=("python", "kubernetes"),
        responsibilities=("design ML platforms",),
        company="Acme",
    )


def test_writer_with_test_model_produces_tailored_resume(resume) -> None:
    """The writer produces a TailoredResume with the master's contact preserved.

    Verifies the data path: contact information is preserved, skills are
    propagated from master, experiences are preserved, and the writer emits
    the expected Step kinds (TALOR, plus tool lookups for read-only tools).
    """
    analysis = _sample_analysis()
    voice = build_profile(resume)

    test_model = TestModel()
    writer = Writer(model="test", model_instance=test_model)
    tailored, jobs = writer.tailor(
        master=resume,
        analysis=analysis,
        voice=voice,
    )

    # Contact information must be preserved from the master
    assert tailored.name == resume.name
    assert tailored.email == resume.email
    assert tailored.phone == resume.phone
    # Summary is non-empty (the writer may rewrite it, but should not blank it)
    assert tailored.summary, "tailored.summary must be non-empty"
    # Skills must propagate from the master (no fabricated skills)
    assert tailored.skills.categories, "tailored.skills.categories must be non-empty"
    for category, items in tailored.skills.categories.items():
        assert category in resume.skills.categories, (
            f"fabricated category {category!r} not in master"
        )
        for item in items:
            assert item in resume.skills.categories[category], (
                f"fabricated skill {item!r} in category {category!r}"
            )
    # Experiences must be preserved (or explicitly dropped)
    assert tailored.experience, "tailored.experience must be non-empty"
    # Jobs must include the TAILOR step
    job_kinds = {j.type.value for j in jobs}
    assert "tailor" in job_kinds, f"missing TAILOR step in {job_kinds}"


def test_writer_with_model_instance_runs_without_model_env_var(
    monkeypatch: pytest.MonkeyPatch, resume
) -> None:
    """TestModel injected via model_instance allows offline runs.

    Verifies that the writer's output is a TailoredResume with the master's
    structure (contact, skills, experiences) preserved.
    """
    monkeypatch.delenv("MODEL", raising=False)
    analysis = _sample_analysis()
    voice = build_profile(resume)
    writer = Writer(model=None, model_instance=TestModel())
    tailored, jobs = writer.tailor(master=resume, analysis=analysis, voice=voice)
    # The master's contact must round-trip through the writer
    assert tailored.email == resume.email
    # The tailored resume should have at least one experience (the writer
    # preserves experiences unless explicitly dropped)
    assert len(tailored.experience) == len(resume.experience)


def test_writer_raises_configuration_error_when_model_missing(
    monkeypatch: pytest.MonkeyPatch, resume
) -> None:
    """Writer.tailor raises ConfigError when neither model nor model_instance.

    The error message must mention the env var name so users can fix it.
    """
    monkeypatch.delenv("MODEL", raising=False)
    analysis = _sample_analysis()
    voice = build_profile(resume)
    writer = Writer(model=None)
    with pytest.raises(ConfigError, match="MODEL is required"):
        writer.tailor(master=resume, analysis=analysis, voice=voice)


def test_tailor_raises_configuration_error_when_model_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tailor raises ConfigError at construction when MODEL is unset."""
    monkeypatch.delenv("MODEL", raising=False)
    with pytest.raises(ConfigError, match="MODEL is required"):
        Tailor(
            resume="sample.tex",
            job_description="https://example.com/jd",
            debug=False,
        )


def test_apply_writer_output_removes_dropped_entries(resume) -> None:
    """Dropped master paths are actually removed from the tailored resume."""
    dropped_experience = "experiences[0]"
    dropped_bullet = "experiences[1].bullets[1]"
    dropped_project = "projects[0]"
    dropped_project_bullet = "projects[1].bullets[0]"

    output = WriterOutput(
        summary="Summary",
        tailored_bullets={
            "experiences[1].bullets[0]": ["Rewritten first bullet"],
        },
        dropped=[
            dropped_experience,
            dropped_bullet,
            dropped_project,
            dropped_project_bullet,
        ],
        rationale="Drop irrelevant experience and project entries.",
    )

    tailored = apply(resume, output, _sample_analysis())

    assert len(tailored.experience) == len(resume.experience) - 1
    assert tailored.experience[0].role == resume.experience[1].role
    assert [b.text for b in tailored.experience[0].bullets] == [
        "Rewritten first bullet",
        *[b.text for b in resume.experience[1].bullets[2:]],
    ]

    assert len(tailored.projects) == len(resume.projects) - 1
    assert tailored.projects[0].name == resume.projects[1].name
    assert [b.text for b in tailored.projects[0].bullets] == [
        b.text for b in resume.projects[1].bullets[1:]
    ]

    dropped_ids = [drop.item_id for drop in tailored.dropped]
    assert dropped_ids == [
        dropped_experience,
        dropped_bullet,
        dropped_project,
        dropped_project_bullet,
    ]


# ---------------------------------------------------------------------------
# Every-bullet rewrite contract
# ---------------------------------------------------------------------------


def test_enumerate_bullet_paths_covers_every_experience_and_project_bullet(
    resume,
) -> None:
    """``enumerate_bullet_paths`` returns one path per experience/project bullet."""
    paths = enumerate_bullet_paths(resume)
    expected_count = sum(len(e.bullets) for e in resume.experience) + sum(
        len(p.bullets) for p in resume.projects
    )
    assert len(paths) == expected_count
    assert all(p.startswith("experiences[") or p.startswith("projects[") for p in paths)


def test_lookup_bullet_text_round_trips(resume) -> None:
    """``lookup_bullet_text`` returns the original bullet at any enumerated path."""
    paths = enumerate_bullet_paths(resume)
    for path in paths:
        text = lookup_bullet_text(resume, path)
        assert text is not None, f"missing bullet text at {path}"
        assert text.strip(), f"empty bullet text at {path}"


def test_rephrase_missing_bullets_test_model_returns_originals(resume) -> None:
    """Under TestModel, the fallback keeps the master text verbatim (test determinism)."""
    paths = enumerate_bullet_paths(resume)
    missing = [(p, lookup_bullet_text(resume, p) or "") for p in paths]
    out = rephrase_missing_bullets(
        missing,
        _sample_analysis(),
        model_instance=TestModel(),
        model_string=None,
    )
    assert set(out.keys()) == {p for p, _ in missing}
    for path, original in missing:
        assert out[path] == [original]


def test_rephrase_missing_bullets_empty_input_returns_empty() -> None:
    """No missing bullets → no work."""
    assert rephrase_missing_bullets(
        [], _sample_analysis(), model_instance=None, model_string=None
    ) == {}


def test_rephrase_missing_bullets_invokes_agent(monkeypatch, resume) -> None:
    """The rephrase batch agent is invoked with all missing paths in one call."""
    captured: dict[str, object] = {}

    real_agent = __import__("gethired.writer", fromlist=["Agent"]).Agent

    class _SpyAgent:
        def __init__(self, *args, **kwargs):
            captured["init_args"] = args
            captured["init_kwargs"] = kwargs

        def run_sync(self, payload):
            captured["payload"] = payload
            return SimpleNamespace(
                output=RephraseBatch(rephrases={"experiences[0].bullets[0]": "x"})
            )

    monkeypatch.setattr("gethired.writer.Agent", _SpyAgent)
    # Pass a non-None, non-TestModel sentinel that satisfies Agent's type hint.
    sentinel: object = object()
    out = rephrase_missing_bullets(
        [("experiences[0].bullets[0]", "Original text here.")],
        _sample_analysis(),
        model_instance=sentinel,  # type: ignore[arg-type]
        model_string=None,
    )
    assert "init_kwargs" in captured, "Agent was not constructed"
    assert "Original text here." in captured["payload"]
    assert "experiences[0].bullets[0]" in captured["payload"]
    assert out == {"experiences[0].bullets[0]": ["x"]}
    monkeypatch.setattr("gethired.writer.Agent", real_agent)


def test_writer_rephrases_every_bullet_in_production(monkeypatch, resume) -> None:
    """Production writer run with a TestModel that omits some paths triggers the fallback."""

    # TestModel returns `tailored_bullets={}` (default TestModel behaviour) for
    # the main WriterOutput call. The writer's fallback must then rephrase
    # every missing bullet via its own TestModel-backed batch agent.
    analysis = _sample_analysis()
    voice = build_profile(resume)
    writer = Writer(model="test", model_instance=TestModel())
    tailored, _ = writer.tailor(master=resume, analysis=analysis, voice=voice)

    # Every original bullet must appear, rephrased (TestModel returns the
    # original verbatim under the fallback path).
    expected_paths = enumerate_bullet_paths(resume)
    rewritten_paths = {c.tailored_path for c in tailored.grounding}
    assert expected_paths, "master has no bullets"
    for path in expected_paths:
        original = lookup_bullet_text(resume, path) or ""
        rewritten = next(
            (
                c
                for c in tailored.grounding
                if c.tailored_path == path
            ),
            None,
        )
        assert rewritten is not None, f"no rewrite record for {path}"
        # Find the matching bullet in the tailored output.
        if path.startswith("experiences["):
            tail = path[len("experiences[") :]
            idx_str, rest = tail.split("].bullets[", 1)
            idx, b_idx = int(idx_str), int(rest.rstrip("]"))
            actual = tailored.experience[idx].bullets[b_idx].text
        else:
            tail = path[len("projects[") :]
            idx_str, rest = tail.split("].bullets[", 1)
            idx, b_idx = int(idx_str), int(rest.rstrip("]"))
            actual = tailored.projects[idx].bullets[b_idx].text
        assert actual == original, (
            f"bullet at {path} was not rephrased by the fallback; got {actual!r}"
        )
    assert rewritten_paths == set(expected_paths)
