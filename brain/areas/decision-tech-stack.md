---
title: Tech stack - MCP Python SDK 2.3, FastAPI and httpx2
type: decision
status: distilled
created: 2026-11-28
authors: [sidtricoder]
tags: [decision, architecture, mcp, python]
requirements: [DC-4, IO-1, AC-3, AC-6, IF-4, IF-12, SC-5, TQ-2, TQ-5]
sources:
  - https://pypi.org/project/mcp/
  - https://pypi.org/project/httpx2/
  - https://lundberg.github.io/respx/guide/
  - spikes/38-mcp-sdk/README.md (branch spike/38-mcp-sdk)
---

# Tech stack: MCP Python SDK 2.3, FastAPI and httpx2

**Status:** accepted
**Issue / PR:** #38
**ADR:** `docs/adr/0004-tech-stack.md`
**Spike:** branch `spike/38-mcp-sdk` (not merged), commit `a69b5b6`

## Context
DC-4 names Python 3.12, pinned dependencies, FastAPI and the official MCP Python SDK. Two questions were open:
- Does the SDK support the current, stateless MCP revision 2026-07-28 ([[mcp-fundamentals]])?
- Which HTTP client should the YouTube provider use, and how is it tested without the network ([[testing-with-fixtures-and-mocks]])?

The layers are fixed by [[decision-layered-architecture]]: the SDK and FastAPI belong only in `transport`, the HTTP client only in `adapters.youtube` and `adapters.identity`.

## What the spike found
Tried `mcp==2.3.0`, `fastapi==0.165.0`, `uvicorn==0.54.0` and `httpx2==2.16.2` on Python 3.12:

- **Protocol:** the SDK's latest protocol version is `2026-07-28`, and it still serves the older `initialize`-based revisions. A raw `tools/list` carrying only the `_meta` version and capabilities, with no `initialize`, was answered with HTTP 200. This matches AC-3 in SRS v0.2.
- **Hosting:** `MCPServer.streamable_http_app(stateless_http=True, json_response=True)` mounts inside FastAPI next to `GET /health`. The SDK's session manager has to run inside FastAPI's lifespan.
- **Tool contract:** a typed Pydantic return value gives the tool an `outputSchema` and `structured_content` (IF-4). Wrong argument types are rejected by schema validation before the tool runs (SC-5). An exception inside a tool comes back as an `is_error` result rather than a protocol error, as [[mcp-fundamentals]] recommends.
- **Testing:** `Client(server)` connects in-process, so tool tests need no network.
- **Authorization:** the SDK provides Protected Resource Metadata, the 401 challenge, a token-verifier hook, and authorize/token/register/revoke routes behind a provider interface. **Client ID Metadata Documents are supported only on the client side.** The server neither fetches them nor advertises them in its metadata, so AC-6's preferred registration method has to be built by us.
- **HTTP client:** the SDK depends on **`httpx2`** (BSD-3-Clause), the successor to `httpx`, not on `httpx` itself. `httpx2.MockTransport` works when injected through the client's constructor. **RESPX does not intercept `httpx2`:** a request "mocked" with RESPX went to the real network, and only the sandbox proxy stopped it.
- **API style:** SDK 2.x results use snake_case attributes (`is_error`, `structured_content`).

## Options considered
1. **MCP SDK 2.3 + FastAPI + `httpx2`, with tests through an injected `httpx2.MockTransport`.** One HTTP library shared with the SDK; mocking by dependency injection, so a test cannot fall back to the network by accident.
2. **MCP SDK 2.3 + FastAPI + `httpx` with RESPX,** as planned in the fixtures research. This means two HTTP libraries in one process, and RESPX's global patching is exactly what failed to cover `httpx2`.
3. **Another MCP framework, or hand-written JSON-RPC.** DC-4 asks for the official SDK, and the spike shows it covers the protocol and most of authorization.

## Decision
Option 1:

| Concern | Choice | Pin |
|---|---|---|
| MCP protocol, tools, resources, prompts, resource-server auth | `mcp` (official Python SDK) | `2.3.0` |
| Web framework for routes and approval pages | `fastapi`, served by `uvicorn` | `0.165.0`, `0.54.0` |
| Outbound HTTP (YouTube, Google identity) | `httpx2` (already required by `mcp`) | `2.16.2` |
| Data models at the boundaries | `pydantic` v2 (required by both) | through the lock file |
| Tests for HTTP adapters | `httpx2.MockTransport` injected into the adapter, with recorded JSON responses | built in |
| Tests for MCP tools | in-process `mcp.Client(server)` against services with fake ports | built in |

Ground rules that follow from the spike:
- Run MCP in **stateless HTTP mode with JSON responses** (SL-1). No server-side MCP sessions.
- **Every tool returns a Pydantic model,** so clients get an output schema and structured content.
- **Adapters receive their `httpx2.AsyncClient` from the composition root;** tests pass one built on `MockTransport`. RESPX is not used.
- **Client ID Metadata Document support is our own code:** fetching and validating the document (IF-7) inside the SDK provider's `get_client` hook, and advertising it in the authorization-server metadata. It is designed in #44.
- Dependencies get exact pins and a **lock file** (DC-4) when they are first added, with the walking skeleton (#47).

## Consequences
- The research note [[testing-with-fixtures-and-mocks]] recommends RESPX, which does not work with `httpx2`. It should be corrected when that note is refined (#51).
- A test-wide guard that fails any real socket connection is still worth adding (for example `pytest-socket`), so a missed injection cannot reach the network (TQ-5).
- The SDK moves fast (2.x, protocol 2026-07-28). Upgrades should be deliberate PRs that re-run the MCP tests.
- Authorization will build on the SDK's provider interfaces instead of a separate OAuth library.

## Related
- [[index]]
- [[mcp-authorization]]
