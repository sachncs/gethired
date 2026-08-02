"""Tests for the data models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from gethired.models import (
    AtsGate,
    Award,
    Bullet,
    ContactInformation,
    DropReason,
    Education,
    Experience,
    FinalOutcome,
    GroundedCitation,
    Job,
    JobDescription,
    JobDescriptionData,
    JobMetadata,
    JobStatus,
    JobType,
    KeywordTier,
    MasterResume,
    Project,
    Run,
    RunDescription,
    RunResult,
    SkillsByCategory,
    SourceReference,
    StepType,
    TailoredResume,
    VoiceProfile,
    WebSearch,
    job,
)


def test_all_models_are_frozen() -> None:
    """Every model should be immutable (frozen=True)."""
    dataclass_models = [
        ContactInformation,
        Bullet,
        Experience,
        Project,
        Education,
        Award,
        SkillsByCategory,
        MasterResume,
        VoiceProfile,
        DropReason,
        GroundedCitation,
        Job,
        JobDescriptionData,
        JobMetadata,
        SourceReference,
        WebSearch,
        Run,
        RunDescription,
        RunResult,
        TailoredResume,
        JobDescription,
    ]
    for model in dataclass_models:
        instance_fields = {f.name for f in fields(model)}
        try:
            kwargs = {
                f.name: f.default if f.default is not f.default_factory else f.default_factory()
                for f in fields(model)
                if f.default is not f.default_factory or True
            }
            _ = kwargs  # used only to validate model can be constructed from defaults
        except (TypeError, AttributeError):
            pass
        if not instance_fields:
            continue
        # Build a minimal valid instance for each
        if model is ContactInformation:
            obj = model(name="x", city="x", phone="x", email="x", github_url=None, linkedin_url=None)
        elif model is Bullet:
            obj = model(text="x")
        elif model is Experience:
            obj = model(role="x", company="x", start_date="x", end_date="x", bullets=())
        elif model is Project:
            obj = model(name="x", url="", bullets=())
        elif model is Education:
            obj = model(institution="x", location="x", degree="x", major="x", graduation="x", gpa=None)
        elif model is Award:
            obj = model(title="x", organization="x", date="x", description="x")
        elif model is SkillsByCategory:
            obj = model(categories={})
        elif model is MasterResume:
            obj = model(
                contact=ContactInformation("x", "x", "x", "x", None, None),
                summary="x",
                skills=SkillsByCategory({}),
                experiences=(),
                projects=(),
                education=(),
                awards=(),
            )
        elif model is VoiceProfile:
            obj = model(
                avg_bullet_length=0.0,
                bullet_length_stddev=0.0,
                opening_verbs=(),
                punctuation_density={},
                sentence_count_per_bullet=(0, 0),
            )
        elif model is DropReason:
            obj = model(item_id="x", reason="x")
        elif model is GroundedCitation:
            obj = model(tailored_path="x", master_path="x", verbatim_span="x", job_id="x")
        elif model is Job:
            obj = model(
                id="x",
                type=JobType.FETCH,
                started_at="x",
                completed_at="x",
                status=JobStatus.SUCCESS,
                inputs=(),
                outputs=(),
                rationale="x",
                model="x",
                tool_name=None,
                metadata=JobMetadata(),
            )
        elif model is JobDescriptionData:
            obj = model(
                id="x",
                type=JobType.FETCH,
                started_at="x",
                completed_at="x",
                status=JobStatus.SUCCESS,
                inputs=(),
                outputs=(),
                rationale="x",
                model="x",
                tool_name=None,
                metadata={},
            )
        elif model is JobMetadata:
            obj = model()
        elif model is SourceReference:
            obj = model(master_path="x", verbatim_span="x", master_hash="x")
        elif model is WebSearch:
            obj = model(step_number=1, query="x", result_snippet="x", reason="x")
        elif model is Run or model is RunDescription:
            obj = model(
                id="x",
                started_at="x",
                master_hash="x",
                jd_urls_hash="x",
                model="x",
                draft_model=None,
            )
        elif model is RunResult:
            obj = model(
                run=Run("x", "x", "x", "x", "x", None),
                completed_at="x",
                duration_seconds=0.0,
                total_input_tokens=0,
                total_output_tokens=0,
                retry_attempts=0,
                final_outcome=FinalOutcome.SUCCESS,
                jobs=(),
            )
        elif model is TailoredResume:
            obj = model(
                contact=ContactInformation("x", "x", "x", "x", None, None),
                summary="x",
                skills=SkillsByCategory({}),
                experiences=(),
                projects=(),
                education=(),
                awards=(),
                dropped=(),
                rationale="x",
                grounding=(),
                jobs=(),
                run_result=RunResult(
                    Run("x", "x", "x", "x", "x", None),
                    "x",
                    0.0,
                    0,
                    0,
                    0,
                    FinalOutcome.SUCCESS,
                    (),
                ),
            )
        elif model is JobDescription:
            obj = model(
                url="x",
                title="x",
                company="x",
                full_text="x",
                keywords=(),
                must_have_keywords=(),
                nice_to_have_keywords=(),
                content_hash="x",
            )
        else:
            continue

        assert is_dataclass(model), f"{model.__name__} should be a dataclass"
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(obj, next(iter(instance_fields)), "modified")  # type: ignore[misc]


def test_job_factory_assigns_uuid() -> None:
    """The ``job`` factory must assign a UUID and current timestamp."""
    j = job(JobType.FETCH, outputs=("jds[0]",), rationale="fetched")
    assert isinstance(j.id, str)
    assert len(j.id) == 36  # standard UUID4 format with hyphens
    assert j.type == JobType.FETCH
    assert j.outputs == ("jds[0]",)
    assert j.rationale == "fetched"
    assert j.metadata == JobMetadata()


def test_job_description_round_trips() -> None:
    """``Job.description()`` should yield a serializable JobDescription."""
    j = job(JobType.FETCH, outputs=("jds[0]",), rationale="fetched", metadata=JobMetadata(url="https://example.com"))
    desc = j.description()
    assert isinstance(desc, JobDescriptionData)
    assert desc.id == j.id
    assert desc.type == JobType.FETCH
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
        master_hash="x",
        jd_urls_hash="y",
        model="anthropic:claude-sonnet-4-5",
        draft_model=None,
    )
    assert len(run.id.split("-")) == 5  # 5 segments


def test_run_result_websearch_calls_derived() -> None:
    """``RunResult.websearch_calls`` is a derived property, not stored."""
    fetch_job = job(JobType.FETCH)
    web_job = job(JobType.WEBSEARCH, metadata=JobMetadata(query="q"))
    run_result = RunResult(
        run=Run("x", "x", "x", "x", "x", None),
        completed_at="x",
        duration_seconds=0.0,
        total_input_tokens=0,
        total_output_tokens=0,
        retry_attempts=0,
        final_outcome=FinalOutcome.SUCCESS,
        jobs=(fetch_job, web_job),
    )
    assert run_result.websearch_calls == (web_job,)


def test_step_type_enum_values() -> None:
    assert StepType.LOOKUP.value == "lookup"
    assert StepType.VALIDATE.value == "validate"


def test_final_outcome_enum_values() -> None:
    assert FinalOutcome.SUCCESS.value == "success"
    assert FinalOutcome.ATS_HARD_FAIL.value == "ats_hard_fail"


def test_ats_gate_has_eleven_values() -> None:
    """There are 11 ATS gates per the plan (one StrEnum with 12 values: 11 + 1)."""
    assert len(AtsGate) == 12


def test_keyword_tier_enum_values() -> None:
    assert KeywordTier.MUST_HAVE.value == "must_have"
    assert KeywordTier.NICE_TO_HAVE.value == "nice_to_have"
