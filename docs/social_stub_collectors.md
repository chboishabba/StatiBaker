# Social Stub Collectors (Meta-Only)

These collectors normalize exported or audit JSONL into SB meta-only records.
They do **not** fetch content and must not emit raw identifiers.

## Bluesky
Adapter: `adapters/social_bluesky_stub.py`

Input fields (JSONL):
- `ts` (ISO8601)
- `uri` or `post_id`
- `did` or `author`
- `event_type`
- `thread_id_hash` (optional)
- `collected_at`

Output signal: `social_feed` with `platform=bluesky`.

## Twitter/X
Adapter: `adapters/social_twitter_stub.py`

Input fields (JSONL):
- `ts`
- `tweet_id` or `post_id`
- `handle` or `author`
- `event_type`
- `thread_id_hash` (optional)
- `collected_at`

Output signal: `social_feed` with `platform=twitter`.

## Mastodon
Adapter: `adapters/social_mastodon_stub.py`

Input fields (JSONL):
- `ts`
- `status_id` or `post_id`
- `acct` or `author`
- `event_type`
- `thread_id_hash` (optional)
- `collected_at`

Output signal: `social_feed` with `platform=mastodon`.

## Reddit
Adapter: `adapters/social_reddit_stub.py`

Input fields (JSONL):
- `ts`
- `post_id` or `full_id`
- `author`
- `event_type`
- `thread_id_hash` (optional)
- `collected_at`

Output signal: `social_feed` with `platform=reddit`.

## Running a stub
Example:

```bash
python adapters/social_bluesky_stub.py \
  --input /tmp/bluesky_export.jsonl \
  --output /tmp/social_feed.jsonl
```

See `docs/social_audit_redaction.md` for hashing and forbidden fields.
