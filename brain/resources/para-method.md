---
title: The PARA method and how our vault uses it
type: concept
status: distilled
created: 2026-11-22
authors: [sidtricoder]
tags: [knowledge-base, para]
requirements: [SB-1, SB-5]
sources: [https://fortelabs.com/blog/para/]
---

# The PARA method and how our vault uses it

## Explanation
PARA is a way of organising notes by **how soon you will act on them**, not by subject. Every note lives in exactly one of four places:

- **Projects**: work with a goal and a deadline. It finishes.
- **Areas**: responsibilities with a standard to maintain but no end date.
- **Resources**: reference material on topics of interest, useful later.
- **Archive**: anything from the other three that is no longer active.

Because the categories follow actionability, a note can move: research gathered as a resource becomes part of a project when it is needed, and returns to the archive when the project ends. Sorting by subject instead tends to create deep folder trees that nobody maintains.

## How we use it
Our vault in `brain/` adds an **inbox** in front of the four PARA folders, so capture and organisation are separate steps:

1. **Capture** (brain-ingest): new material lands in `inbox/` with `status: inbox`, quickly and without deciding where it belongs.
2. **Refine** (brain-refine): each inbox note is reviewed, merged with duplicates, linked, and moved to `projects/`, `areas/` or `resources/` with `status: distilled`, and linked from [[index]].
3. **Query** (brain-query): questions are answered from distilled notes, with citations.
4. **Archive**: finished project notes move to `archive/` with `status: archived`.

Examples for youtube-sieve:

| Folder | Example notes |
|---|---|
| `projects/` | stage deliverables, a release plan |
| `areas/` | YouTube API usage and quota, testing, security, design decisions |
| `resources/` | TF-IDF and cosine similarity, MCP concepts, this note |
| `archive/` | notes for a finished stage |

The exact rules (folders, frontmatter, links) are in [[AGENTS]] and are enforced in CI.

## Related
- [[index]]
- [[decision-ci-and-validation-tooling]]
