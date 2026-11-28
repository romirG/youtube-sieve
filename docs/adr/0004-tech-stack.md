# 0004. Build on MCP Python SDK 2.3, FastAPI and httpx2

- **Status:** Accepted
- **Date:** 2026-11-28
- **Decision note:** [`brain/areas/decision-tech-stack.md`](../../brain/areas/decision-tech-stack.md)
- **Spike:** branch `spike/38-mcp-sdk`, not merged
- **Requirements:** DC-4, IO-1, AC-3, AC-6, IF-4, SC-5, SL-1, TQ-2, TQ-5

## Context
DC-4 requires Python 3.12, FastAPI and the official MCP Python SDK, with pinned dependencies. It was not known whether the SDK supports the current stateless MCP revision (2026-07-28), or which HTTP client the YouTube provider should use and how to test it without the network. A one-day spike answered both.

## Decision
| Concern | Choice | Pin |
|---|---|---|
| MCP protocol, tools, resources, prompts, resource-server auth | `mcp` | `2.3.0` |
| Web framework and server | `fastapi`, `uvicorn` | `0.165.0`, `0.54.0` |
| Outbound HTTP | `httpx2`, already a dependency of `mcp` | `2.16.2` |
| HTTP adapter tests | injected `httpx2.MockTransport` with recorded responses | built in |
| MCP tool tests | in-process `mcp.Client(server)` with fake ports | built in |

- MCP runs in **stateless HTTP mode with JSON responses**, mounted in FastAPI beside the web routes. The SDK's session manager runs in FastAPI's lifespan.
- Every tool returns a **Pydantic model**, giving an output schema and structured content (IF-4). Input schemas reject bad arguments before tools run (SC-5).
- HTTP adapters receive their `httpx2.AsyncClient` from the composition root (ADR 0003); **RESPX is not used**, because it does not intercept `httpx2`.
- **Client ID Metadata Documents are implemented by us** in the SDK's authorization-provider hooks, because the SDK supports them only on the client side (AC-6, IF-7).
- Exact pins and a lock file arrive with the walking skeleton (#47).

## Consequences
- One HTTP library in the process; mocking by injection cannot silently fall through to the network.
- Part of authorization (fetching and validating metadata documents, and advertising them) is our code and needs its own tests.
- SDK 2.x changes quickly; upgrades are deliberate, tested PRs.
- The fixtures research note's RESPX advice must be corrected (#51).
