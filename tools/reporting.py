"""Shared command-line reporting for the repository validators."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from tools.problems import Problem


def report(problems: Sequence[Problem], location: Path, guidance: str) -> int:
    """Print every problem and a summary; return the process exit code (0 clean, 1 problems)."""
    for problem in problems:
        print(problem)
    if not problems:
        print(f"{location}: no problems found.")
        return 0
    noun = "problem" if len(problems) == 1 else "problems"
    print(f"\n{len(problems)} {noun} found in {location}. See {guidance}.")
    return 1
