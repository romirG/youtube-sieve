---
title: Enforce quota budgets before calling the YouTube API
type: decision
status: distilled
created: 2026-11-22
authors: [sidtricoder]
tags: [decision, quota, youtube-api]
requirements: [TQ-6, QM-1, QM-2, QM-3, QM-4, QM-9, FR-5]
sources: [https://developers.google.com/youtube/v3/determine_quota_cost, https://developers.google.com/youtube/v3/getting-started]
---

# Enforce quota budgets before calling the YouTube API

**Status:** accepted
**Issue / PR:** #19
**ADR:** `docs/adr/0001-enforce-quota-budget-before-api-calls.md`

## Context
All users share one Google Cloud project, and Google charges that project for every call ([[youtube-api-quota-costs]]):

- by default, **10,000 units a day** for most methods, plus a **separate bucket of 100 `search.list` calls**
- both reset at **midnight Pacific Time**
- invalid requests still cost at least one unit, and each extra page costs the full price again
- playlist writes are expensive: a playlist of *n* videos costs 50 + 50·*n* units

TQ-6 requires that the system tracks quota cost per request, and that a workflow which would exceed the remaining budget is **rejected before any API call**. The previous implementation only counted usage and let Google refuse requests mid-workflow, which can leave a playlist half-written and lets one user exhaust everyone's quota.

## Options considered
1. **Meter only; let Google enforce.** Least code. But failures happen half-way through a workflow, there is no fairness between users, and TQ-6 is not met.
2. **Check the remaining budget before each individual API call.** Stops early, but a multi-call workflow can still fail part-way (for example after creating a playlist but before inserting its videos).
3. **Estimate a whole workflow's worst-case cost up front, reserve it atomically, then reconcile afterwards.** Rejects before any call, never strands a workflow half-way for budget reasons, and is safe when several server instances share the budget.

## Decision
Option 3.

- **Two pools per Pacific-time day:** API *units* and *search calls*. Allowances are **configuration**, not code, because Google says they can change.
- **Layered budgets:** a global budget for the project; a cap for public (signed-out) callers; a per-user daily budget for signed-in callers. A request must fit every budget that applies to it.
- **Estimate first.** Each workflow (one MCP tool call) builds a plan of the API calls it will make and computes their worst-case cost from a configurable cost table, counting every page it may fetch. Items already in the cache cost nothing.
- **Reject or reserve.** If the estimate exceeds what remains in any applicable budget, the tool returns an `isError` result saying what was needed, what remains and when the budget resets, and **no API call is made**. Otherwise the estimate is reserved in shared storage in one atomic step, so concurrent requests and multiple instances cannot overdraw it.
- **Reconcile.** After the workflow, the actual cost is recorded and any unused reservation released. Calls that failed are still charged, as Google charges them.
- **Respect Google's verdict.** If Google returns `quotaExceeded`, that pool is marked exhausted until the next reset, and further billable workflows are rejected locally ([[youtube-api-errors]]).
- **Playlist size** is capped by a named constant, so the worst-case write cost is known before the draft is shown.

## Consequences
- Every provider call has a known cost, and the estimate must never undercount it. Tests must check, against a fake provider, that a rejected workflow makes **zero** calls (TQ-6).
- Users get a clear, early refusal instead of a confusing failure half-way through.
- Default values need care. With the SRS defaults, a 50-video playlist (2,550 units) would not fit a 2,500-unit per-user budget; the defaults will be set together when the quota module is built.
- Request-rate limiting (QM-8) is a separate control and is not covered here.

## Related
- [[decision-browser-only-playlist-confirmation]]
- [[youtube-api-methods]]
- [[index]]
