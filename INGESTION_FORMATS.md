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

## System / journal events (machine)
Path: `logs/system/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-05T12:04:01Z",
  "signal": "system",
  "event": "network_down",
  "iface": "wlan0"
}

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
