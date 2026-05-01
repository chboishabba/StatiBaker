# OpenRecall Connector (Bounded Timeline + Deep Links)

This connector lets `StatiBaker` place OpenRecall activity on the daily
timeline without rebuilding OpenRecall's own browser/search UI.

## Purpose

Use OpenRecall as:
- a personal multi-machine observer lane
- a bounded activity-indicator source
- a drill-down target for screenshots and OCR history

Do not use this connector to:
- replace the OpenRecall web interface
- import full screenshots into SB
- promote OpenRecall rows into canonical SB authority
- merge identities or contexts automatically

## Current boundary

OpenRecall stays producer-owned for:
- capture
- OCR
- screenshot storage
- native search/history browsing
- entry-level deep inspection

StatiBaker consumes only:
- `captured_date`
- `timestamp`
- `entry_id`
- `device_id` / `session_id` when supplied
- app and window title
- bounded OCR preview
- screenshot presence/count
- stable source refs and deep links

This is a narrow personal-convenience exception to the broader "meta-only"
collector posture. It is allowed because the connector is:
- read-only
- explicitly local/personal-first
- bounded to preview-sized text
- non-authoritative

## Deep-link contract

The producer-owned link target is:

- `GET /entry/<entry_id>`

This route belongs to OpenRecall and should be used by external dashboards when
they want users to inspect one concrete capture entry.

## Adapter flow

The adapter reads a local `recall.db` and emits `openrecall_activity` JSONL for
one `captured_date`.

Example:

```bash
python adapters/openrecall_activity.py \
  --db-path ~/.local/share/openrecall/recall.db \
  --date 2026-05-01 \
  --device-id workstation-a \
  --session-id alice-home-2026-05-01 \
  --base-url http://127.0.0.1:8082 \
  --output /tmp/openrecall_activity.jsonl
```

Then `run_day.sh` can ingest that lane directly by passing:

- positional arg 26: `OPENRECALL_DB_PATH`
- positional arg 27: `OPENRECALL_BASE_URL`
- positional arg 28: `OPENRECALL_DEVICE_ID`
- positional arg 29: `OPENRECALL_SESSION_ID`

## Daily-bake role

OpenRecall feeds:
- timeline placement
- coarse activity indicators
- device/session transitions
- short preview snippets
- "open in OpenRecall" links

It does not feed:
- semantic verdicts
- risk/compliance labels
- cross-context identity fusion
- screenshot bytes in canonical SB state rows
