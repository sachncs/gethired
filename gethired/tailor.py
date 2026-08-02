"""Tailor — orchestrator class (entry point).

Multi-agent coordination: parser → fetcher → description → profiler → writer → critic → renderer.
"""

from __future__ import annotations

from gethired.models import JobDescription, MasterResume, TailoredResume


class Tailor:
    """Main entry point for the gethired system.

    Example::

        tailor = Tailor(resume=master_resume, job_description=job, debug=True)
        result = tailor.run()
    """

    def __init__(
        self,
        resume: MasterResume | str,
        job_description: JobDescription | str,
        debug: bool = False,
        model: str | None = None,
        draft_model: str | None = None,
    ) -> None:
        self._resume = resume
        self._job_description = job_description
        self._debug = debug
        self._model = model
        self._draft_model = draft_model

    def run(self) -> TailoredResume:
        """Execute the full tailoring pipeline."""
        raise NotImplementedError("Tailor.run is not yet implemented")

    def plan(self) -> dict[str, object]:
        """Estimate cost without executing the agent."""
        raise NotImplementedError("Tailor.plan is not yet implemented")

    def finalize(self, edited_json_path: object) -> TailoredResume:
        """Re-render an edited tailored.json without calling the agent."""
        raise NotImplementedError("Tailor.finalize is not yet implemented")

    def diff(self, other_run_id: str) -> str:
        """Return a markdown diff between this run and a prior run."""
        raise NotImplementedError("Tailor.diff is not yet implemented")


__all__ = ["Tailor"]
