#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE="${1:-$(date +%F)}"
REPO_PATH="${2:-$ROOT_DIR}"
SNAPSHOTS_PATH="${3:-}"
FS_DIR="${4:-}"
PROM_BASE_URL="${5:-}"
OSQUERY_QUERIES="${6:-}"
PROM_QUERIES="${7:-}"
WINDOW_FOCUS_INPUT="${8:-}"
INPUT_ACTIVITY_INPUT="${9:-}"
CLI_META_INPUT="${10:-}"
AV_STATUS_INPUT="${11:-}"
BROWSER_USAGE_INPUT="${12:-}"
CLOUD_AUDIT_INPUT="${13:-}"
NOTES_META_INPUT="${14:-}"
SOCIAL_FEED_INPUT="${15:-}"
WINDOWS_EVENT_INPUT="${16:-}"
MACOS_EVENT_INPUT="${17:-}"

if [[ -n "$WINDOW_FOCUS_INPUT" && ! -f "$WINDOW_FOCUS_INPUT" ]]; then
  echo "warn: WINDOW_FOCUS_INPUT not found: $WINDOW_FOCUS_INPUT" >&2
  WINDOW_FOCUS_INPUT=""
fi
if [[ -n "$INPUT_ACTIVITY_INPUT" && ! -f "$INPUT_ACTIVITY_INPUT" ]]; then
  echo "warn: INPUT_ACTIVITY_INPUT not found: $INPUT_ACTIVITY_INPUT" >&2
  INPUT_ACTIVITY_INPUT=""
fi
if [[ -n "$CLI_META_INPUT" && ! -f "$CLI_META_INPUT" ]]; then
  echo "warn: CLI_META_INPUT not found: $CLI_META_INPUT" >&2
  CLI_META_INPUT=""
fi
if [[ -n "$AV_STATUS_INPUT" && ! -f "$AV_STATUS_INPUT" ]]; then
  echo "warn: AV_STATUS_INPUT not found: $AV_STATUS_INPUT" >&2
  AV_STATUS_INPUT=""
fi
if [[ -n "$BROWSER_USAGE_INPUT" && ! -f "$BROWSER_USAGE_INPUT" ]]; then
  echo "warn: BROWSER_USAGE_INPUT not found: $BROWSER_USAGE_INPUT" >&2
  BROWSER_USAGE_INPUT=""
fi
if [[ -n "$CLOUD_AUDIT_INPUT" && ! -f "$CLOUD_AUDIT_INPUT" ]]; then
  echo "warn: CLOUD_AUDIT_INPUT not found: $CLOUD_AUDIT_INPUT" >&2
  CLOUD_AUDIT_INPUT=""
fi
if [[ -n "$NOTES_META_INPUT" && ! -f "$NOTES_META_INPUT" ]]; then
  echo "warn: NOTES_META_INPUT not found: $NOTES_META_INPUT" >&2
  NOTES_META_INPUT=""
fi
if [[ -n "$SOCIAL_FEED_INPUT" && ! -f "$SOCIAL_FEED_INPUT" ]]; then
  echo "warn: SOCIAL_FEED_INPUT not found: $SOCIAL_FEED_INPUT" >&2
  SOCIAL_FEED_INPUT=""
fi
if [[ -n "$WINDOWS_EVENT_INPUT" && ! -f "$WINDOWS_EVENT_INPUT" ]]; then
  echo "warn: WINDOWS_EVENT_INPUT not found: $WINDOWS_EVENT_INPUT" >&2
  WINDOWS_EVENT_INPUT=""
fi
if [[ -n "$MACOS_EVENT_INPUT" && ! -f "$MACOS_EVENT_INPUT" ]]; then
  echo "warn: MACOS_EVENT_INPUT not found: $MACOS_EVENT_INPUT" >&2
  MACOS_EVENT_INPUT=""
fi

RUN_DIR="$ROOT_DIR/runs/$DATE"
LOG_DIR="$RUN_DIR/logs/git"
OUT_DIR="$RUN_DIR/outputs"

mkdir -p "$LOG_DIR" "$OUT_DIR"
export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"

GIT_LOG_PATH="$LOG_DIR/$DATE.jsonl"
python "$ROOT_DIR/adapters/gitlog.py" --repo "$REPO_PATH" --date "$DATE" --output "$GIT_LOG_PATH"

if [[ -n "$FS_DIR" ]]; then
  FS_LOG_DIR="$RUN_DIR/logs/fs"
  FS_LOG_PATH="$FS_LOG_DIR/$DATE.jsonl"
  FS_STATE_PATH="$ROOT_DIR/runs/fs_state.json"
  mkdir -p "$FS_LOG_DIR"
  python "$ROOT_DIR/adapters/fs_meta.py" --dir "$FS_DIR" --state "$FS_STATE_PATH" --output "$FS_LOG_PATH"
fi

if [[ -n "$PROM_BASE_URL" ]]; then
  METRICS_LOG_DIR="$RUN_DIR/logs/metrics"
  METRICS_LOG_PATH="$METRICS_LOG_DIR/$DATE.jsonl"
  QUERIES_PATH="${PROM_QUERIES:-$ROOT_DIR/configs/prometheus_queries.json}"
  mkdir -p "$METRICS_LOG_DIR"
  if python "$ROOT_DIR/adapters/prometheus_summary.py" \
    --base-url "$PROM_BASE_URL" \
    --date "$DATE" \
    --queries "$QUERIES_PATH" \
    --output "$METRICS_LOG_PATH"; then
    PROM_STATUS="ok"
  else
    PROM_STATUS="failed"
    : >"$METRICS_LOG_PATH"
  fi
fi

if [[ -n "$OSQUERY_QUERIES" ]]; then
  FACTS_LOG_DIR="$RUN_DIR/logs/system_facts"
  FACTS_LOG_PATH="$FACTS_LOG_DIR/$DATE.jsonl"
  mkdir -p "$FACTS_LOG_DIR"
  if python "$ROOT_DIR/adapters/osquery_poll.py" \
    --queries "$OSQUERY_QUERIES" \
    --output "$FACTS_LOG_PATH"; then
    OSQUERY_STATUS="ok"
  else
    OSQUERY_STATUS="failed"
    : >"$FACTS_LOG_PATH"
  fi
fi

if [[ -n "$INPUT_ACTIVITY_INPUT" ]]; then
  INPUT_LOG_DIR="$RUN_DIR/logs/input"
  INPUT_LOG_PATH="$INPUT_LOG_DIR/$DATE.jsonl"
  mkdir -p "$INPUT_LOG_DIR"
  python "$ROOT_DIR/adapters/input_activity.py" --input "$INPUT_ACTIVITY_INPUT" --output "$INPUT_LOG_PATH"
fi

if [[ -n "$WINDOW_FOCUS_INPUT" ]]; then
  WINDOW_LOG_DIR="$RUN_DIR/logs/windows"
  WINDOW_LOG_PATH="$WINDOW_LOG_DIR/$DATE.jsonl"
  mkdir -p "$WINDOW_LOG_DIR"
  python "$ROOT_DIR/adapters/window_focus.py" --input "$WINDOW_FOCUS_INPUT" --output "$WINDOW_LOG_PATH"
fi

if [[ -n "$CLI_META_INPUT" ]]; then
  CLI_LOG_DIR="$RUN_DIR/logs/cli"
  CLI_LOG_PATH="$CLI_LOG_DIR/$DATE.jsonl"
  mkdir -p "$CLI_LOG_DIR"
  python "$ROOT_DIR/adapters/cli_meta.py" --input "$CLI_META_INPUT" --output "$CLI_LOG_PATH"
fi

if [[ -n "$AV_STATUS_INPUT" ]]; then
  AV_LOG_DIR="$RUN_DIR/logs/av"
  AV_LOG_PATH="$AV_LOG_DIR/$DATE.jsonl"
  mkdir -p "$AV_LOG_DIR"
  python "$ROOT_DIR/adapters/av_status.py" --input "$AV_STATUS_INPUT" --output "$AV_LOG_PATH"
fi

if [[ -n "$BROWSER_USAGE_INPUT" ]]; then
  BROWSER_LOG_DIR="$RUN_DIR/logs/browser"
  BROWSER_LOG_PATH="$BROWSER_LOG_DIR/$DATE.jsonl"
  mkdir -p "$BROWSER_LOG_DIR"
  python "$ROOT_DIR/adapters/browser_usage.py" --input "$BROWSER_USAGE_INPUT" --output "$BROWSER_LOG_PATH"
fi

if [[ -n "$CLOUD_AUDIT_INPUT" ]]; then
  CLOUD_LOG_DIR="$RUN_DIR/logs/cloud"
  CLOUD_LOG_PATH="$CLOUD_LOG_DIR/$DATE.jsonl"
  mkdir -p "$CLOUD_LOG_DIR"
  python "$ROOT_DIR/adapters/cloud_audit.py" --input "$CLOUD_AUDIT_INPUT" --output "$CLOUD_LOG_PATH"
fi

if [[ -n "$NOTES_META_INPUT" ]]; then
  NOTES_LOG_DIR="$RUN_DIR/logs/notes"
  NOTES_LOG_PATH="$NOTES_LOG_DIR/$DATE.jsonl"
  mkdir -p "$NOTES_LOG_DIR"
  python "$ROOT_DIR/adapters/notes_meta.py" --input "$NOTES_META_INPUT" --output "$NOTES_LOG_PATH"
fi

if [[ -n "$SOCIAL_FEED_INPUT" ]]; then
  SOCIAL_LOG_DIR="$RUN_DIR/logs/social"
  SOCIAL_LOG_PATH="$SOCIAL_LOG_DIR/$DATE.jsonl"
  mkdir -p "$SOCIAL_LOG_DIR"
  python "$ROOT_DIR/adapters/social_feed.py" --input "$SOCIAL_FEED_INPUT" --output "$SOCIAL_LOG_PATH"
fi

if [[ -n "$WINDOWS_EVENT_INPUT" ]]; then
  SYS_LOG_DIR="$RUN_DIR/logs/system"
  SYS_LOG_PATH="$SYS_LOG_DIR/$DATE.windows.jsonl"
  mkdir -p "$SYS_LOG_DIR"
  python "$ROOT_DIR/adapters/windows_event_stub.py" --input "$WINDOWS_EVENT_INPUT" --output "$SYS_LOG_PATH"
fi

if [[ -n "$MACOS_EVENT_INPUT" ]]; then
  SYS_LOG_DIR="$RUN_DIR/logs/system"
  SYS_LOG_PATH="$SYS_LOG_DIR/$DATE.macos.jsonl"
  mkdir -p "$SYS_LOG_DIR"
  python "$ROOT_DIR/adapters/macos_unified_log_stub.py" --input "$MACOS_EVENT_INPUT" --output "$SYS_LOG_PATH"
fi

DEFAULT_SNAPSHOTS="$ROOT_DIR/tests/fixtures/snapshots.json"
if [[ -z "$SNAPSHOTS_PATH" && -f "$DEFAULT_SNAPSHOTS" ]]; then
  SNAPSHOTS_PATH="$DEFAULT_SNAPSHOTS"
fi

LEDGER_PATH="$OUT_DIR/activity_ledger.json"
SESSIONIZER_RUNTIME_PATH="$OUT_DIR/sessionizer_runtime_ms.txt"
if [[ -n "$SNAPSHOTS_PATH" && -f "$SNAPSHOTS_PATH" ]]; then
  start_ms=$(date +%s%3N)
  python -m sb.activity.sessionize "$SNAPSHOTS_PATH" --output "$LEDGER_PATH"
  end_ms=$(date +%s%3N)
  echo $((end_ms - start_ms)) >"$SESSIONIZER_RUNTIME_PATH"
else
  python - <<'PY' >"$LEDGER_PATH"
import json
import sys

ledger = {
    "activity_events": [],
    "provenance": {
        "algorithm": "sb.sessionize.v0",
        "input_hash": "",
        "policy_receipt": "",
    },
}
json.dump(ledger, sys.stdout, indent=2, sort_keys=True)
PY
  echo 0 >"$SESSIONIZER_RUNTIME_PATH"
fi

BRIEF_PATH="$OUT_DIR/daily_brief.md"
RETRO_PATH="$OUT_DIR/retrospective.md"
STATE_PATH="$OUT_DIR/state.json"
DRIFT_PATH="$OUT_DIR/drift.json"

ROOT_DIR="$ROOT_DIR" \
DATE="$DATE" \
GIT_LOG_PATH="$GIT_LOG_PATH" \
BRIEF_PATH="$BRIEF_PATH" \
RETRO_PATH="$RETRO_PATH" \
STATE_PATH="$STATE_PATH" \
DRIFT_PATH="$DRIFT_PATH" \
PROM_STATUS="${PROM_STATUS:-}" \
OSQUERY_STATUS="${OSQUERY_STATUS:-}" \
python - <<'PY'
import json
import os

from sb.compress import apply_phase2_compression
from sb.drift import compute_drift
from sb.fold import apply_minimal_fold, previous_date
from sb.observed_ingest import load_observed_events

date = os.environ["DATE"]
git_log_path = os.environ["GIT_LOG_PATH"]
brief_path = os.environ["BRIEF_PATH"]
retro_path = os.environ["RETRO_PATH"]
state_path = os.environ["STATE_PATH"]
drift_path = os.environ["DRIFT_PATH"]
prom_status = os.environ.get("PROM_STATUS")
osquery_status = os.environ.get("OSQUERY_STATUS")

entries = []
with open(git_log_path, "r", encoding="utf-8") as handle:
    for line in handle:
        if not line.strip():
            continue
        entries.append(json.loads(line))

repo = entries[0]["repo"] if entries else "unknown"
commit_count = len(entries)
commit_ids = [entry["hash"][:7] for entry in entries[:5]]
commit_list = ", ".join(commit_ids) if commit_ids else "none"
uptime_note = None

facts_path = os.path.join(os.environ["ROOT_DIR"], "runs", date, "logs", "system_facts", f"{date}.jsonl")
if os.path.exists(facts_path):
    with open(facts_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("name") == "uptime":
                total_seconds = data.get("row", {}).get("total_seconds")
                if total_seconds is not None:
                    uptime_note = f"- System uptime (seconds): {total_seconds}"
                break

events = []
for entry in entries:
    short_hash = entry["hash"][:7]
    events.append(
        {
            "id": f"git-{short_hash}",
            "ts": entry["ts"],
            "source": "git",
            "type": "commit",
            "text": f"commit {short_hash} ({entry['repo']})",
        }
    )

observed_events = load_observed_events(
    os.path.join(os.environ["ROOT_DIR"], "runs", date, "logs")
)
events.extend(observed_events)

state = {
    "date": date,
    "day_state": "active",
    "human_energy": "medium",
    "constraints": [],
    "alerts": [],
    "priorities": ["Review git activity", "Update SB outputs"],
    "open_questions": [],
    "blocked_tasks": [],
    "carryover_threads": [],
    "agent_actions": [],
    "agent_permissions": {"autonomous_runs": False, "write_actions": False},
    "sources": [{"kind": "git", "uri": git_log_path}],
    "events": events,
}

prev_date = previous_date(date)
prev_state_path = os.path.join(os.environ["ROOT_DIR"], "runs", prev_date, "outputs", "state.json")
prev_state = {}
if os.path.exists(prev_state_path):
    with open(prev_state_path, "r", encoding="utf-8") as handle:
        prev_state = json.load(handle)

state = apply_minimal_fold(prev_state, state, date)
state = apply_phase2_compression(state)
drift = compute_drift(state)
drift_payload = {
    "date": date,
    **drift,
}
labels = list(state.get("labels", []))
if prom_status == "failed":
    labels.append("prometheus_missing")
if osquery_status == "failed":
    labels.append("osquery_missing")
state["labels"] = labels

def _bullet_list(items, empty="- None"):
    if not items:
        return [empty]
    return [f"- {item}" for item in items]

carryover_lines = _bullet_list(state.get("carryover_threads", []))
carryover_new = ", ".join(state.get("carryover_new_threads", [])) or "none"
carryover_resolved = ", ".join(state.get("carryover_resolved_threads", [])) or "none"
window_counts = state.get("carryover_window_counts", [])
window_lines = [
    f"- <= {entry['window_days']} days: {entry['count']}" for entry in window_counts
] or ["- None"]

brief = "\n".join(
    [
        "# Daily Brief (Generated)",
        f"Date: {date}",
        "",
        "## Context snapshot",
        "- Yesterday ended at: unknown",
        "- Energy: medium",
        "- Constraints: none",
        "- Alerts: none",
        "",
        "## Top priorities (max 5)",
        "1. Review git activity",
        "2. Update SB outputs",
        "",
        "## Carryover threads",
        *carryover_lines,
        f"- New today: {carryover_new}",
        f"- Resolved today: {carryover_resolved}",
        "",
        "## Carryover window counts",
        *window_lines,
        "",
        "## Open questions",
        "- None",
        "",
        "## Agent actions queued",
        "- None",
        "",
        "## Schedule anchors",
        "- None",
        "",
        "## Notes",
        f"- Git repo: {repo}",
        f"- Commits captured: {commit_count} ({commit_list})",
        uptime_note or "- System uptime (seconds): unknown",
        "",
    ]
)

retro = "\n".join(
    [
        "# Retrospective (Generated)",
        f"Date: {date}",
        "",
        "## Completed",
        f"- Git commits captured: {commit_count}",
        "",
        "## Partial / blocked",
        "- None",
        "",
        "## Missed",
        "- None",
        "",
        "## Drift signals",
        "- None",
        "",
        "## Tomorrow setup",
        "- Review carryover threads",
        "",
    ]
)

with open(brief_path, "w", encoding="utf-8") as handle:
    handle.write(brief)
with open(retro_path, "w", encoding="utf-8") as handle:
    handle.write(retro)
with open(state_path, "w", encoding="utf-8") as handle:
    json.dump(state, handle, indent=2, sort_keys=True)
with open(drift_path, "w", encoding="utf-8") as handle:
    json.dump(drift_payload, handle, indent=2, sort_keys=True)
PY

echo "Wrote:"
echo "  $BRIEF_PATH"
echo "  $RETRO_PATH"
echo "  $STATE_PATH"
echo "  $DRIFT_PATH"
echo "  $LEDGER_PATH"
echo "  $SESSIONIZER_RUNTIME_PATH"
