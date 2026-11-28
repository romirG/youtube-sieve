---
title: One error catalogue, mapped in the services layer, with a structured error object
type: decision
status: distilled
created: 2026-11-28
authors: [Devaang-Rastogi]
tags: [decision, errors, architecture]
requirements: [IF-4, US-2, TQ-4, SC-10, AC-4, AC-11, QM-2, QM-8, QM-9, RL-2]
---

# One error catalogue, mapped in the services layer, with a structured error object

**Status:** accepted
**Issue / PR:** #43
**Design:** `docs/design/errors.md`

## Context
The SRS uses eight error codes in different sections (`invalid_input`, `not_found`, `quota_budget_exceeded`, `quota_exceeded`, `rate_limited`, `channel_required`, `not_enough_videos`, `upstream_unavailable`), plus the OAuth `insufficient_scope`. It never lists them in one place, and several required situations have no code at all: an expired Google grant (AC-11), unsatisfiable constraints (FR-5.6), an expired draft (FR-5.10) and an uncertain write (FR-5.18). SRS §4.7 fixes the error object as `{"error": {"code", "message"}}`, but QM-2 also asks for the estimated cost, remaining budget and reset time, and QM-8 for a retry delay. The provider design ([[decision-youtube-provider-interface]]) left the mapping from its error types to these codes to this issue. [[youtube-api-errors]] lists the Google reasons behind them.

## Options considered

**Where errors are mapped to codes**
1. **In each transport** (MCP tools, web routes). Transports would need to know provider and domain error types, putting logic in the layer that ADR 0003 keeps thin ([[decision-layered-architecture]]), and the MCP and web mappings could drift apart.
2. **In the provider adapter.** The adapter would choose user-facing codes, but the right code often depends on the use case. A `NotFound` is `not_found` for a seed video, but only a skipped item when adding one video to a playlist.
3. **In the services layer.** Services already know the use case, so they catch domain and provider errors and raise one application error with a catalogue code. Transports only render it.

**Extra data in the error object**
1. **Only `code` and `message`, exactly as §4.7 shows.** Numbers such as the remaining quota would then live only in the message text, so clients and the video-to-playlist skill would have to parse prose.
2. **Add optional `retryable`, `retry_after_seconds`, `details` and `request_id`.** `code` and `message` stay as §4.7 requires. `details` keys are fixed per code and hold only numbers, IDs and field names, never free text.

**Google rate limiting**
1. **Report it as `rate_limited`.** That would tell the user they sent too many requests, when it was youtube-sieve that hit Google's limit.
2. **Report it as `upstream_unavailable`.** `rate_limited` stays reserved for youtube-sieve's own per-caller limit (QM-8).

## Decision
Mapping option 3, object option 2 and rate-limit option 2. Also:

- Six new codes fill the gaps: `reauthorization_required`, `write_access_required`, `constraints_unsatisfiable`, `draft_expired`, `draft_not_confirmable` and `outcome_uncertain`. Further codes cover browser pages and internal failures: `session_required`, `request_rejected`, `playlist_limit_reached`, `playlist_write_rejected`, `service_unavailable` and `internal_error`.
- Errors reach callers through three channels: tool errors (`isError: true`), HTTP 401/403 for MCP authentication (never a tool error, so clients start sign-in, AC-4), and browser error pages.
- Partial and uncertain playlist outcomes are draft states reported by `playlist_status`, not errors of that tool.
- Messages come from fixed templates that say what to do next (US-2), and never include YouTube text, Google's messages, tokens or stack traces (SC-4, SC-10).
- Logs carry `request_id`, the code, the internal error class and Google's allow-listed reason, and never secrets or upstream bodies.

## Consequences
- One table to keep up to date: every new code or error type is added to `docs/design/errors.md` in the same pull request.
- Clients and skills can branch on `code` and `details` rather than message text.
- Services need an application error type and a mapping function per use case, built with the services in Stage 3.
- The extra fields go beyond the literal §4.7 example. If the SRS is revised, §4.7 should list them.
- Tests must cover each code's message and log line, including that a fixture token never appears in either (TQ-4).

## Related
- [[index]]
- [[decision-youtube-provider-interface]]
- [[decision-quota-budget-enforcement]]
- [[decision-browser-only-playlist-confirmation]]
- [[youtube-api-errors]]
