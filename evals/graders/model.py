"""Model-based graders (LLM-as-judge) for subjective evaluations.

Per Anthropic's article: model graders are flexible, scalable, and capture
nuance for open-ended tasks. They should be calibrated against human
graders before being trusted. They are non-deterministic and more
expensive than code-based graders.
"""

from __future__ import annotations

from dataclasses import dataclass

from gethired.provider import resolve_model


@dataclass(frozen=True, slots=True)
class ModelGrade:
    """LLM judge output."""

    name: str
    score: float         # 0.0-1.0
    passed: bool
    rationale: str
    raw_response: str


_MODEL_GRADE_PROMPT = """You are evaluating the output of a resume tailoring system.

Rubric:
{rubric}

Output to evaluate:
{output}

Reply with strict JSON of the form:
{{"score": <0.0-1.0>, "rationale": "<one or two sentences>"}}
"""


def model_grade(
    name: str,
    rubric: str,
    output: str,
    model_string: str | None = None,
    threshold: float = 0.7,
) -> ModelGrade:
    """Run an LLM-as-judge grader against ``output`` using ``rubric``.

    Args:
        name: Stable grader name (used in reports).
        rubric: Human-readable rubric describing the criteria.
        output: The candidate output text.
        model_string: Model identifier; defaults to ``MODEL`` env var.
        threshold: Minimum score to count as ``passed``.

    Returns:
        A ``ModelGrade`` with score, pass/fail, rationale, and raw response.
    """
    import asyncio
    import json

    from pydantic_ai import Agent

    resolved = resolve_model(model_string)
    agent = Agent(
        resolved.model,
        system_prompt=(
            "You grade outputs against a rubric. "
            "Reply with strict JSON only."
        ),
        output_type=str,
    )
    prompt = _MODEL_GRADE_PROMPT.format(rubric=rubric, output=output)
    result = asyncio.run(agent.run(prompt))
    raw = result.output.strip()

    try:
        parsed = json.loads(raw)
        score = float(parsed.get("score", 0.0))
        rationale = str(parsed.get("rationale", ""))
    except (json.JSONDecodeError, ValueError, TypeError):
        score = 0.0
        rationale = f"Could not parse LLM response: {raw[:200]}"

    return ModelGrade(
        name=name,
        score=score,
        passed=score >= threshold,
        rationale=rationale,
        raw_response=raw,
    )


__all__ = ["ModelGrade", "model_grade"]
