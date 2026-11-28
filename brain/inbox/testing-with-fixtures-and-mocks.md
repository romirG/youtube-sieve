---
title: Testing against recorded fixtures and mocks
type: research
status: inbox
created: 2026-11-28
authors: [sidtricoder]
tags: [testing, fixtures, mocking]
requirements: [TQ-1, TQ-2, TQ-4, TQ-5, IF-10, SC-10]
sources:
  - https://docs.pytest.org/en/stable/how-to/fixtures.html
  - https://lundberg.github.io/respx/
  - https://lundberg.github.io/respx/guide/
---

# Testing against recorded fixtures and mocks

## Summary
Code that calls an HTTP API can be tested without calling it, at two levels:

1. **A fake behind our own interface.** Services talk to a provider interface (IF-10). In tests, an in-memory fake that returns prepared data replaces the real provider. This tests business logic quickly and needs no HTTP at all.
2. **A mocked HTTP transport.** The real provider, which builds requests and parses responses, is tested by intercepting its HTTP calls and returning recorded responses. For the `httpx` client, RESPX does this: tests declare routes (method and URL) and the response each returns.

pytest supplies both through **fixtures**: reusable setup functions that a test requests by naming them as parameters.

## Key points

**pytest fixtures**
- Each test gets its own fixture result by default (`function` scope), so tests do not share state. Wider scopes (`class`, `module`, `package`, `session`) suit expensive resources, but state that tests change must be reset or recreated.
- A fixture may depend only on fixtures of the same or a wider scope.
- **`yield` fixtures** are the recommended way to clean up: code after `yield` runs at teardown, in reverse order of setup. Keep one state-changing action per fixture, so earlier steps still clean up if a later one fails.
- Fixtures in `conftest.py` are shared with every test in that folder and below; they should not be imported into test modules.
- **Parametrized fixtures** (`params=`) run each dependent test once per value. **Factory fixtures** return a function that builds data on demand.
- `autouse=True` applies a fixture without it being requested. It hides dependencies, so use it sparingly.
- Tests must not depend on execution order; fixtures should request their preconditions explicitly.

**RESPX for `httpx`**
- Routes are registered with `@respx.mock`, a context manager, or the `respx_mock` pytest fixture; a `base_url` option allows relative routes.
- **`assert_all_mocked` is on by default:** any request that does not match a route raises an error instead of reaching the network. Turned off, unmatched requests get an automatic 200.
- **`assert_all_called` is on by default:** a route declared but never called fails the test when it exits.
- A route returns, for example, `Response(200, json={...})`. A `side_effect` can raise an exception (any `httpx.HTTPError` subclass or other exception), or be a sequence that returns the next response or raises the next exception on each repeated call.
- Calls can be inspected through `route.called`, `route.call_count` and `route.calls.last.request`.
- `.pass_through()` lets a route reach the real network.

## Relevance to youtube-sieve
- **Two layers of tests, mirroring two layers of code** ([[decision-package-layout]]):
  - Service and MCP-tool tests use a **fake YouTube provider** that implements the same interface as the real one (IF-10, Liskov substitution in `AGENTS.md`). They can assert that a rejected workflow makes **zero** provider calls (TQ-6).
  - Provider tests (TQ-2) use **RESPX with recorded responses** shaped like the real API, covering pagination, missing fields, private or deleted IDs and every error group in [[youtube-api-errors]] (TQ-4): `quotaExceeded` mid-batch, `rateLimitExceeded`, `youtubeSignupRequired`, expired tokens. A sequence `side_effect` can model "succeeds 12 times, then `quotaExceeded`" for partial playlist writes ([[youtube-playlist-creation]]).
- **No live calls in CI (TQ-5).** Keep `assert_all_mocked` on and never use `.pass_through()` in the ordinary suite, so an unexpected request fails the test instead of spending quota. Live tests belong in a separate scheduled workflow with a fixed quota budget.
- **Fixture files are data, not secrets (SC-10).** Recorded responses must use synthetic IDs, titles and channel names, and no tokens or API keys. Strip `Authorization` headers and `key=` parameters before saving anything recorded from a real call.
- **Scopes:** function-scoped fakes and RESPX routers; at most a session-scoped loader for read-only fixture files, so tests stay independent.
- **Shared builders** go in `conftest.py` or helper modules, following the existing `tests/tools/vault_builder.py` pattern, instead of being copied between test files.
- **Open question:** RESPX is not yet a dependency. It should be added, and pinned, with the first provider PR, once `httpx` is chosen as the HTTP client in the architecture decision.

## Related
- [[youtube-api-methods]]
- [[index]]
