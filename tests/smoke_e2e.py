"""End-to-end smoke test with real MiniMax-M3 model.

Run with: uv run python -m tests.smoke_e2e
Requires API_KEY env var or .env file with valid MiniMax-M3 credentials.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from gethired.models import JobDescription
from gethired.parser import parse_tex
from gethired.tailor import Tailor

# Load .env manually
_ENV_PATH = Path(__file__).parent.parent / ".env"
if _ENV_PATH.exists():
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key, value)


def main() -> int:
    master = parse_tex("resume.tex")

    # Synthetic JD to avoid network dependency
    jd = JobDescription(
        url="test://synthetic",
        title="Senior Machine Learning Engineer",
        company="Acme AI",
        full_text=(
            "We are hiring a Senior Machine Learning Engineer with 5+ years "
            "experience in Python, Kubernetes, distributed systems, and PyTorch. "
            "You will design and deploy ML platforms, lead architecture reviews, "
            "and mentor junior engineers. Nice to have: LLM inference, RAG, AWS."
        ),
        keywords=("python", "kubernetes", "pytorch", "distributed"),
        must_have_keywords=("python", "kubernetes", "pytorch"),
        nice_to_have_keywords=("llm", "rag", "aws"),
        content_hash="smoke-test",
    )

    tailor = Tailor(resume=master, job_description=jd, debug=False, model="MiniMax-M3")
    print("Running full pipeline with MiniMax-M3...")
    tailored = tailor.run()

    print()
    print(f"Run.id: {tailored.run.id}")
    print(f"final_outcome: {tailored.run_result.final_outcome}")
    print(f"jobs: {len(tailored.jobs)}")
    print(f"grounding citations: {len(tailored.grounding)}")
    print()
    print("=== Summary (rewritten by MiniMax-M3) ===")
    print(tailored.summary)
    print()
    print(f"=== Output written to: tailored/{tailored.run.id}/ ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
