"""Validate every Agent Skill under skills/.

Two layers of rules:
1. The Agent Skills specification, checked by the official `skills-ref` reference library.
2. Project rules: each SKILL.md cites at least one distilled note in the knowledge base (SB-3)
   and contains no broken [[wikilinks]]. Vault parsing is reused from tools.validate_brain.

Usage: python -m tools.validate_skills [--skills DIR] [--brain DIR]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from skills_ref import validate as validate_specification

from tools.problems import Problem
from tools.reporting import report
from tools.validate_brain import Vault, link_targets, load_vault, parse_note

DEFAULT_SKILLS = Path("skills")
DEFAULT_VAULT = Path("brain")
SKILL_FILE = "SKILL.md"


def skill_directories(skills_root: Path) -> list[Path]:
    """Each visible subdirectory of the skills folder is one skill."""
    return sorted(p for p in skills_root.iterdir() if p.is_dir() and not p.name.startswith("."))


def _display_path(skills_root: Path, path: Path) -> PurePosixPath:
    return PurePosixPath(skills_root.name, *path.relative_to(skills_root).parts)


def check_citations(skill_md: Path, vault: Vault) -> Iterable[str]:
    """Body links must resolve, and at least one must point at a distilled note."""
    body = parse_note(PurePosixPath(SKILL_FILE), skill_md.read_text(encoding="utf-8")).body
    targets = [t for t in link_targets(body) if t]
    known, distilled = vault.known_targets(), vault.distilled_names()
    for target in targets:
        if target not in known:
            yield f"broken link [[{target}]]: no note or attachment with that name in brain/"
    if not any(t in distilled for t in targets):
        yield "skill must cite at least one distilled note in brain/ with [[...]] (SB-3)"


def validate_skill(skill_dir: Path, skills_root: Path, vault: Vault | None) -> list[Problem]:
    skill_md = skill_dir / SKILL_FILE
    shown = _display_path(skills_root, skill_md if skill_md.is_file() else skill_dir)
    messages = list(validate_specification(skill_dir))
    if skill_md.is_file() and vault is not None:
        messages.extend(check_citations(skill_md, vault))
    return [Problem(shown, message) for message in messages]


def validate(skills_root: Path, vault_root: Path) -> list[Problem]:
    if not skills_root.is_dir():
        return [
            Problem(
                PurePosixPath(skills_root.name), f"skills folder '{skills_root}' does not exist"
            )
        ]
    directories = skill_directories(skills_root)
    if not directories:
        return [Problem(PurePosixPath(skills_root.name), "no skills found")]
    problems: list[Problem] = []
    vault = load_vault(vault_root) if vault_root.is_dir() else None
    if vault is None:
        problems.append(
            Problem(
                PurePosixPath(vault_root.name), f"vault directory '{vault_root}' does not exist"
            )
        )
    for directory in directories:
        problems.extend(validate_skill(directory, skills_root, vault))
    return sorted(set(problems))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Agent Skills under skills/.")
    parser.add_argument("--skills", type=Path, default=DEFAULT_SKILLS, help="skills folder")
    parser.add_argument("--brain", type=Path, default=DEFAULT_VAULT, help="knowledge-base vault")
    args = parser.parse_args(argv)
    return report(validate(args.skills, args.brain), args.skills, "CONTRIBUTING.md")


if __name__ == "__main__":
    sys.exit(main())
