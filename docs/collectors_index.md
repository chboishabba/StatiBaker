# Collectors Index

This index lists all supported collectors/adapters and their expected inputs.
All collectors are **meta-only** and must not emit content.

## Core system collectors
- `adapters/gitlog.py` (git commits)
- `adapters/fs_meta.py` (filesystem metadata)
- `adapters/prometheus_summary.py` (metrics summaries)
- `adapters/journald.py` (Linux system events)
- `adapters/osquery_poll.py` (system facts)
- `adapters/wazuh_lifecycle.py` (Wazuh lifecycle events)

## Input / activity
- `adapters/input_activity.py` (keyboard/mouse counts)
- `adapters/window_focus.py` (app focus + title hash)
- `adapters/cli_meta.py` (CLI command hash + cwd hash)

## Security / endpoint
- `adapters/av_status.py` (AV/endpoint status summaries)

## Browser / apps
- `adapters/browser_usage.py` (domain hash + duration)
- `adapters/notes_meta.py` (Obsidian/Evernote metadata)

## Cloud audit feeds
- `adapters/cloud_audit.py` (Google Drive / MS365 audit logs)

## Social feed stubs
- `adapters/social_feed.py` (generic meta-only social events)
- `adapters/social_bluesky_stub.py`
- `adapters/social_twitter_stub.py`
- `adapters/social_mastodon_stub.py`
- `adapters/social_reddit_stub.py`

## OS stubs
- `adapters/windows_event_stub.py`
- `adapters/macos_unified_log_stub.py`

## Related docs
- `INGESTION_FORMATS.md`
- `docs/observed_signals.md`
- `docs/social_audit_redaction.md`
- `docs/social_stub_collectors.md`
