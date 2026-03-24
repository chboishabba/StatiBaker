# Ingestion Formats (Append-Only)

All inputs are append-only. Each line is timestamped and never rewritten.
Canonical encoding for machine logs is JSON Lines. Human logs remain Markdown.

## Journal (human)
Path: `logs/journal/YYYY-MM-DD.md`

Format (Markdown):
- Top block is freeform text
- Optional section headers for focus, constraints, reflections

## TODOs (human)
Path: `logs/todo/YYYY-MM-DD.md`

Format (Markdown):
- [ ] task description
- [x] completed task description
- Use `@blocker` tag in text for blocked items

## Agent logs (machine)
Path: `logs/agents/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-03T10:15:00Z",
  "agent": "metrics-bot",
  "type": "action",
  "text": "Drafted schema fields",
  "thread_id": "stati_schema",
  "severity": "info"
}

## Tool execution envelopes (machine)
Path: `logs/tools/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-19T03:12:44Z",
  "signal": "tool_execution",
  "tool": "openclaw",
  "execution_id": "uuid",
  "started_at": "2026-02-19T03:12:44Z",
  "ended_at": "2026-02-19T03:13:21Z",
  "host": {"hostname": "builder-07", "os": "linux", "arch": "x86_64"},
  "toolchain": {"openclaw_version": "0.4.2", "runtime": "python3.12"},
  "prompt": {"hash": "sha256:...", "length_chars": 1832},
  "declared_intent": {"label": "deploy hotfix", "supplied_by": "human"},
  "scope": {"filesystem": "read-only", "network": "internal-only"}
}

## Calendar (machine)
Path: `logs/calendar/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-03T15:30:00Z",
  "type": "commitment",
  "text": "Call with X",
  "duration_min": 30,
  "location": "remote"
}

## External commitments (machine)
Path: `logs/commitments/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-03-24T08:10:00Z",
  "signal": "external_commitment",
  "version": "external_commitment_event_v1",
  "source_system": "google",
  "source_kind": "google_tasks_task",
  "external_account_id": "acct:primary",
  "external_list_id": "tasks:default",
  "external_item_id": "task:123",
  "title": "Call Mum",
  "notes_excerpt": "created from voice capture",
  "status": "open",
  "due_at": "2026-03-25T09:00:00Z",
  "voice_origin": "tasks_command",
  "provenance": {"source": "google_tasks", "collected_at": "2026-03-24T08:10:01Z"}
}

Allowed `source_kind` values in v1:
- `google_tasks_task`
- `google_keep_list_item`

Allowed `status` values in v1:
- `open`
- `completed`
- `archived`
- `unknown`

These records preserve source truth only. SB may derive read-only projection
fields and completion candidates later, but it must not overwrite the source
status.

## Completion candidates (machine)
Path: `logs/task_candidates/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-03-24T10:30:00Z",
  "signal": "task_completion_candidate",
  "version": "task_completion_candidate_v1",
  "candidate_id": "cand:task:123:sha256:abc",
  "target_system": "google",
  "target_kind": "google_tasks_task",
  "external_item_id": "task:123",
  "proposed_action": "mark_complete",
  "candidate_status": "proposed",
  "reason_codes": ["title_token_match", "evidence_from_git"],
  "generator": "sb.dashboard.v1",
  "generated_at": "2026-03-24T10:30:00Z",
  "evidence_refs": [
    {"kind": "git_commit", "id": "abc1234", "source_path": "logs/git/2026-03-24.jsonl"}
  ]
}

Candidate rows are append-only proposal artifacts. They do not mutate
canonical task state and they do not imply that any downstream tool executed
the proposed action.

## Git activity (machine)
Path: `logs/git/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-03T11:02:00Z",
  "type": "commit",
  "repo": "StatiBaker",
  "hash": "abc1234",
  "summary": "Add schema and templates"
}

## Git branch history (machine)
Path: `logs/git_branch/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-08T06:00:55Z",
  "signal": "git_branch",
  "event_type": "branch_checkout",
  "repo": "StatiBaker",
  "ref": "HEAD",
  "from_ref": "main",
  "to_ref": "feature/dashboard",
  "commit_hash": "abc1234",
  "event_hash": "sha256:...",
  "provenance": {"source": "git_reflog", "collected_at": "2026-02-08T06:00:55Z"}
}

## Input activity (machine)
Path: `logs/input/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T11:32:14Z",
  "signal": "input",
  "focus_app": "org.gnome.Terminal",
  "keys": {"text": 0, "nav": 12, "control": 4},
  "modifiers": {"ctrl": 3, "alt": 1, "super": 0},
  "mouse": {"moves": 140, "clicks": 3, "scroll": 1}
}

## Window/app focus (machine)
Path: `logs/windows/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T11:35:12Z",
  "signal": "window_focus",
  "app_id": "org.gnome.Terminal",
  "window_title_hash": "sha256:...",
  "duration_ms": 120000,
  "workspace": 2,
  "provenance": {"source": "x11_focus", "collected_at": "2026-02-05T11:35:13Z"}
}

## System / journal events (machine)
Path: `logs/system/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T12:04:01Z",
  "signal": "system",
  "event": "network_down",
  "iface": "wlan0"
}

### macOS / Windows stubs
These platforms emit the same `signal: system` records with platform-specific
`event_id` values and no message content.

## Antivirus / endpoint status (machine)
Path: `logs/av/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T12:04:01Z",
  "signal": "av_status",
  "engine": "defender",
  "status": "ok",
  "signature_age_days": 1,
  "threat_count": 0,
  "provenance": {"source": "osquery", "collected_at": "2026-02-05T12:04:02Z"}
}

## Browser usage metadata (machine)
Path: `logs/browser/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T12:40:10Z",
  "signal": "browser_usage",
  "browser": "firefox",
  "domain_hash": "sha256:...",
  "duration_ms": 420000,
  "provenance": {"source": "browser_history", "collected_at": "2026-02-05T12:41:00Z"}
}

## Cloud audit feeds (machine)
Path: `logs/cloud/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T13:15:30Z",
  "signal": "cloud_audit",
  "provider": "google_drive",
  "event_type": "file_updated",
  "resource_id_hash": "sha256:...",
  "actor_hash": "sha256:...",
  "provenance": {"source": "google_audit", "collected_at": "2026-02-05T13:15:45Z"}
}

## Notes app metadata (machine)
Path: `logs/notes/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T14:10:00Z",
  "signal": "notes_meta",
  "app": "obsidian",
  "note_id_hash": "sha256:...",
  "event": "note_modified",
  "provenance": {"source": "fs_watcher", "collected_at": "2026-02-05T14:10:02Z"}
}

### NotebookLM metadata via connector
NotebookLM events are normalized into the same `notes_meta` signal with
`app: "notebooklm"`:

{
  "ts": "2026-02-08T10:00:00Z",
  "signal": "notes_meta",
  "app": "notebooklm",
  "notebook_id_hash": "sha256:...",
  "note_id_hash": "sha256:...",
  "event": "source_observed",
  "source_title": "Quarterly Review Notes",
  "source_type": "google_doc",
  "source_status": "ready",
  "source_url": "https://docs.google.com/...",
  "source_summary": "Short source-guide summary snippet...",
  "source_keywords": ["q1", "variance", "forecast"],
  "provenance": {"source": "notebooklm_meta", "collected_at": "2026-02-08T10:00:00Z"}
}

Optional NotebookLM event types and fields:
- `event: artifact_observed`
  - `artifact_id_hash`
  - `artifact_title`
  - `artifact_type`
  - `artifact_status`
  - `artifact_created_at`
- `event: notebook_observed`
  - `notebook_title`

Raw snapshot capture helper:
```bash
python scripts/capture_notebooklm_meta.py --output /tmp/notebooklm_meta.jsonl
python adapters/notebooklm_meta.py --input /tmp/notebooklm_meta.jsonl --output /tmp/notebooklm_notes.jsonl
```

Richer local UX capture (optional):
```bash
python scripts/capture_notebooklm_meta.py \
  --output /tmp/notebooklm_meta.jsonl \
  --with-source-guides \
  --source-snippet-chars 600
```

`run_day.sh` can ingest this directly with positional arg 20 (`NOTEBOOKLM_META_INPUT`).

## Media consumption metadata (machine)
Path: `logs/media/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-08T12:20:00Z",
  "signal": "media_consumption",
  "platform": "youtube",
  "event_type": "playback_observed",
  "item_id_hash": "sha256:...",
  "item_title_hash": "sha256:...",
  "channel_hash": "sha256:...",
  "consumed_seconds": 412,
  "content_duration_seconds": 920,
  "completion_ratio": 0.448,
  "provenance": {"source": "youtube_watch_stub", "collected_at": "2026-02-08T12:20:05Z"}
}

`run_day.sh` ingests this via positional arg 21 (`MEDIA_CONSUMPTION_INPUT`).
See `docs/media_connectors.md` for connector mappings and churn heuristics.

## Context-field overlays (machine)
Path: `logs/context/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-08T12:30:00Z",
  "signal": "context_field",
  "context_type": "living_environment",   // aquaponics | crops | medication | mood | inaturalist | pet_wearable | location_timeline | weather | ...
  "event_type": "snapshot_observed",
  "zone_id_hash": "sha256:...",
  "temp_c": 23.7,
  "humidity_pct": 51.2,
  "co2_ppm": 612,
  "provenance": {"source": "living_environment_simulator_stub", "collected_at": "2026-02-08T12:30:01Z"}
}

Adapter stubs for this signal:
- `adapters/living_environment_simulator_stub.py`
- `adapters/aquaponics_calculator_stub.py`
- `adapters/crops_stub.py`
- `adapters/medication_tracker_stub.py`
- `adapters/mood_self_report_stub.py`
- `adapters/inaturalist_stub.py`
- `adapters/pet_wearable_stub.py`

These records are non-authoritative context overlays only.

`run_day.sh` can append these via positional arg 22 (`CONTEXT_FIELD_APPEND_INPUT`).
Medication tracker raw JSONL can be passed via positional arg 23
(`MEDICATION_TRACKER_INPUT`) and will be normalized with
`adapters/medication_tracker_stub.py` before appending to the same path.

## Social feeds (machine)
Path: `logs/social/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T14:30:00Z",
  "signal": "social_feed",
  "platform": "bluesky",
  "event_type": "post_created",
  "post_id_hash": "sha256:...",
  "author_hash": "sha256:...",
  "thread_id_hash": "sha256:...",
  "provenance": {"source": "bluesky_audit", "collected_at": "2026-02-05T14:30:01Z"}
}

### Social audit redaction rules
See `docs/social_audit_redaction.md` for required hashing and forbidden fields.

## Power and lifecycle signals (machine)
Path: `logs/power/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T09:14:02Z",
  "signal": "power_state",
  "state": "suspend"
}

## Filesystem metadata (machine)
Path: `logs/fs/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T10:22:01Z",
  "signal": "fs_meta",
  "dir_hash": "sha256:...",
  "changes": 42,
  "scanned_files": 2000
}

## Network shape (machine)
Path: `logs/net/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T11:03:30Z",
  "signal": "net_shape",
  "bytes_in": 1200000,
  "bytes_out": 220000,
  "connections": 18,
  "protocols": {"tcp": 16, "udp": 2}
}

## Error surfaces (machine)
Path: `logs/errors/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T12:15:44Z",
  "signal": "error_surface",
  "kind": "exit_nonzero",
  "count": 3
}

## Time-anchor beacons (machine)
Path: `logs/anchors/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T13:00:00Z",
  "signal": "anchor",
  "kind": "calendar_reminder"
}

## Environment context (machine)
Path: `logs/env/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T06:00:00Z",
  "signal": "env",
  "kind": "timezone",
  "value": "UTC-05"
}

## Consent and redaction events (machine)
Path: `logs/consent/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T14:10:00Z",
  "signal": "consent",
  "state": "capture_disabled",
  "scope": "screen"
}

## CLI activity (machine)
Path: `logs/cli/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T12:11:09Z",
  "signal": "cli",
  "cmd": "git",
  "cwd_hash": "sha256:...",
  "exit": 1,
  "duration_ms": 430
}

## Pull request lifecycle (machine)
Path: `logs/pr/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-08T06:12:10Z",
  "signal": "pr_event",
  "event_type": "pr_commented",
  "repo": "ITIR-suite",
  "pr_number": 42,
  "pr_key_hash": "sha256:...",
  "actor_hash": "sha256:...",
  "state": "open",
  "provenance": {"source": "github_webhook", "collected_at": "2026-02-08T06:12:11Z"}
}

Direct connector:
```bash
python adapters/pr_events_github.py --date 2026-02-08 --repo owner/repo --output /tmp/pr_events.jsonl
```
When used from `run_day.sh` with positional arg 19, source becomes
`github_gh_cli`.

## Mobile status (machine)
Path: `logs/mobile/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T15:20:00Z",
  "signal": "mobile_status",
  "source": "adb",
  "device": "R58M123ABC",
  "battery": {"level": 42, "charging": true},
  "screen": "off",
  "interactive": false,
  "network": "wifi"
}

## System facts (osquery)
Path: `logs/system_facts/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T16:00:00Z",
  "signal": "system_fact",
  "source": "osquery",
  "name": "uptime",
  "row": {"total_seconds": "123456"}
}

## Metrics summaries (machine)
Path: `logs/metrics/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "t_start": "2026-02-05T10:00:00Z",
  "t_end": "2026-02-05T11:00:00Z",
  "signal": "metric_summary",
  "metric": "node_cpu_seconds_total",
  "summary": {"mean": 0.82, "p95": 0.97}
}

## Smart home status (machine)
Path: `logs/home/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-03T07:00:00Z",
  "type": "energy",
  "text": "No alerts",
  "severity": "info"
}
