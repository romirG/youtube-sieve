---
title: Layered ports-and-adapters architecture with fixed dependency rules
type: decision
status: distilled
created: 2026-11-28
authors: [sidtricoder]
tags: [decision, architecture]
requirements: [SE-2, SE-3, SE-6, MT-1, IF-10, SL-1, PT-1]
---

# Layered ports-and-adapters architecture with fixed dependency rules

**Status:** accepted
**Issue / PR:** #39
**ADR:** `docs/adr/0003-layered-architecture.md`

## Context
Only the pure domain layer exists ([[decision-package-layout]]). Next come the YouTube provider, storage, Google sign-in, the MCP endpoint and the browser approval pages. Without agreed boundaries, framework and API code leaks into business logic, which then cannot be tested with fakes. The project's own rules already demand separation:

- IF-10 and SE-6: YouTube is reached only through a provider interface, replaceable by a test double without changing ranking logic, services or MCP tools.
- MT-1: SOLID, constructor injection, and no business logic in the MCP transport layer.
- SL-1: the application tier is stateless; shared state lives in the database.
- PT-1: all configuration comes from environment variables.
- `AGENTS.md` *Code and design*: transport, business logic and external services in separate layers; dependencies injected, never created inside logic.

## Options considered
1. **Classic three tiers** (presentation → business → data access). Familiar, but business logic depends directly on the data-access and API code below it, so tests need a database or the network, and IF-10's substitutable provider is not natural.
2. **Vertical feature slices only** (one package per feature, each with its own handlers, logic and API calls). Keeps a feature's code together, but the provider, quota ledger and authorization are shared by every feature and would be duplicated or tangled across slices.
3. **Ports and adapters (hexagonal), arranged in layers.** Business logic depends on small interfaces (*ports*); concrete code that talks to YouTube, Google or the database (*adapters*) implements them; transports (MCP, web) only call services. One *composition root* wires adapters into services. Features are grouped by module inside the services layer, which keeps option 2's locality without duplicating shared infrastructure.

## Decision
Option 3, with six layers and one-way dependencies:

| Layer | Package | Holds | May import |
|---|---|---|---|
| Domain | `youtube_sieve.domain` | pure rules: durations, similarity, quota arithmetic, playlist selection, draft states | standard library only |
| Ports | `youtube_sieve.ports` | `typing.Protocol` interfaces: YouTube read and write, stores (drafts, quota ledger, grants, tokens, cache), clock, identity | domain |
| Services | `youtube_sieve.services` | use cases, one module per feature group: `discovery` (FR-1, FR-2, FR-6), `insights` (FR-3, FR-4), `playlists` (FR-5, FR-7), `accounts` (AC-9 to AC-11), `quota_guard` (QM) | domain, ports |
| Adapters | `youtube_sieve.adapters.*` | `youtube` (HTTP client), `storage` (database), `identity` (Google OAuth), `crypto`; each implements ports | domain, ports, their own third-party library |
| Transports | `youtube_sieve.transport.mcp`, `youtube_sieve.transport.web` | MCP tools, resources and prompts; HTTP routes, authorization checks, approval pages; input validation and error mapping only | services, domain types, ports types |
| Composition root | `youtube_sieve.bootstrap`, `youtube_sieve.config` | reads settings from the environment once, builds adapters, injects them into services and transports | everything |

Rules, checkable in review:

- **Nothing imports a layer above it.** Domain never imports ports; services never import adapters, transports, FastAPI, the MCP SDK, the HTTP client or a database driver.
- **Transports contain no business logic** (MT-1): they validate input, call one service method, and map results and errors.
- **Only the composition root constructs adapters.** Services receive ports through their constructors.
- **Settings are one typed object**, loaded from the environment in `config` and passed in; no module reads `os.environ` itself (PT-1).
- **No shared state in modules** (SL-1): no module-level caches or singletons holding user data; per-request state lives in function scope, shared state behind store ports.
- **Each adapter has a fake** in `tests/fakes/` implementing the same port, so services are tested without network or database (Liskov substitution, [[testing-with-fixtures-and-mocks]]).

## Consequences
- Services and domain are fully testable with fakes; adapters are tested separately against mocked HTTP or a test database.
- A few more modules and interfaces than a flat design, which is the cost of IF-10 and MT-1.
- The tech stack (#38), the provider interface (#40), storage (#42) and the walking skeleton (#47) fill in their layers under these rules.
- Import rules should be enforced by a CI check instead of review alone (#57).
- Existing code needs no move: `youtube_sieve.domain` is already the innermost layer.

## Related
- [[index]]
- [[decision-quota-budget-enforcement]]
- [[decision-browser-only-playlist-confirmation]]
