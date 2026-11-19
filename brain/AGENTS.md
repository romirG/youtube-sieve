# Knowledge-base schema

Rules for every note in `brain/`, for people and AI agents alike. CI validates notes against this schema.

## Folders (PARA)

| Folder | Holds | Move a note here when… |
|---|---|---|
| `inbox/` | New, unsorted material | It has just been captured and not yet reviewed |
| `projects/` | Work with a deadline (e.g. a release or stage) | It serves a goal that will finish |
| `areas/` | Ongoing responsibilities (YouTube API, testing, security) | It needs maintaining with no end date |
| `resources/` | Distilled reference material | It is reviewed, accurate and reusable |
| `archive/` | Inactive notes | Its project finished or it is superseded |
| `templates/` | Note templates | Never; templates are not notes |

`index.md` is the entry point and must link every note outside `inbox/` and `archive/`. `log.md` records every brain-skill run.

## File names

- Lower-case kebab-case, `.md` extension: `tfidf-cosine-similarity.md`.
- **Unique across the whole vault**, because `[[wikilinks]]` resolve by file name.
- AI-session notes: `ai-session-YYYY-MM-DD-<slug>.md`. Review notes: `review-<stage-or-release>.md`. Meeting notes: `meeting-YYYY-MM-DD.md`. Decision notes: `decision-<slug>.md`.

## Frontmatter

Every note except `index.md` and `log.md` starts with YAML frontmatter:

```yaml
---
title: TF-IDF and cosine similarity
type: research
status: distilled
created: 2026-11-19
updated: 2026-11-21
authors: [sidtricoder]
tags: [similarity]
requirements: [FR-1, FR-2]
sources: [https://example.org/article]
---
```

| Field | Required | Allowed values |
|---|---|---|
| `title` | yes | Non-empty text |
| `type` | yes | `research`, `concept`, `decision`, `ai-session`, `review`, `meeting` |
| `status` | yes | `inbox`, `distilled`, `archived` |
| `created` | yes | Date, `YYYY-MM-DD` |
| `updated` | no | Date, `YYYY-MM-DD`, not before `created` |
| `authors` | yes | List of GitHub usernames, at least one |
| `tags` | no | List of lower-case kebab-case words |
| `requirements` | no | List of requirement IDs, e.g. `FR-1`, `NFR-3`, `SK-1`, `TQ-6`, `SB-2` |
| `sources` | `research` notes: yes | List of URLs or repository paths |

`status` must agree with the folder: `inbox/` → `inbox`; `archive/` → `archived`; everywhere else → `distilled`.

## Note types

- **research**: what an external source says, summarised in your own words, with sources.
- **concept**: an idea explained for the team (e.g. PARA, quota costs), linking the research behind it.
- **decision**: a design decision: context, options considered, the choice, and its consequences. File it in the `areas/` or `projects/` folder it concerns, and link the issue or PR that implements it. Significant decisions are also recorded as an ADR in `docs/adr/` that cites this note.
- **ai-session**: a significant AI-assisted session: goal, what worked, what failed, follow-ups.
- **review**: end-of-stage review: what worked, what did not, what to change.
- **meeting**: decisions and action items from a team meeting.

## Linking

- Link related notes with `[[file-name]]` (no `.md`). Every note links at least one other note.
- No broken links: every `[[target]]` must match an existing file name.
- Refer to requirements by ID in `requirements` and in the text (e.g. "supports FR-1").
- Refer to GitHub work as `#12` (issue or PR) in the text.
- Architecture Decision Records (`docs/adr/`) cite at least one distilled note; skills cite at least one distilled note.

## Writing

- Summarise in your own words; quote sparingly and attribute quotes.
- One topic per note. Split notes that cover several topics.
- No secrets, tokens or real personal data.

## Run log

Each run of `brain-ingest`, `brain-refine` or `brain-query` appends one row to `log.md`:

```
| YYYY-MM-DD | skill | GitHub username | what changed, with [[links]] | PR #n |
```
