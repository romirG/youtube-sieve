---
title: CI and knowledge-base validation tooling
type: decision
status: distilled
created: 2026-11-20
authors: [sidtricoder]
tags: [decision, ci, tooling]
requirements: [SB-1, SB-5, TQ-8]
sources: [https://docs.astral.sh/ruff/, https://github.com/gitleaks/gitleaks, https://peps.python.org/pep-0735/]
---

# CI and knowledge-base validation tooling

**Status:** accepted
**Issue / PR:** #7

## Context
Every pull request needs automatic checks for code quality, tests, the knowledge-base schema in [[AGENTS]] and accidentally committed secrets. The checks must run identically on each member's machine (Windows and Linux) and in GitHub Actions, and be cheap enough to run on every push.

## Options considered
1. **Lint and format:** Ruff, versus flake8 + isort + Black. Ruff replaces all three with one fast tool and one configuration block.
2. **Vault validation:** an existing Markdown or link checker, versus a small Python script. Generic link checkers do not understand `[[wikilinks]]`, frontmatter fields or the rule that `status` must match the PARA folder.
3. **Secret scanning:** GitHub's built-in secret scanning only, versus Gitleaks in CI as well. Gitleaks scans full history on every PR and fails the build, rather than alerting after the fact.
4. **Development dependencies:** `requirements-dev.txt`, versus a `[dependency-groups]` table in `pyproject.toml` (PEP 735). Dependency groups keep all configuration in one standard file without making dev tools part of the package.

## Decision
- Ruff for linting and formatting, pytest with pytest-cov for tests, with a 90% branch-coverage threshold.
- A purpose-built validator, `tools/validate_brain.py`, whose rules mirror [[AGENTS]] one-to-one and are listed as separate functions, so a new schema rule is a new function rather than an edit to existing ones.
- Gitleaks in CI alongside GitHub's own scanning.
- Exact version pins in a PEP 735 `dev` dependency group, so local and CI runs use the same tools.
- Four separate CI jobs (lint, tests, knowledge base, secrets), so each can become an individually required status check.

## Consequences
- Contributors need pip 25.1 or newer for `pip install --group dev`.
- Any change to the schema in `brain/AGENTS.md` must change the validator and its tests in the same pull request.
- Version pins need periodic updates (Dependabot can be added later).

## Related
- [[index]]
