---
title: The Agent Skills format
type: research
status: inbox
created: 2026-11-22
authors: [sidtricoder]
tags: [skills, agents]
requirements: [SK-1, SB-3]
sources:
  - https://agentskills.io/specification
  - https://modelcontextprotocol.io/specification
---

# The Agent Skills format

## Summary
An Agent Skill is a folder of instructions an AI agent can load when a task calls for it. The only required file is `SKILL.md`: YAML frontmatter followed by Markdown instructions. Optional folders hold supporting material: `scripts/` (code the agent can run), `references/` (extra documentation) and `assets/` (templates, images, data).

## Key points

**Frontmatter fields:**

| Field | Required | Rules |
|---|---|---|
| `name` | yes | 1–64 characters; lower-case `a–z`, digits and hyphens; no leading, trailing or double hyphens; **must equal the folder name** |
| `description` | yes | 1–1024 characters; says **what** the skill does and **when** to use it, with keywords that help an agent pick it |
| `license` | no | a licence name or a bundled licence file |
| `compatibility` | no | up to 500 characters on environment needs (product, packages, network); most skills omit it |
| `metadata` | no | a map of string keys to string values |
| `allowed-tools` | no | experimental; space-separated tools pre-approved for the skill |

No other fields are allowed.

**Progressive disclosure: why skills stay small**
1. At start-up the agent loads only each skill's `name` and `description` (about 100 tokens per skill).
2. When it activates a skill, it loads the whole `SKILL.md` body. Under 5,000 tokens and 500 lines is recommended.
3. Files in `scripts/`, `references/` and `assets/` load only when needed. Reference them by relative path, one level deep from `SKILL.md`.

So the description decides *whether* a skill is used, and long reference material belongs in separate files rather than the body.

**Body:** there is no required structure. Step-by-step instructions, input and output examples, and common edge cases are recommended.

**Validation:** the reference library `skills-ref` checks frontmatter and naming (`skills-ref validate ./my-skill`).

**Skills and MCP:** the MCP specification lists "Skills over MCP", an extension under development for discovering and using skills through an MCP server.

## Relevance to youtube-sieve
- **Skills we must ship:** `video-to-playlist` (SK-1), `local-check`, and the brain skills (`brain-ingest` exists; `brain-refine`, `brain-query` to come). Each needs a precise description naming its trigger, for example "Use when the user wants a playlist built from one video".
- **Keep `SKILL.md` lean:** put long material, such as tool parameter tables or constraint rules, in `references/` so the body stays under the recommended size.
- **Already enforced:** CI validates every skill with `skills-ref` plus our rule that each skill cites a distilled note (SB-3); see [[decision-skill-validation]].
- **Open question:** whether to also serve `video-to-playlist` through the "Skills over MCP" extension, so MCP clients discover it from the server itself. This depends on client support and the extension's maturity; see [[mcp-fundamentals]].

## Related
- [[mcp-fundamentals]]
- [[para-method]]
- [[index]]
