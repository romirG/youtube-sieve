---
title: Stage 1 review
type: review
status: distilled
created: 2026-11-27
authors: [sidtricoder]
tags: [review, stage-1]
requirements: [SB-2]
---

# Stage 1 review

**Stage or release:** Stage 1 (requirements), released as `v0.1.0` (#30)

First draft written from the repository history. Teammates: add or correct points in review on #30.

## What worked

- **Issue → branch → PR for every change.** Every change from #2 to #29 came in through a pull request that closes an issue, on a branch named `<type>/<issue>-<slug>`. Nothing was pushed straight to `main`.
- **CI caught problems before merge.** Ruff, pytest with a 90% coverage gate, Gitleaks, and the vault and skill validators run on every PR, so schema and formatting errors were fixed in review rather than on `main`.
- **Decide before building.** Quota enforcement and playlist confirmation were settled in decision notes and ADRs 0001 and 0002 before the code that depends on them ([[decision-quota-budget-enforcement]], [[decision-browser-only-playlist-confirmation]]).
- **Everyone wrote notes (SB-6).** All four members ingested research notes with brain-ingest, as [[log]] shows: 14 notes in total, above the Stage 1 minimum of 10.
- **The domain layer is pure and tested.** Duration parsing, TF-IDF similarity ([[decision-tfidf-similarity]]) and quota arithmetic have no I/O, so they can be tested without the API (TQ-1).

## What did not work

- **Merge practice differs from `CONTRIBUTING.md`.** The guide says squash-merge and rebase on `main`. Instead, every PR was merged with a merge commit, and several branches merged `main` into themselves (#24, #26, #27). This makes `main`'s history noisier than planned.
- **Run-log rows were written before their PR existed.** One row stayed as "PR pending" after its PR (#26) merged, which broke the note → PR link that SB-1 asks for.
- **No research note has been refined yet.** All 14 notes are still in `inbox/`, so [[index]] links none of the research, and later skills and ADRs can only cite the decision notes.
- **Code got ahead of design.** The domain layer was built before any architecture document. That is fine for pure functions, but the provider, service and MCP layers need a design before they are written.
- **Deleted branches confused local clones.** Merged branches are deleted on GitHub, but local remote-tracking branches were not pruned, so pulling a merged branch failed with "couldn't find remote ref".

## What we will change

- Either allow only squash merging in the repository settings, or update `CONTRIBUTING.md` to describe the merge-commit flow. Rebase instead of merging `main` into branches.
- Add the run-log row after opening the PR, when its number is known.
- Run brain-refine early in Stage 2 to move the inbox notes into `areas/` and `resources/`.
- Write the Stage 2 architecture document, including the YouTube provider interface (SE-6), before the provider and MCP layers.
- Everyone sets `git config --global fetch.prune true`.

## Related
- [[index]]
- [[log]]
