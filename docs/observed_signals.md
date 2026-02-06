# Observed Signals (Meta-Only)

StatiBaker ingests **observed signals** as append-only JSONL. These signals are
structural metadata only and must not include content.

Core rules:
- Meta only: no free text, no document bodies, no message content.
- Hashes are allowed to reference content stored elsewhere.
- Provenance is required on every record.
- Absence is explicit (use `missing_*` fields, never implicit).

## Scope (current)
All sources below are supported as **metadata-only** streams. Linux is the first
implementation target; macOS and Windows are stubbed via normalized formats.
Cloud connectors are read-only audit feeds.

### Input activity (keyboard/mouse)
- Signal: `input`
- Required fields: `ts`, `focus_app`, `keys`, `mouse`, `provenance`
- Allowed fields:
  - `keys`: counts only (e.g., `text`, `nav`, `control`)
  - `mouse`: counts only (e.g., `moves`, `clicks`, `scroll`)

### Window/app focus
- Signal: `window_focus`
- Required fields: `ts`, `app_id`, `window_title_hash`, `provenance`
- Allowed fields: `duration_ms`, `workspace`, `display`

### Command history (CLI)
- Signal: `cli`
- Required fields: `ts`, `cmd_hash`, `cwd_hash`, `exit`, `provenance`
- Allowed fields: `duration_ms`, `shell` (no raw command lines)

### System event logs
- Signal: `system`
- Required fields: `ts`, `platform`, `event_id`, `severity`, `provenance`
- Allowed fields: `source`, `category`, `count`
- Linux source: journald adapter (curated event mapping)
- macOS/Windows: normalized event log format (stubbed adapters)

### Antivirus / endpoint status
- Signal: `av_status`
- Required fields: `ts`, `engine`, `status`, `provenance`
- Allowed fields: `signature_age_days`, `threat_count` (no threat names)

### Browser usage stats
- Signal: `browser_usage`
- Required fields: `ts`, `browser`, `domain_hash`, `duration_ms`, `provenance`
- Allowed fields: `profile_id`, `tab_count`

### Cloud audit feeds (Google Drive / MS365)
- Signal: `cloud_audit`
- Required fields: `ts`, `provider`, `event_type`, `resource_id_hash`, `provenance`
- Allowed fields: `actor_hash`, `ip_hash`, `device_hash`
- Read-only: no content, no file bodies

### Notes apps (Obsidian / Evernote)
- Signal: `notes_meta`
- Required fields: `ts`, `app`, `note_id_hash`, `event`, `provenance`
- Allowed fields: `vault_id_hash`, `notebook_id_hash`

### Social feeds (Bluesky, Twitter/X, Mastodon, Reddit)
- Signal: `social_feed`
- Required fields: `ts`, `platform`, `event_type`, `post_id_hash`, `provenance`
- Allowed fields: `author_hash`, `thread_id_hash`

## Platform notes
- Linux: journald + collectors emit normalized records.
- macOS/Windows: stub adapters emit normalized records from external exports.
- Cloud: audit feeds are read-only and must be hashed.

## Sample run_day wiring (meta-only)
Example using pre-exported JSONL files (no live collection):

```bash
./scripts/run_day.sh 2026-02-06 \
  . "" "" "" "" "" \
  /tmp/window_focus.jsonl \
  /tmp/input_activity.jsonl \
  /tmp/cli_meta.jsonl \
  /tmp/av_status.jsonl \
  /tmp/browser_usage.jsonl \
  /tmp/cloud_audit.jsonl \
  /tmp/notes_meta.jsonl \
  /tmp/social_feed.jsonl \
  /tmp/windows_event.jsonl \
  /tmp/macos_unified.jsonl
```

All inputs are optional; missing files are skipped with warnings.

## Provenance
Every record must include:
- `provenance.source` (collector or adapter name)
- `provenance.collected_at` (UTC ISO8601)
- Optional `provenance.policy_receipt` (if gated by consent)

## Forbidden fields (non-exhaustive)
Any of the following must be rejected:
- `text`, `content`, `body`, `message`, `summary`, `tokens`
- raw URLs, raw file paths, raw titles (use hashes)

## Storage
Observed signals are append-only JSONL under `logs/<signal>/YYYY-MM-DD.jsonl`.
See `INGESTION_FORMATS.md` for per-signal schemas.
