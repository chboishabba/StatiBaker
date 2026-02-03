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

## Smart home status (machine)
Path: `logs/home/YYYY-MM-DD.jsonl`

Each line (JSON):
{
  "ts": "2026-02-03T07:00:00Z",
  "type": "energy",
  "text": "No alerts",
  "severity": "info"
}
