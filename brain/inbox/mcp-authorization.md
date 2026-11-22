---
title: MCP authorization for HTTP servers
type: research
status: inbox
created: 2026-11-22
authors: [sidtricoder]
tags: [mcp, oauth, security]
requirements: [AC-3, AC-4, AC-5, AC-6, AC-10]
sources:
  - https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization.md
  - https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md
---

# MCP authorization for HTTP servers

## Summary
MCP defines how a client gets permission to call a protected server over HTTP, using a chosen subset of **OAuth 2.1**. Authorization is optional overall. HTTP servers *should* follow this specification, and stdio servers should instead read credentials from their environment.

There are three roles. The **MCP server** is an OAuth *resource server*: it accepts and checks access tokens. The **MCP client** is the OAuth *client*. The **authorization server** signs the user in and issues tokens; it can be hosted with the MCP server or separately.

## Key points

**Discovery: how a client finds out where to sign in**
1. The client calls the server without a token. The server replies **401** with a `WWW-Authenticate: Bearer` header containing `resource_metadata="<url>"` and, ideally, `scope="..."` listing the scopes needed.
2. The server **must** publish **Protected Resource Metadata** (RFC 9728) at that URL, naming its authorization server(s) and `scopes_supported`.
3. The client reads the authorization server's metadata through RFC 8414 or OpenID Connect Discovery. Authorization servers must offer at least one; clients must support both.

**Client registration: how the client gets a client ID**
Three options:
- **Client ID Metadata Documents** (should be supported): the client ID is an HTTPS URL to a JSON document describing the client.
- **Pre-registration.**
- **Dynamic Client Registration** (RFC 7591), now **deprecated** and kept only for authorization servers that lack metadata documents.

**The sign-in flow**
- The flow is the authorization code flow with **PKCE**.
- The client must send a `resource` parameter (RFC 8707) with the server's canonical URI, e.g. `https://mcp.example.com/mcp`, in both the authorization and the token request.
- The client checks the `iss` value in the response against the expected issuer (RFC 9207) to prevent mix-up attacks.

**Using tokens**
- The token goes in `Authorization: Bearer <token>` on **every** HTTP request, and **never** in the URL query string.
- The server **must** validate each token, including that its **audience** is this server. Invalid or expired tokens get **401**.
- **No token passthrough:** a server must only accept tokens issued for itself, and must not accept or forward any other token.

**Scopes**
- Clients should request the least privilege: the scopes from the 401 challenge, otherwise `scopes_supported`.
- If a token lacks a scope at run time, the server should answer **403** with `error="insufficient_scope"`, the required `scope` and `resource_metadata`. It should list *all* scopes the operation needs in one challenge.
- The client then re-authorizes for the union of old and new scopes ("step-up") and retries a limited number of times.
- Servers should not advertise `offline_access`; refresh tokens are the client's concern.

**Public and protected tools together:** the tools specification allows `tools/list` to depend on the authorization presented with each request, so one endpoint can serve anonymous callers some tools and signed-in callers more.

## Relevance to youtube-sieve
- **Two separate OAuth relationships.** Our server is the *resource server* for MCP clients, and also a *client* of Google for YouTube access. Because of the no-passthrough rule, an MCP access token must never be forwarded to Google, and Google tokens must never be accepted as MCP tokens. The server keeps each user's Google grant itself and looks it up from the verified MCP token. This underpins user isolation (AC-10).
- **Public versus signed-in** (AC-3, AC-4, AC-5): similar videos and channels can work without a token, while recommendations, engagement analysis and playlist writes answer 401 with the metadata URL and scopes, and 403 `insufficient_scope` when a write scope is missing.
- **SRS update needed:** AC-6 currently names dynamic client registration. The current specification prefers Client ID Metadata Documents and marks dynamic registration as deprecated, so AC-6 should require metadata documents and keep dynamic registration only for compatibility.
- **Tests to plan:** 401 with a correct `WWW-Authenticate`; wrong-audience and expired tokens rejected even on public tools; tokens in query strings rejected; a 403 step-up challenge.
- Google-side scopes and token expiry are covered separately (issue #14).

## Related
- [[mcp-fundamentals]]
- [[index]]
