# 0002. Confirm playlist creation only in the user's browser

- **Status:** Accepted
- **Date:** 2026-11-22
- **Decision note:** [`brain/areas/decision-browser-only-playlist-confirmation.md`](../../brain/areas/decision-browser-only-playlist-confirmation.md)
- **Requirements:** FR-5, AC-10

## Context
FR-5 writes to the user's YouTube account only after explicit confirmation. Drafts are built from untrusted video metadata, which can contain prompt injection aimed at the AI client. An MCP server cannot tell whether a tool call was decided by a human or by the model, and the MCP specification asks for a human in the loop for consequential actions.

## Decision
- `create_playlist_draft` stores an immutable, owned, expiring draft and returns a `draft_id` and an **approval URL**.
- The playlist is created only when the **draft's owner confirms in their own browser** on a page served by youtube-sieve. The page shows the exact ordered videos, durations, total time and constraints. Confirmation requires a session for the same Google account, a CSRF token and a same-origin request.
- **No MCP tool, resource or prompt can confirm, approve or resume a draft.** MCP tokens are rejected on approval routes, and browser sessions are rejected on the MCP endpoint.
- The AI reads progress through a read-only `playlist_status` tool.

## Consequences
- Injected text in video metadata cannot trigger a write, and the server has evidence that a person approved it.
- Users take one extra step: opening a link.
- The server must serve and test a small set of web pages: sign-in, approval and status.
- The `video-to-playlist` skill must present the approval link and confirm creation only through `playlist_status`.
