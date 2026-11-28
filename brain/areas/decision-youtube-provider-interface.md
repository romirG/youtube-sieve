---
title: YouTube provider interface with separate read and write protocols and typed errors
type: decision
status: distilled
created: 2026-11-28
authors: [Devaang-Rastogi]
tags: [decision, architecture, youtube-api, errors]
requirements: [SE-6, IF-10, IF-11, TQ-4, TQ-6, DC-1, AC-2, AC-10, QM-2, QM-4, QM-9]
---

# YouTube provider interface with separate read and write protocols and typed errors

**Status:** accepted
**Issue / PR:** #40
**ADR:** `docs/adr/0005-youtube-provider-interface.md`
**Design:** `docs/design/provider-interface.md`

## Context
[[decision-layered-architecture]] puts YouTube behind a port in `youtube_sieve.ports`, implemented by an HTTP adapter and by a fake for tests. IF-10 asks for separate read and write protocols, so that the provider or a test double can be swapped without touching services or MCP tools. Several facts from the research shape the interface:

- Search results have no duration or statistics, so every search is followed by a batched `videos.list` lookup ([[youtube-api-methods]]).
- List calls return at most 50 items per page, and each page costs the full price again ([[youtube-api-quota-costs]]).
- Playlists are written one video per request, with no transaction, so a write can stop half-way ([[youtube-playlist-creation]]).
- Google's errors come as an HTTP status plus a reason string, and the reference gives no retry guidance for the methods we use ([[youtube-api-errors]]).
- ADR 0001 requires a workflow's worst-case cost to be known and reserved before any call ([[decision-quota-budget-enforcement]]).
- Public functions must use only the System's own credential, and users must be isolated from each other (AC-2, AC-10).

## Options considered

**Shape of the interface**
1. **One provider class with every method.** Simple, but every service gets write access, including public read paths, and the fake has to implement everything for every test. It breaks interface segregation.
2. **Separate read and write protocols, with the credential passed to every method.** Satisfies IF-10, but any call site can pass the wrong user's token, and public reads could pick up a user token by mistake.
3. **Three small protocols: a public reader, an account reader and a playlist writer, created by a factory that binds the credential once.** A public path never holds a user token or a write method. The account reader adds only the "mine" calls. It costs one more interface.

**Paging**
1. **Expose page tokens to services.** Flexible, but every service re-implements the paging loop, and the number of requests, and so the quota estimate, depends on service code.
2. **Methods take a `limit` and page internally.** The worst-case request count follows from `limit` alone, memory stays bounded, and results report `truncated` so services can disclose it (FR-3.2).

**Errors**
1. **Let HTTP errors propagate.** Services would have to read status codes and Google's JSON, which breaks the layer rules and makes the fake hard to write.
2. **Result objects instead of exceptions.** Explicit, but verbose for the many calls where any failure simply ends the workflow.
3. **A small hierarchy of typed exceptions, with missing items returned as data.** Services catch only what they handle. A private or deleted video in a batch is normal data, not a failure.

## Decision
Shape option 3, paging option 2 and error option 3. In summary (full contract in `docs/design/provider-interface.md`):

- `YouTubeProviderFactory` hands out a `YouTubeReader` (API key), an `AccountReader` (one user's token) or a `PlaylistWriter` (one user's token with the management scope). It checks scopes before any request.
- Methods take validated IDs and bounded limits, batch IDs in groups of 50, page internally and never expose page tokens.
- Every request is charged to an injected `QuotaMeter` before it is sent. The meter can refuse a request that goes beyond the workflow's reservation, so an estimate that undercounts fails loudly.
- Errors are `QuotaExhausted`, `QuotaReservationExceeded`, `AuthRequired`, `ChannelRequired`, `NotFound`, `WriteRejected`, `Transient` (with `outcome_known` for uncertain writes) and `BadRequest`. They carry Google's reason code for logs, never Google's message text.
- Idempotent reads are retried a bounded number of times; writes never are (IF-11).
- Playlists are always created private; the write interface has no privacy parameter (FR-5.15).
- The fake implements all three protocols with the same limits, batching, charges and error behaviour. Search results in the fake are programmed by the test. One contract test suite runs against both the fake and the HTTP adapter.

## Consequences
- Services and MCP tools can be tested against the fake only, including every TQ-4 failure and the "zero calls when rejected" check for TQ-6.
- The worst-case cost of each method is a simple formula, so quota plans are easy to build.
- Three protocols and a factory are more code than one class, and the HTTP adapter must keep its retries inside the reservation.
- Several behaviours are assumptions until recorded fixtures confirm them, such as how private videos appear in each list. They are listed as open questions in the design document.
- The final MCP error codes are decided by the error catalogue (#43). The provider's error types are designed to map onto it.

## Related
- [[index]]
- [[decision-layered-architecture]]
- [[decision-tech-stack]]
- [[decision-quota-budget-enforcement]]
- [[decision-browser-only-playlist-confirmation]]
