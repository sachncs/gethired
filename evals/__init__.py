"""gethired evaluation framework.

Implements the patterns described in Anthropic's "Demystifying evals for AI agents":

- Tasks (test cases) defined in YAML
- Three grader types: code-based, model-based, outcome
- Trial recording with transcripts
- pass@k and pass^k metrics
- Capability vs regression eval categories

Run via the CLI: ``gethired-eval [--category parser] [--trials 3]``
"""

from evals.graders.code import (
    GraderResult,
    code_equal,
    code_field_length,
    code_field_present,
    code_json_round_trip,
    code_no_banned_words,
    code_no_jd_plagiarism,
    code_numbers_in_master,
    code_text_contains,
    code_text_not_contains,
)
from evals.graders.registry import GraderRegistry
from evals.harness import (
    EvalHarness,
    EvalSuiteResult,
    GraderResultRecord,
    GraderSpec,
    TaskDefinition,
    TaskOutcome,
    TrialRecord,
    load_suite,
    load_task,
)
from gethired.models import TailoredResume

__all__ = [
    "EvalHarness",
    "EvalSuiteResult",
    "GraderSpec",
    "GraderResultRecord",
    "TaskDefinition",
    "TaskOutcome",
    "TrialRecord",
    "code_equal",
    "code_field_length",
    "code_field_present",
    "code_json_round_trip",
    "code_no_banned_words",
    "code_no_jd_plagiarism",
    "code_numbers_in_master",
    "code_text_contains",
    "code_text_not_contains",
    "load_suite",
    "load_task",
]
