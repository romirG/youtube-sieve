# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Knowledge-base vault in `brain/` with PARA folders, index and run log (#1).
- Pull request template, issue forms, contributing guide and this changelog (#3).
- Root `AGENTS.md`, knowledge-base schema in `brain/AGENTS.md` and note templates, including code-design, scalability and testing rules, and decision notes (#5).
- CI pipeline: Ruff lint and format, pytest with coverage, knowledge-base schema validation and Gitleaks secret scanning (#7).
- `tools/validate_brain.py`, which checks every note against `brain/AGENTS.md` (#7).
- `brain-ingest` skill for capturing sources as schema-valid inbox notes (#9).
- `tools/validate_skills.py` and an *Agent Skills* CI job: specification checks via `skills-ref`, plus each skill must cite a distilled note (#9).
- Concept note on the PARA method and a decision note on skill validation (#9).
- Research notes on MCP fundamentals, MCP authorization and the Agent Skills format (#11).
- Research notes on YouTube Data API quota costs, API methods, error reasons and playlist creation (#12).
