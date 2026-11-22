---
title: YouTube Data API quota costs
type: research
status: inbox
created: 2026-11-22
authors: [Devaang-Rastogi]
tags: [youtube-api, quota]
requirements: [TQ-6, FR-1, FR-2, FR-3, FR-4, FR-5]
sources:
  - https://developers.google.com/youtube/v3/determine_quota_cost
  - https://developers.google.com/youtube/v3/getting-started
  - https://developers.google.com/youtube/v3/docs/search/list
  - https://developers.google.com/youtube/v3/docs/search
  - https://developers.google.com/youtube/v3/docs/videos/list
  - https://developers.google.com/youtube/v3/docs/videos
  - https://developers.google.com/youtube/v3/docs/channels/list
  - https://developers.google.com/youtube/v3/docs/playlists/list
  - https://developers.google.com/youtube/v3/docs/playlistItems/list
---

# YouTube Data API quota costs

## Summary
Every YouTube Data API v3 request costs quota units, charged to the Google Cloud project that owns the API key or OAuth client, not to the end user. A project gets a fixed daily allowance by default. Google says the allowance is "subject to change", so we should not hardcode it as a fact about the API.

## Key points

**Default allowance (getting-started page)**
- **100 `search.list` calls** per day, in a bucket of their own.
- **100 `videos.insert` calls** per day, also separate. We never upload, so this does not apply to us.
- **10,000 units** per day shared by every other method.
- Quotas reset at **midnight Pacific Time**, not UTC and not at our own local midnight.
- A project that needs more can apply through Google's quota extension request form.

**Cost of the methods we plan to use (quota cost table)**

| Method | Cost | Used for |
|---|---|---|
| `search.list` | 1 call from the 100-a-day search bucket | Discovering candidate videos |
| `videos.list` | 1 unit | Details, statistics, durations |
| `channels.list` | 1 unit | Channel metadata |
| `playlists.list` | 1 unit | Reading the user's playlists |
| `playlistItems.list` | 1 unit | Reading playlist contents |
| `playlists.insert` | 50 units | Creating a playlist |
| `playlistItems.insert` | 50 units | Adding **one** video to a playlist |

**What each method does and how we will use it**

All the read methods below share some rules. Each takes a required `part` parameter listing which groups of fields to return. Paged results use `pageToken`, and responses carry `nextPageToken` and `prevPageToken`.

- **`search.list`: finding candidate videos (FR-1, FR-2)**
  - `part` can only be `snippet`. A result has `id.kind` plus `id.videoId`, `id.channelId` or `id.playlistId`, and a snippet with `publishedAt`, `channelId`, `title`, `description`, `thumbnails`, `channelTitle` and `liveBroadcastContent`.
  - Results have **no statistics and no duration**, so every candidate must then be looked up with `videos.list`.
  - Useful filters:
    - `q`: supports `-` for NOT and `|` (sent as `%7C`) for OR;
    - `type`: defaults to `video,channel,playlist`, so we set `video`;
    - `channelId`;
    - `publishedAfter` and `publishedBefore`: RFC 3339 dates;
    - `relevanceLanguage` and `regionCode`;
    - `safeSearch`: `moderate` by default;
    - `order`: `relevance` by default, or `date`, `rating`, `title`, `videoCount` or `viewCount`.
  - Video-only filters need `type=video`, or the call fails with `invalidSearchFilter`. These are `videoDuration`, `videoCaption`, `videoDefinition`, `videoEmbeddable`, `videoLicense`, `videoType` and `eventType`. `videoDuration` takes `short` (under 4 min), `medium` (4–20 min) or `long` (over 20 min).
  - `maxResults` is 0–50 with a default of 5, and the API may return fewer.
  - `pageInfo.totalResults` is only an approximation, so it must not be used to build page links.
  - Searching one channel with `type=video` returns at most 500 videos.
  - A non-default `order` may give a smaller or incomplete result set.
  - Basic searches work with an API key. `forMine` and similar filters need OAuth.
  - The page does not mention `relatedToVideoId`, so we cannot rely on a related-videos search.
- **`videos.list`: enriching and ranking videos (FR-3, FR-4)**
  - Takes exactly one filter:
    - `id`: a comma-separated list of video IDs;
    - `chart=mostPopular`: with `regionCode` and `videoCategoryId`;
    - `myRating`: `like` or `dislike`, needs OAuth, capped at the 1,000 most recent videos.
  - With `id`, `maxResults` and `pageToken` are not supported, so the batch size is however many IDs we put in one call.
  - The parts we need:
    - `snippet`: `publishedAt`, `channelId`, `title`, `description` (up to 5,000 bytes), `tags`, `categoryId`, `defaultAudioLanguage`.
    - `contentDetails`: `duration` as an ISO 8601 string such as `PT15M33S` (it can be about 1 s off), `definition` (`hd`/`sd`), `caption` (the string `"true"`/`"false"`), `licensedContent`.
    - `statistics`: `viewCount`, `likeCount`, `commentCount`, all strings. `dislikeCount` has been private since December 2021, and `favoriteCount` is always 0.
    - `status`: `privacyStatus`, `uploadStatus`, `embeddable`, `madeForKids`, `license`.
    - `topicDetails.topicCategories`: Wikipedia URLs.
  - Counts are strings and may be missing, so the parser must cope with absent values.
  - Owner-only parts (`fileDetails`, `processingDetails`, `suggestions`) return 403. We never request them.
- **`channels.list`: channel context for ranking and similar-channel features**
  - Takes exactly one filter: `id` (comma-separated), `forHandle` (a leading `@` is allowed), `forUsername`, or `mine` (OAuth).
  - Parts include `snippet`, `statistics`, `contentDetails`, `status` and `topicDetails`.
  - `contentDetails.relatedPlaylists.uploads` is the ID of the channel's uploads playlist, which lets us list a channel's videos through `playlistItems.list` at 1 unit per page instead of spending search calls.
  - `maxResults` is 0–50 with a default of 5.
- **`playlists.list`: reading the user's playlists before writing (FR-5)**
  - Takes exactly one filter: `channelId`, `id` (comma-separated) or `mine` (OAuth).
  - Parts are `snippet`, `status`, `contentDetails`, `id`, `player` and `localizations`.
  - We use it with `mine=true` to show existing playlists and avoid creating duplicates.
  - `maxResults` is 0–50 with a default of 5.
- **`playlistItems.list`: reading playlist contents**
  - Takes `playlistId` or `id`, plus an optional `videoId` that returns only items containing that video. `snippet` includes `position` and `resourceId.videoId`.
  - We use it to list a channel's uploads and to resume a half-finished playlist write by skipping videos already added ([[youtube-playlist-creation]]).
  - `maxResults` is 0–50 with a default of 5.
- **`playlists.insert` and `playlistItems.insert`: the only writes (FR-5)**
  - These create a playlist and add one video per call. Details are in [[youtube-playlist-creation]].

**Rules that change how we spend quota**
- **Invalid requests still cost at least one unit.** We should validate input before calling the API.
- **Each extra page costs the full price again.** Paging through search results spends one search call per page.
- The cost is **flat per method**. The docs do not tie it to which `part` values are requested. `part` and `fields` cut latency and bandwidth, but they do not save quota.
- Neither page says how many IDs fit in one `videos.list` call. The 50-ID batch limit in the root `AGENTS.md` should be checked against the `videos.list` reference before we rely on it.

## Relevance to youtube-sieve
- **Search is the scarce resource** (FR-1, FR-2). With about 100 searches a day per project, shared by all users, each search must be worth a lot. We should cache search results, always set `maxResults` explicitly (the default is only 5, the maximum 50), and then enrich results through cheap `videos.list` calls instead of more searches.
- **Batch enrichment.** One `videos.list` call can cover many IDs for one unit, so ranking (FR-3, FR-4) should collect IDs first and look them up in batches.
- **Playlist writes are costly** (FR-5). A playlist of *n* videos costs 50 + 50·*n* units. A 20-video playlist costs 1,050 units, about a tenth of the daily 10,000. The confirmation step should show the user the video count before writing, and the server should cap playlist size with a named constant.
- **Quota budgeting (TQ-6).** Costs, the daily limits and the reset time belong in configuration, not inline in code. A per-request budget can refuse an operation before it starts instead of failing half-way. Day boundaries in quota tracking must use Pacific Time.
- Because invalid requests are charged, input validation saves quota as well as giving better errors. What happens when quota runs out is covered in [[youtube-api-errors]].

## Related
- [[youtube-api-errors]]
- [[youtube-playlist-creation]]
- [[mcp-fundamentals]]
- [[index]]
