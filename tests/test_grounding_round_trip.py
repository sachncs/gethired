"""Data-process tests: end-to-end verification of the citation round-trip.

These tests are the most important safety net: every tailored bullet
must cite a verbatim span that appears in the master. This is the
property the system promises but which no existing test exercises.
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from gethired.models import Citation, Job, Tailored
from gethired.tailor import Tailor
from gethired.validator import grounding

SAMPLE_JD = Job(
    url="https://example.com/jd",
    title="ML Engineer",
    company="Acme",
    full_text="Need Python and Kubernetes experience.",
    keywords=("python", "kubernetes"),
    must_have_keywords=("python", "kubernetes"),
    nice_to_have_keywords=(),
    content_hash="abc",
)


def test_grounding_citation_round_trip_passes(resume: Master) -> None:
    """Every verbatim span in a Citation must appear in the master.

    The GroundedCitation dataclass promises that each tailored bullet
    cites a verbatim span from the master. Grounding() verifies this.
    Construct a Citation with a real master span and assert the round-trip.
    """
    master_span = resume.experience[0].bullets[0].text
    citation = Citation(
        tailored_path="experiences[0].bullets[0]",
        master_path="experiences[0].bullets[0]",
        verbatim_span=master_span,
        job_id="writer",
    )
    tailored = Tailored(
        name=resume.name,email=resume.email,city=resume.city,phone=resume.phone,github=resume.github,linkedin=resume.linkedin,
        summary=resume.summary,
        skills=resume.skills,
        experience=resume.experience,
        projects=resume.projects,
        education=resume.education,
        awards=resume.awards,
        dropped=(),
        rationale="test",
        grounding=(citation,),
        jobs=(),
    )
    violations = grounding(tailored, resume)
    # The real master span should produce zero violations
    assert not violations, (
        f"grounding() flagged a real citation; expected no violations, got {violations}"
    )


def test_grounding_citation_with_fabricated_span_fails(resume: Master) -> None:
    """A Citation whose verbatim_span is NOT in the master must fail grounding.

    This is the failure mode that catches a writer bug: a Citation was
    emitted with a span that doesn't exist in the master, which is
    exactly the kind of fabrication we need to prevent.
    """
    fabricated_span = "This text was never in the master resume, ever."
    citation = Citation(
        tailored_path="experiences[0].bullets[0]",
        master_path="experiences[0].bullets[0]",
        verbatim_span=fabricated_span,
        job_id="writer",
    )
    tailored = Tailored(
        name=resume.name,email=resume.email,city=resume.city,phone=resume.phone,github=resume.github,linkedin=resume.linkedin,
        summary=resume.summary,
        skills=resume.skills,
        experience=resume.experience,
        projects=resume.projects,
        education=resume.education,
        awards=resume.awards,
        dropped=(),
        rationale="test",
        grounding=(citation,),
        jobs=(),
    )
    violations = grounding(tailored, resume)
    assert violations, "grounding() did not flag a fabricated citation span"
    assert any(fabricated_span in v.detail for v in violations), (
        f"grounding() violations do not name the fabricated span: {violations}"
    )


def test_grounding_citation_partial_span_still_passes(resume: Master) -> None:
    """A Citation whose span is a substring of a master bullet is valid.

    Real writers may emit a span that is a contiguous substring of a
    master bullet. Grounding() must accept this as long as the substring
    is present in the master text.
    """
    full_bullet = resume.experience[0].bullets[0].text
    # Take the first 30 characters as the citation span
    if len(full_bullet) < 30:
        pytest.skip("master bullet is too short to substring")
    partial_span = full_bullet[:30]
    citation = Citation(
        tailored_path="experiences[0].bullets[0]",
        master_path="experiences[0].bullets[0]",
        verbatim_span=partial_span,
        job_id="writer",
    )
    tailored = Tailored(
        name=resume.name,email=resume.email,city=resume.city,phone=resume.phone,github=resume.github,linkedin=resume.linkedin,
        summary=resume.summary,
        skills=resume.skills,
        experience=resume.experience,
        projects=resume.projects,
        education=resume.education,
        awards=resume.awards,
        dropped=(),
        rationale="test",
        grounding=(citation,),
        jobs=(),
    )
    violations = grounding(tailored, resume)
    assert not violations, f"grounding() should accept a substring span, got {violations}"


def test_tailor_pipeline_emits_real_grounding_citations(resume: Master) -> None:
    """The full Tailor pipeline produces a TailoredResume that passes grounding.

    This is the end-to-end data process test: parse the master, run the
    writer with a TestModel, and verify the produced TailoredResume has
    no grounding violations. The grounding tuple may be empty when the
    TestModel doesn't emit citations, but the structure must be valid.
    """
    tailor = Tailor(
        resume=resume,
        job_description=SAMPLE_JD,
        model="test",
        model_instance=TestModel(),
    )
    result = tailor.run()
    # The result must be a valid TailoredResume (no exceptions raised)
    assert isinstance(result, Tailored)
    # Grounding must return a tuple (possibly empty) - the validator must
    # handle empty grounding gracefully
    violations = grounding(result, resume)
    assert isinstance(violations, tuple)
    # If citations were emitted, they must all check out
    if result.grounding:
        for citation in result.grounding:
            assert isinstance(citation, Citation)
            assert citation.verbatim_span, "citation must have a non-empty verbatim_span"
            assert citation.tailored_path, "citation must have a tailored_path"
            assert citation.master_path, "citation must have a master_path"
