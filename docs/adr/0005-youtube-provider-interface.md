# 0005. Reach YouTube through separate read and write protocols with typed errors

- **Status:** Accepted
- **Date:** 2026-11-28
- **Decision note:** [`brain/areas/decision-youtube-provider-interface.md`](../../brain/areas/decision-youtube-provider-interface.md)
- **Design:** [`docs/design/provider-interface.md`](../design/provider-interface.md)
- **Requirements:** SE-6, IF-10, IF-11, TQ-4, TQ-6, DC-1, AC-2, AC-10, QM-2, QM-4, QM-9

## Context
ADR 0003 places YouTube behind a port, with an HTTP adapter and a test fake. IF-10 requires separate read and write protocols that can be replaced without changing services or tools. Public functions must use only the System's credential (AC-2), and users must be isolated (AC-10). ADR 0001 requires every workflow's worst-case cost to be estimated and reserved before any call. Google reports failures as an HTTP status and a reason string, with little retry guidance, and playlist writes go one video per request with no transaction.

## Decision
- **Three protocols in `youtube_sieve.ports.youtube`:** `YouTubeReader` for public data, `AccountReader` for the signed-in user's own data, and `PlaylistWriter` for `playlists.insert` and `playlistItems.insert` only.
- **A factory binds the credential when it creates each object:** the System's API key for the public reader, one user's token for the others. It checks scopes before any request. No method takes a credential.
- **Bounded calls:** methods take validated IDs and a `limit`, batch IDs in groups of 50, page internally and never expose page tokens. Each method has a fixed worst-case request count.
- **Metered requests:** every request is charged to an injected `QuotaMeter` before it is sent, and the meter refuses requests beyond the workflow's reservation.
- **Typed errors:** `QuotaExhausted`, `QuotaReservationExceeded`, `AuthRequired`, `ChannelRequired`, `NotFound`, `WriteRejected`, `Transient` (with `outcome_known`) and `BadRequest`. Missing items in batch results are data, not errors. Google's message text is never passed on.
- **Retries** only for idempotent reads, bounded and inside the reservation. Writes are never retried (IF-11). Playlists are always created private.
- **An in-memory fake** implements all three protocols with the same limits, batching, charges and errors, and one contract test suite runs against both the fake and the HTTP adapter.

## Consequences
- Services and tools are tested against the fake alone, including every TQ-4 failure and the zero-call check for TQ-6.
- An estimate that undercounts fails as `QuotaReservationExceeded` instead of overdrawing a budget.
- More interfaces than a single provider class; the HTTP adapter must keep retries within the reservation.
- Some API behaviours, such as how private videos appear in lists, are assumptions until recorded fixtures confirm them (open questions in the design document).
- The MCP-facing error codes are fixed by the error catalogue (#43), which maps these types.
