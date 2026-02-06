#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="${1:-$(date +%F)}"

./scripts/run_day.sh "$DATE" \
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
