"""Data models for the gethired system.

All models are frozen dataclasses with ``__slots__`` per AGENTS.md.
Traceability is built on the ``Job`` value object: every pipeline step
produces a ``Job`` whose ``.description()`` returns a serializable
``JobDescription``.

The factory function ``job(...)`` creates a ``Job`` with auto-generated
``Run.id = uuid4()`` and UTC timestamps.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import uuid4

from gethired.observability import utcnow_iso


def _new_uuid() -> str:
    return str(uuid4())


def _now() -> str:
    return utcnow_iso()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class StepType(StrEnum):
    """Type of step performed during a run."""

    LOOKUP = "lookup"
    COMPARE = "compare"
    REORDER = "reorder"
    REWRITE = "rewrite"
    DROP = "drop"
    ADD = "add"
    VALIDATE = "validate"
    PERSIST = "persist"


class JobType(StrEnum):
    """Pipeline-level job type."""

    PARSE = "parse"
    FETCH = "fetch"
    PROFILE = "profile"
    TAILOR = "tailor"
    WEBSEARCH = "websearch"
    VALIDATE_GROUNDING = "validate_grounding"
    VALIDATE_STYLE = "validate_style"
    VALIDATE_PLAGIARISM = "validate_plagiarism"
    VALIDATE_ATS = "validate_ats"
    RENDER = "render"
    PERSIST = "persist"


class JobStatus(StrEnum):
    """Outcome status of a Job."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class FinalOutcome(StrEnum):
    """Outcome of a complete tailoring run."""

    SUCCESS = "success"
    GROUNDING_HARD_FAIL = "grounding_hard_fail"
    STYLE_HARD_FAIL = "style_hard_fail"
    PLAGIARISM_HARD_FAIL = "plagiarism_hard_fail"
    ATS_HARD_FAIL = "ats_hard_fail"


class AtsGate(StrEnum):
    """One of the eleven ATS compliance gates."""

    PDF_COMPILES = "pdf_compiles"
    PDF_TEXT_EXTRACTABLE = "pdf_text_extractable"
    PDF_TEXT_MATCHES_TXT = "pdf_text_matches_txt"
    SECTION_HEADINGS_STANDARD = "section_headings_standard"
    NO_TABLES_FOR_LAYOUT = "no_tables_for_layout"
    NO_IMAGES = "no_images"
    NO_COLORS = "no_colors"
    FONT_SIZE_10_12 = "font_size_10_12"
    LENGTH_WITHIN_LIMIT = "length_within_limit"
    KEYWORDS_COVERED = "keywords_covered"
    BULLETS_QUANTIFIED = "bullets_quantified"
    ACTION_VERBS_FIRST = "action_verbs_first"


class KeywordTier(StrEnum):
    """Tiering for JD keyword coverage checks."""

    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"


# ---------------------------------------------------------------------------
# Resume domain models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContactInformation:
    name: str
    city: str
    phone: str
    email: str
    github_url: str | None
    linkedin_url: str | None


@dataclass(frozen=True, slots=True)
class Bullet:
    text: str


@dataclass(frozen=True, slots=True)
class Experience:
    role: str
    company: str
    start_date: str
    end_date: str
    bullets: tuple[Bullet, ...]


@dataclass(frozen=True, slots=True)
class Project:
    name: str
    url: str
    bullets: tuple[Bullet, ...]


@dataclass(frozen=True, slots=True)
class Education:
    institution: str
    location: str
    degree: str
    major: str
    graduation: str
    gpa: str | None


@dataclass(frozen=True, slots=True)
class Award:
    title: str
    organization: str
    date: str
    description: str


@dataclass(frozen=True, slots=True)
class SkillsByCategory:
    categories: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class MasterResume:
    """Canonical resume model. Single source of truth for tailoring."""

    contact: ContactInformation
    summary: str
    skills: SkillsByCategory
    experiences: tuple[Experience, ...]
    projects: tuple[Project, ...]
    education: tuple[Education, ...]
    awards: tuple[Award, ...]
    schema_version: int = 1

    def to_markdown(self) -> str:
        """Render the resume as Markdown for human inspection."""
        lines: list[str] = [f"# {self.contact.name}", ""]
        contact_bits = [self.contact.city, self.contact.phone, self.contact.email]
        if self.contact.github_url:
            contact_bits.append(self.contact.github_url)
        if self.contact.linkedin_url:
            contact_bits.append(self.contact.linkedin_url)
        lines.append(" · ".join(bit for bit in contact_bits if bit))
        lines.append("")
        lines.append("## Summary")
        lines.append(self.summary)
        lines.append("")
        lines.append("## Technical Skills")
        for category, items in self.skills.categories.items():
            lines.append(f"- **{category}**: {', '.join(items)}")
        lines.append("")
        lines.append("## Experience")
        for exp in self.experiences:
            lines.append(f"### {exp.role} — {exp.company} ({exp.start_date} — {exp.end_date})")
            for bullet in exp.bullets:
                lines.append(f"- {bullet.text}")
            lines.append("")
        lines.append("## Selected Projects")
        for project in self.projects:
            lines.append(f"### [{project.name}]({project.url})")
            for bullet in project.bullets:
                lines.append(f"- {bullet.text}")
            lines.append("")
        lines.append("## Education")
        for edu in self.education:
            bits = [edu.institution, edu.location, edu.degree, edu.major, edu.graduation]
            if edu.gpa:
                bits.append(f"CGPA: {edu.gpa}")
            lines.append("- " + ", ".join(bits))
        lines.append("")
        if self.awards:
            lines.append("## Awards")
            for award in self.awards:
                lines.append(f"- **{award.title}** ({award.organization}, {award.date}): {award.description}")
        return "\n".join(lines)

    def content_hash(self) -> str:
        """Deterministic sha256 over the resume's text content."""
        return _sha256(self.to_markdown())


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    avg_bullet_length: float
    bullet_length_stddev: float
    opening_verbs: tuple[str, ...]
    punctuation_density: dict[str, float]
    sentence_count_per_bullet: tuple[int, int]


@dataclass(frozen=True, slots=True)
class DropReason:
    item_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class GroundedCitation:
    tailored_path: str
    master_path: str
    verbatim_span: str
    job_id: str


# ---------------------------------------------------------------------------
# Job description model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class JobDescription:
    url: str
    title: str
    company: str
    full_text: str
    keywords: tuple[str, ...]
    must_have_keywords: tuple[str, ...]
    nice_to_have_keywords: tuple[str, ...]
    content_hash: str


# ---------------------------------------------------------------------------
# Traceability: WebSearch + Job + JobDescription
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WebSearch:
    """A single WebSearch invocation by the writer agent."""

    step_number: int
    query: str
    result_snippet: str
    reason: str


@dataclass(frozen=True, slots=True)
class JobMetadata:
    """Typed metadata attached to a Job, replacing primitive dict[str, str]."""

    url: str | None = None
    gate: AtsGate | None = None
    char_count: int | None = None
    query: str | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, str]:
        from dataclasses import fields as dc_fields

        result: dict[str, str] = {}
        for f in dc_fields(self):
            value = getattr(self, f.name)
            if value is not None:
                result[f.name] = str(value)
        return result


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Pointer from a tailored claim back to a master span."""

    master_path: str
    verbatim_span: str
    master_hash: str

    def description(self) -> SourceReference:
        return self


@dataclass(frozen=True, slots=True)
class SourceDescription:
    """Serializable form of ``SourceReference`` produced by ``.description()``."""

    master_path: str
    verbatim_span: str
    master_hash: str


@dataclass(frozen=True, slots=True)
class Job:
    """A unit of work performed during a run."""

    id: str
    type: JobType
    started_at: str
    completed_at: str
    status: JobStatus
    inputs: tuple[SourceReference, ...]
    outputs: tuple[str, ...]
    rationale: str
    model: str
    tool_name: str | None
    metadata: JobMetadata

    def description(self) -> JobDescriptionData:
        """Return the serializable ``JobDescription`` for traceability."""
        return JobDescriptionData(
            id=self.id,
            type=self.type,
            started_at=self.started_at,
            completed_at=self.completed_at,
            status=self.status,
            inputs=tuple(ref.description() for ref in self.inputs),
            outputs=self.outputs,
            rationale=self.rationale,
            model=self.model,
            tool_name=self.tool_name,
            metadata=self.metadata.as_dict(),
        )


@dataclass(frozen=True, slots=True)
class JobDescriptionData:
    """Serializable description of a ``Job``, produced by ``Job.description()``."""

    id: str
    type: JobType
    started_at: str
    completed_at: str
    status: JobStatus
    inputs: tuple[SourceReference, ...]
    outputs: tuple[str, ...]
    rationale: str
    model: str
    tool_name: str | None
    metadata: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status.value,
            "inputs": [
                {
                    "master_path": ref.master_path,
                    "verbatim_span": ref.verbatim_span,
                    "master_hash": ref.master_hash,
                }
                for ref in self.inputs
            ],
            "outputs": list(self.outputs),
            "rationale": self.rationale,
            "model": self.model,
            "tool_name": self.tool_name,
            "metadata": dict(self.metadata),
        }

    def to_markdown_row(self) -> str:
        inputs_repr = ", ".join(ref.master_path for ref in self.inputs) or "—"
        outputs_repr = ", ".join(self.outputs) or "—"
        return (
            f"| {self.id[:8]} | `{self.type.value}` | {inputs_repr} | "
            f"{outputs_repr} | {self.rationale} | `{self.status.value}` |"
        )


# ---------------------------------------------------------------------------
# Run + RunResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Run:
    """Identity of a single run. ``Run.id = uuid4()``."""

    id: str
    started_at: str
    master_hash: str
    jd_urls_hash: str
    model: str
    draft_model: str | None

    def description(self) -> RunDescription:
        return RunDescription(
            id=self.id,
            started_at=self.started_at,
            master_hash=self.master_hash,
            jd_urls_hash=self.jd_urls_hash,
            model=self.model,
            draft_model=self.draft_model,
        )


@dataclass(frozen=True, slots=True)
class RunDescription:
    id: str
    started_at: str
    master_hash: str
    jd_urls_hash: str
    model: str
    draft_model: str | None


@dataclass(frozen=True, slots=True)
class RunResult:
    run: Run
    completed_at: str
    duration_seconds: float
    total_input_tokens: int
    total_output_tokens: int
    retry_attempts: int
    final_outcome: FinalOutcome
    jobs: tuple[Job, ...]

    @property
    def websearch_calls(self) -> tuple[Job, ...]:
        """Derived property: jobs of type ``WEBSEARCH``."""
        return tuple(job_ for job_ in self.jobs if job_.type == JobType.WEBSEARCH)

    def describe(self) -> RunDescriptionExtended:
        return RunDescriptionExtended(
            run=self.run.description(),
            completed_at=self.completed_at,
            duration_seconds=self.duration_seconds,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            retry_attempts=self.retry_attempts,
            final_outcome=self.final_outcome,
            jobs=tuple(j.description() for j in self.jobs),
        )


@dataclass(frozen=True, slots=True)
class RunDescriptionExtended:
    run: RunDescription
    completed_at: str
    duration_seconds: float
    total_input_tokens: int
    total_output_tokens: int
    retry_attempts: int
    final_outcome: FinalOutcome
    jobs: tuple[JobDescriptionData, ...]


# ---------------------------------------------------------------------------
# Tailored resume
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TailoredResume:
    """The tailored output plus full traceability."""

    contact: ContactInformation
    summary: str
    skills: SkillsByCategory
    experiences: tuple[Experience, ...]
    projects: tuple[Project, ...]
    education: tuple[Education, ...]
    awards: tuple[Award, ...]
    dropped: tuple[DropReason, ...]
    rationale: str
    grounding: tuple[GroundedCitation, ...]
    jobs: tuple[Job, ...]
    run_result: RunResult

    @property
    def run(self) -> Run:
        """Canonical access to the run identity via ``run_result.run``."""
        return self.run_result.run


# ---------------------------------------------------------------------------
# Job factory
# ---------------------------------------------------------------------------


def job(  # noqa: PLR0913 — factory convenience
    type: JobType,
    inputs: tuple[SourceReference, ...] = (),
    outputs: tuple[str, ...] = (),
    rationale: str = "",
    model: str = "",
    tool_name: str | None = None,
    metadata: JobMetadata | None = None,
    status: JobStatus = JobStatus.SUCCESS,
    started_at: str | None = None,
    completed_at: str | None = None,
    *,
    job_id: str | None = None,
) -> Job:
    """Factory that creates a ``Job`` with auto-generated id and timestamps.

    Example::

        j = job(JobType.FETCH, outputs=("jds[0]",), rationale="...")
        description = j.description()
    """
    now = _now()
    return Job(
        id=job_id if job_id is not None else _new_uuid(),
        type=type,
        started_at=started_at or now,
        completed_at=completed_at or now,
        status=status,
        inputs=inputs,
        outputs=outputs,
        rationale=rationale,
        model=model,
        tool_name=tool_name,
        metadata=metadata or JobMetadata(),
    )


__all__ = [
    "AtsGate",
    "Award",
    "Bullet",
    "ContactInformation",
    "DropReason",
    "Education",
    "Experience",
    "FinalOutcome",
    "GroundedCitation",
    "Job",
    "JobDescription",
    "JobDescriptionData",
    "JobMetadata",
    "JobStatus",
    "JobType",
    "KeywordTier",
    "MasterResume",
    "Project",
    "Run",
    "RunDescription",
    "RunDescriptionExtended",
    "RunResult",
    "SkillsByCategory",
    "SourceDescription",
    "SourceReference",
    "StepType",
    "TailoredResume",
    "VoiceProfile",
    "WebSearch",
    "job",
]
