"""Tests for the data models."""

from __future__ import annotations

import dataclasses
from dataclasses import fields

import pytest

from gethired.models import (
    ADVISORY_GATES,
    HARD_GATES,
    AtsGate,
    Award,
    Bullet,
    Citation,
    Contact,
    Education,
    Experience,
    GateTier,
    Job,
    JobData,
    KeywordTier,
Resume,
    Outcome,
    Project,
    Reason,
    Run,
    RunResult,
    RunView,
    Skills,
    Source,
    Step,
    StepEnv,
    StepKind,
    StepMeta,
    StepStatus,
    Tailored,
    Voice,
    job,
    Resume,
)


def test_all_models_are_frozen() -> None:
    """Every model should be immutable (frozen=True) and constructible.

    Each model is built from minimal placeholder values for required fields.
    The test then verifies (1) the model has frozen semantics and (2) every
    declared field is accessible on the resulting instance.
    """
    contact = Resume(name="x", city="x", phone="x", email="x", github=None, linkedin=None, summary="", skills=Skills(categories={}), experience=(), projects=(), education=(), awards=())
    placeholder_objs: dict[type, object] = {
        Contact: contact,
        Bullet: Bullet(text="x"),
        Experience: Experience(role="x", company="x", start_date="x", end_date="x", bullets=()),
        Project: Project(name="x", url="", bullets=()),
        Education: Education(
            institution="x", location="x", degree="x", major="x", graduation="x", gpa=None
        ),
        Award: Award(title="x", organization="x", date="x", description="x"),
        Skills: Skills(categories={}),
        Resume: Resume(
            name=contact.name,email=contact.email,city=contact.city,phone=contact.phone,github=contact.github,linkedin=contact.linkedin,
            summary="x",
            skills=Skills(categories={}),
            experience=(),
            projects=(),
            education=(),
            awards=()),
        Voice: Voice(
            avg_bullet_length=0.0,
            bullet_length_stddev=0.0,
            opening_verbs=(),
            punctuation_density={},
            sentence_count_per_bullet=(0, 0)),
        Reason: Reason(item_id="x", reason="x"),
        Citation: Citation(path="x", source_path="x", span="x", step_id="x"),
        Step: Step(
            id="x",
            type=StepKind.FETCH,
            started_at="x",
            completed_at="x",
            status=StepStatus.SUCCESS,
            inputs=(),
            outputs=(),
            rationale="x",
            model="x",
            tool_name=None,
            metadata=StepMeta()),
        JobData: JobData(
            id="x",
            type=StepKind.FETCH,
            started_at="x",
            completed_at="x",
            status=StepStatus.SUCCESS,
            inputs=(),
            outputs=(),
            rationale="x",
            model="x",
            tool_name=None,
            metadata={"url": None}),
        StepMeta: StepMeta(url="x"),
        Source: Source(source_path="x", span="x", resume_hash="x"),
        # WebSearch was deleted; old test removed
        Run: Run(
            id="x",
            started_at="x",
            resume_hash="x",
            jd_hash="x",
            model="x",
            draft_model=None),
        RunView: RunView(
            id="x",
            started_at="x",
            resume_hash="x",
            jd_hash="x",
            model="x",
            draft_model=None),
        RunResult: RunResult(
            run=Run("x", "x", "x", "x", "x", None),
            completed_at="x",
            duration_seconds=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            retry_attempts=0,
            final_outcome=Outcome.SUCCESS,
            jobs=()),
        Tailored: Tailored(
            name=contact.name,email=contact.email,city=contact.city,phone=contact.phone,github=contact.github,linkedin=contact.linkedin,
            summary="x",
            skills=Skills(categories={}),
            experience=(),
            projects=(),
            education=(),
            awards=(),
            dropped=(),
            rationale="x",
            grounding=(),
            jobs=()),
        Job: Job(
            url="x",
            title="x",
            company="x",
            full_text="x",
            keywords=(),
            must_have_keywords=(),
            nice_to_have_keywords=(),
            content_hash="x"),
    }
    for model_type, obj in placeholder_objs.items():
        # 1. frozen=True semantics: setattr on any declared field must raise.
        declared_fields = [f.name for f in fields(model_type)]
        assert declared_fields, f"{model_type.__name__} has no declared fields"
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            setattr(obj, declared_fields[0], "mutated")
        # 2. Every declared dataclass field is reachable on the instance.
        for f in fields(model_type):
            assert hasattr(obj, f.name), f"{model_type.__name__}.{f.name} missing"


def test_job_factory_assigns_uuid() -> None:
    """The ``job`` factory must assign a UUID and current timestamp."""
    j = job(StepKind.FETCH, outputs=("jds[0]"), rationale="fetched")
    assert isinstance(j.id, str)
    assert len(j.id) == 36  # standard UUID4 format with hyphens
    assert j.type == StepKind.FETCH
    assert j.outputs == ("jds[0]")
    assert j.rationale == "fetched"
    assert j.metadata == StepMeta()


def test_job_description_round_trips() -> None:
    """``Job.description()`` should yield a serializable Job."""
    j = job(
        StepKind.FETCH,
        outputs=("jds[0]"),
        rationale="fetched",
        envelope=StepEnv(metadata=StepMeta(url="https://example.com")))
    desc = j.description()
    assert isinstance(desc, JobData)
    assert desc.id == j.id
    assert desc.type == StepKind.FETCH
    assert desc.metadata == {"url": "https://example.com"}
    as_dict = desc.to_dict()
    assert as_dict["id"] == j.id
    assert as_dict["type"] == "fetch"
    assert as_dict["status"] == "success"


def test_run_id_is_uuid_format() -> None:
    """``Run.id`` must be UUID-shaped (per user directive)."""
    run = Run(
        id="0192c8b3-5e0e-7def-9012-abcdef012345",
        started_at="2026-08-02T00:00:00.000Z",
        resume_hash="x",
        jd_hash="y",
        model="anthropic:claude-sonnet-4-5",
        draft_model=None)
    assert len(run.id.split("-")) == 5  # 5 segments


def test_run_result_websearch_calls_derived() -> None:
    """``RunResult.websearch_calls`` is a derived property, not stored."""
    fetch_job = job(StepKind.FETCH)
    web_job = job(
        StepKind.WEBSEARCH,
        envelope=StepEnv(metadata=StepMeta(query="q")))
    run_result = RunResult(
        run=Run("x", "x", "x", "x", "x", None),
        completed_at="x",
        duration_seconds=0.0,
        total_input_tokens=0,
        total_output_tokens=0,
        retry_attempts=0,
        final_outcome=Outcome.SUCCESS,
        jobs=(fetch_job, web_job))
    assert run_result.websearch_calls == (web_job)


def test_final_outcome_enum_values() -> None:
    assert Outcome.SUCCESS.value == "success"
    assert Outcome.ATS_HARD_FAIL.value == "ats_hard_fail"


def test_ats_gate_has_twelve_values() -> None:
    """There are 12 ATS gates: 9 hard-blocking and 3 advisory."""
    assert len(AtsGate) == 12


def test_ats_gate_tiers_partition_members() -> None:
    """Hard and advisory tiers are mutually exclusive and cover every gate."""
    hard = frozenset(gate for gate in AtsGate if gate.tier is GateTier.HARD)
    advisory = frozenset(gate for gate in AtsGate if gate.tier is GateTier.ADVISORY)
    assert len(hard) == 9
    assert len(advisory) == 3
    assert hard | advisory == frozenset(AtsGate)
    assert hard & advisory == frozenset()
    assert hard == HARD_GATES
    assert advisory == ADVISORY_GATES


def test_keyword_tier_enum_values() -> None:
    assert KeywordTier.MUST_HAVE.value == "must_have"
    assert KeywordTier.NICE_TO_HAVE.value == "nice_to_have"
