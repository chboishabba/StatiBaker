# Social Audit Redaction Rules (Meta-Only)

SB ingests social feed metadata only. Content and identifiers are hashed before
ingest. These rules apply to Bluesky, Twitter/X, Mastodon, Reddit, and future
platforms.

## Required behavior
- Hash all platform identifiers (`post_id`, `uri`, `status_id`, `full_id`).
- Hash all author identifiers (`did`, `handle`, `acct`, `author`).
- Drop all content fields (post text, media URLs, titles, bodies).
- Keep event type and timestamps only.

## Forbidden fields
Reject input if any of the following appear in normalized output:
- `content`, `text`, `body`, `message`, `summary`
- `url`, `media_url`, `link`, `path`

## Allowed fields
- `ts`
- `platform`
- `event_type`
- `post_id_hash`
- `author_hash`
- `thread_id_hash`
- `provenance`

## Rationale
These feeds are high-risk for content leakage and retroactive inference. SB is
restricted to structural metadata only and must never embed content.

