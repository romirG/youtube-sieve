# Error catalogue

- **Status:** Accepted
- **Issue:** #43
- **Decision note:** [`brain/areas/decision-error-catalogue.md`](../../brain/areas/decision-error-catalogue.md)
- **Requirements:** IF-4, US-2, TQ-4, SC-10, SRS §4.7, AC-4, AC-5, AC-10, AC-11, AC-12, IF-5, IF-6, QM-2, QM-8, QM-9, RL-2, FR-1.1, FR-1.2, FR-5.6, FR-5.9, FR-5.10

This document lists every error youtube-sieve can report, how each one reaches the caller, what message the user sees and whether trying again can help. It also maps the domain errors and the YouTube provider errors ([provider-interface.md](provider-interface.md) §8) to these codes, and says what is logged. Implementation is out of scope.

## 1. Where errors are reported

Errors reach a caller in one of three ways. Each code in the catalogue belongs to exactly one of them.

| Channel | Used for | Form |
|---|---|---|
| **Tool error** | Anything that goes wrong inside an MCP tool call | A tool result with `isError: true`. Its structured content is the error object (section 2), and its text content is the same `message`, so clients that ignore structured content still show it (IF-4). |
| **HTTP authentication error** | Missing or bad MCP credentials, before any tool runs | HTTP 401 or 403 with a `WWW-Authenticate: Bearer` header, as the MCP authorization specification and RFC 6750 require (AC-4, AC-5, IF-5). Never a tool error: clients only start sign-in on a real 401. |
| **Browser error page** | Sign-in, confirmation and other browser routes (IF-9) | An HTML page with a plain-language explanation and a link to the next step, with the matching HTTP status. API clients never receive HTML. |

OAuth endpoints (authorize, token, register, revoke) return the standard error codes of RFC 6749 and RFC 7009 (`invalid_request`, `invalid_grant`, `invalid_client`, `unauthorized_client`, `unsupported_grant_type`, `invalid_scope`, `access_denied`). They follow those specifications and are not repeated here. MCP protocol faults that come before a tool runs, such as an unknown method or malformed JSON-RPC, use the JSON-RPC error codes the SDK returns.

## 2. The error object

SRS §4.7 requires `{"error": {"code": "…", "message": "…"}}`. youtube-sieve adds three optional fields so that QM-2, QM-8 and US-2 can be met without parsing the message:

```json
{
  "error": {
    "code": "quota_budget_exceeded",
    "message": "This request needs more of today's YouTube quota than is left. Try again after 00:00 Pacific Time, or ask for fewer videos.",
    "retryable": "after_reset",
    "retry_after_seconds": 18000,
    "details": {
      "estimated": {"units": 1051, "search_calls": 1},
      "remaining": {"units": 600, "search_calls": 4},
      "budget": "account",
      "resets_at": "2026-11-29T08:00:00Z"
    },
    "request_id": "c0a8012e-7f3b-4b0e-9d1a-5e6f2b9c4d10"
  }
}
```

| Field | Always present | Meaning |
|---|---|---|
| `code` | yes | One of the codes in section 3. Stable: clients and skills may branch on it. |
| `message` | yes | Plain-language text that says what happened and what to do next (US-2). Built from a fixed template; never contains text from YouTube, from Google's error responses, tokens or stack traces (SC-4, SC-10). |
| `retryable` | yes | `no`, `yes` (the same request may work later) or `after_reset` (only after the quota day resets). |
| `retry_after_seconds` | when known | Seconds to wait before retrying. |
| `details` | for some codes | Structured facts, limited to the keys listed for that code below. Values are numbers, booleans, IDs, field names or timestamps, never free text. |
| `request_id` | yes | A random ID that also appears in the server log, so a user can report a problem without sharing any personal data. |

## 3. Catalogue

`Tool` means a tool error, `Page` a browser error page, `HTTP` an authentication error. Every code used in `docs/srs.md` appears here once, marked **SRS**.

### 3.1 Input and lookup

| Code | Channel | When | Message pattern (with the next step) | Retryable | `details` |
|---|---|---|---|---|---|
| `invalid_input` **SRS** | Tool | An argument fails validation: wrong type, out of range, malformed URL or ID, bad dates (FR-1.1, FR-2.1, FR-4.6, SC-5) | "`{field}` is not valid: `{rule}`. Change it and try again." For example: "`video` must be a YouTube link or an 11-character video ID." | no | `field`, `rule` (a fixed rule name, e.g. `max_length`) |
| `not_found` **SRS** | Tool, Page | The video, channel, playlist or draft does not exist, is private or deleted, or belongs to another user (FR-1.2, AC-10) | "That `{kind}` could not be found. It may be private or deleted. Check the link, or try a different one." | no | `kind` (`video`, `channel`, `playlist`, `draft`) |

`not_found` for another user's draft must be identical to `not_found` for a draft that never existed: same message, same `details`, same status (AC-10).

### 3.2 Quota and rate limits

| Code | Channel | When | Message pattern | Retryable | `details` |
|---|---|---|---|---|---|
| `quota_budget_exceeded` **SRS** | Tool | The workflow's estimated cost does not fit a remaining budget; rejected before any YouTube call (QM-2, ADR 0001) | "This request needs more of today's YouTube quota than is left. Try again after `{reset time}`, or ask for fewer videos." | after_reset | `estimated`, `remaining`, `budget` (`global`, `public` or `account`), `resets_at` |
| `quota_exceeded` **SRS** | Tool, Page | Google reported the project's daily allowance as used up (QM-9) | "YouTube's daily limit for this service has been reached. Try again after `{reset time}`." | after_reset | `pool` (`units` or `search_calls`), `resets_at` |
| `rate_limited` **SRS** | Tool | The caller sent more requests per minute than allowed (QM-8) | "Too many requests. Wait `{n}` seconds and try again." | yes | `limit_per_minute` |

`rate_limited` is youtube-sieve's own limit on callers. When **Google** rate-limits youtube-sieve, that is reported as `upstream_unavailable` (section 3.5), because the caller did nothing wrong.

QM-8 also applies to MCP requests that are not tool calls (for example `tools/list`). Those are refused with HTTP 429 and a `Retry-After` header, because there is no tool result to put the error in.

### 3.3 Sign-in and permissions

| Code | Channel | When | Message pattern | Retryable | `details` |
|---|---|---|---|---|---|
| `invalid_token` | HTTP 401 | No MCP credentials for a Signed-in operation, or credentials that are invalid, expired, revoked or for another audience, on any operation (AC-4, AC-5) | No message body. The `WWW-Authenticate` header carries `error="invalid_token"` when credentials were sent, and the protected-resource metadata URL, so the client starts sign-in. | — | — |
| `insufficient_scope` **SRS** | HTTP 403 | The MCP token lacks youtube-sieve's own scope for personal data (IF-5, IF-8) | `WWW-Authenticate: Bearer error="insufficient_scope", scope="…"` | — | — |
| `reauthorization_required` | Tool | The MCP token is valid, but the user's Google grant has expired or been revoked, and refreshing it failed; includes the 7-day expiry in Testing status (AC-11) | "Your YouTube connection has expired. Sign in again at `{link}`, then repeat the request." | no | `sign_in_url` |
| `write_access_required` | Tool | A playlist action needs the YouTube management scope, and the user did not grant it at sign-in (AC-8) | "To create playlists, allow youtube-sieve to manage your YouTube playlists at `{link}`. Reading your data still works." | no | `grant_url` |
| `channel_required` **SRS** | Tool, Page | The Google account has no YouTube channel, or its channel is closed or suspended; writes only (AC-12) | "Your Google account needs an active YouTube channel to create playlists. Create one at youtube.com, then try again. Recommendations and analysis still work." | no | `reason` (`no_channel`, `closed`, `suspended`) |
| `session_required` | Page 401 | A browser route that needs the user's browser session was opened without one (FR-5.12) | "Sign in to continue." with a sign-in link that returns to this page | — | — |
| `request_rejected` | Page 403 | A browser request failed a CSRF, same-origin or session-owner check, or carried an MCP access token (FR-5.13, FR-5.14, SC-8) | "This action could not be confirmed. Open the link from your AI client again, and confirm on that page." | no | — |

The page deliberately does not say which check failed, so it gives nothing away to an attacker.

### 3.4 Playlists and drafts

| Code | Channel | When | Message pattern | Retryable | `details` |
|---|---|---|---|---|---|
| `constraints_unsatisfiable` | Tool | No selection meets the constraints; nothing is drafted (FR-5.6) | "No set of videos meets all your constraints. The limiting one is `{constraint}`. Change it if you want a playlist." | no | `binding_constraint` (a field name, e.g. `max_seconds`) |
| `not_enough_videos` **SRS** | Tool, Page | Fewer videos meet the constraints than the requested count (FR-5.6), or too few remain when the draft is re-verified before writing (FR-5.9) | "Only `{found}` videos meet your constraints, but you asked for `{requested}`. Lower the count, change `count_mode`, or relax a constraint." | no | `found`, `requested` |
| `draft_expired` | Page | The draft is more than 30 minutes old and was never confirmed (FR-5.10) | "This draft has expired. Ask your AI client to make the playlist again." | no | — |
| `draft_not_confirmable` | Page | The draft is already being written, complete or in an uncertain state, so it cannot be confirmed again (FR-5.16, FR-5.18) | "This playlist has already been created, or is being created. Check its status in your AI client." | no | `state` |
| `playlist_limit_reached` | Page | YouTube refused to create the playlist because the channel has the maximum number of playlists | "Your channel already has the maximum number of playlists YouTube allows. Delete one in YouTube, then confirm again." | no | — |
| `playlist_write_rejected` | Page | YouTube refused a write for another reason: the playlist is full or the write is forbidden. The draft becomes *partial* (FR-5.16) | "YouTube stopped accepting videos for this playlist after `{n}` of `{total}`. The videos already added are kept. You can try to add the rest." | no | `inserted`, `total` |
| `outcome_uncertain` | Page | The connection to YouTube failed during a write, so it is unknown whether it succeeded. The draft becomes *uncertain*; nothing is retried (FR-5.18) | "We could not tell whether YouTube saved the last change. Check the playlist in your YouTube account before doing anything else." | no | `playlist_url` (when known) |

Partial and uncertain outcomes are also reported by the `playlist_status` tool (FR-5.19). There they are **states of the draft, not errors**: the status call itself succeeds, and its result carries the state and the same code as a `reason`.

### 3.5 Upstream and internal

| Code | Channel | When | Message pattern | Retryable | `details` |
|---|---|---|---|---|---|
| `upstream_unavailable` **SRS** | Tool, Page | Google is down, slow or rate-limiting youtube-sieve, after the provider's bounded retries (RL-2, IF-11) | "YouTube is not responding right now. Try again in a few minutes." | yes | — |
| `service_unavailable` | Tool, Page, HTTP 503 | youtube-sieve's own database or another required service is unreachable; the System fails closed (DC-5) | "youtube-sieve is temporarily unavailable. Try again in a few minutes." | yes | — |
| `internal_error` | Tool, Page, HTTP 500 | A bug: a malformed request to YouTube, an unparseable response, a quota estimate that undercounted, invalid configuration, or any unexpected exception | "Something went wrong on our side. Try again; if it keeps happening, report request `{request_id}`." | yes | — |

## 4. Mapping errors to codes

All mapping happens in **one place: the services layer.** Services catch domain and provider errors and raise an application error carrying a code from this catalogue. Transports only turn that application error into a tool error, an HTTP response or a page (ADR 0003: transports contain no business logic). Anything a service does not catch becomes `internal_error`.

### 4.1 Provider errors

Every error type from [provider-interface.md](provider-interface.md) §8:

| Provider error | Code | Notes |
|---|---|---|
| `QuotaExhausted(pool)` | `quota_exceeded` | Also marks that pool exhausted until the reset (QM-9). |
| `QuotaReservationExceeded` | `internal_error` | The estimate undercounted. Logged as a bug. |
| `AuthRequired(EXPIRED)` | `reauthorization_required` | Only after the accounts service has tried one token refresh and the retried read still fails. |
| `AuthRequired(REVOKED)` | `reauthorization_required` | No refresh attempt. |
| `AuthRequired(INSUFFICIENT_SCOPE)` from a `PlaylistWriter` | `write_access_required` | |
| `AuthRequired(INSUFFICIENT_SCOPE)` from an `AccountReader` | `reauthorization_required` | The read-only scope is requested at sign-in (AC-8), so missing it means consent was incomplete. |
| `ChannelRequired(NO_CHANNEL / CLOSED / SUSPENDED)` | `channel_required` | `details.reason` gives which. Reads stay available. |
| `NotFound` for the target of the request (seed video, channel, playlist) | `not_found` | |
| `NotFound` for one video in `add_video` | none | The video is skipped and reported in the draft's result (FR-5.9). |
| IDs in `Lookup.missing` | none, or `not_found` for the seed | Missing candidates are excluded silently (FR-1.6, FR-2.5); a missing seed is `not_found` (FR-1.2). |
| `WriteRejected(PLAYLIST_LIMIT)` | `playlist_limit_reached` | |
| `WriteRejected(PLAYLIST_FULL or FORBIDDEN)` | `playlist_write_rejected` | Draft becomes *partial*. |
| `WriteRejected(DUPLICATE_ITEM)` | none | The video is already in the playlist, so it counts as added (resume, FR-5.17). |
| `Transient(outcome_known=True)` | `upstream_unavailable` | Includes Google's `rateLimitExceeded` once retries are used up. |
| `Transient(outcome_known=False)` | `outcome_uncertain` | Only possible on writes. Draft becomes *uncertain*. |
| `BadRequest` | `internal_error` | |

### 4.2 Domain errors

From `youtube_sieve.domain.errors`:

| Domain error | Code | Notes |
|---|---|---|
| `InvalidDurationError` from parsing a **YouTube response** | `internal_error` | The adapter reports this as `BadRequest(malformed_response)`; it never reaches services as a domain error. A video whose duration cannot be parsed is treated as having no duration and excluded where a duration is needed. |
| `InvalidDurationError` from **user input** | `invalid_input` | Only if a tool ever accepts ISO 8601 durations. SRS tools take whole seconds (FR-5.1). |
| `InvalidSimilarityConfigError` | `internal_error` | Configuration is checked at startup, so this should stop the server from starting rather than reach a user. |
| `InvalidDocumentError` | `internal_error` | A service passed a malformed document: a bug. |
| `InvalidQuotaError` | `internal_error` | Invalid quota configuration or a programming error. |
| `QuotaDecision` with shortfalls (`check_budgets`) | `quota_budget_exceeded` | Not an exception. `details` come from the first shortfall and the budget's reset time. |

New domain errors must be added to this table in the same pull request.

## 5. What is logged

Every error writes one structured log line. It **contains**:

- `request_id`, `code`, and the tool or route name;
- the internal error class (for example `Transient`) and, for provider errors, Google's `reason` string from the allow-list in the provider design;
- for signed-in callers, a keyed hash of the Google subject, not the subject itself;
- counts and IDs that are already in `details`.

It **never contains** (SC-10, PV-1, SRS §4.7):

- access tokens, refresh tokens, ID tokens, API keys, authorization codes, PKCE verifiers, CSRF tokens or session cookies;
- Google's error `message` text or any response body;
- titles, descriptions, tags or other text from YouTube;
- full request URLs with query strings, headers, or tool arguments other than validated IDs and numbers;
- stack traces in anything a user can see. Stack traces go to the server log only, for `internal_error`.

Tests check that the error object and the log line for each code contain none of the above. A fixture token placed in a failing request must not appear in either (TQ-4, SC-10).

## 6. Rules for adding a code

1. Add it to section 3 with its channel, message pattern, retryability and `details` keys, and map its sources in section 4, in the same pull request as the code that raises it.
2. Codes are lower-case `snake_case`, describe the problem rather than the HTTP status, and are never renamed once released (clients may depend on them).
3. Prefer an existing code with `details` over a new code that differs only in detail.
4. Every message says what the user can do next (US-2), and never includes untrusted text.
