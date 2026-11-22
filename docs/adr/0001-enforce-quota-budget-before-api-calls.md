# 0001. Enforce quota budgets before calling the YouTube API

- **Status:** Accepted
- **Date:** 2026-11-22
- **Decision note:** [`brain/areas/decision-quota-budget-enforcement.md`](../../brain/areas/decision-quota-budget-enforcement.md)
- **Requirements:** TQ-6, QM-1 to QM-4, QM-9, FR-5

## Context
All users share one Google Cloud project's daily allowance:
- by default, 10,000 units for most methods, plus a separate bucket of 100 `search.list` calls
- both reset at midnight Pacific Time
- failed calls are still charged
- playlist writes cost 50 + 50·*n* units for *n* videos

TQ-6 requires that a workflow which would exceed the remaining budget is rejected before any API call. Metering alone lets workflows fail half-way, and lets one user exhaust everyone's quota.

## Decision
- Track two pools per Pacific-time day, **units** and **search calls**. Allowances and per-method costs are configuration.
- Apply layered budgets: global, a cap for public callers, and a per-user daily budget.
- Before any API call, each workflow estimates its **worst-case cost** from the planned calls, including every page and excluding cached items. If the estimate exceeds what remains in any applicable budget, the workflow is rejected with an actionable tool error and **no API call is made**.
- Otherwise the estimate is **reserved atomically** in shared storage, and reconciled with actual usage afterwards; unused amounts are released.
- A `quotaExceeded` response from Google marks that pool exhausted until reset.

## Consequences
- Early, clear refusals; no budget-caused half-written playlists; fair sharing between users.
- Every provider call needs an accurate cost, and estimates must never undercount.
- Tests must prove a rejected workflow makes zero provider calls.
- The default budget values must be set together, so the largest allowed playlist fits a single user's budget.
- Request-rate limiting (QM-8) is decided separately.
