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

RUN_DIR="$ROOT_DIR/runs/$DATE"
LOG_DIR="$RUN_DIR/logs/git"
OUT_DIR="$RUN_DIR/outputs"

mkdir -p "$LOG_DIR" "$OUT_DIR"

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
  python "$ROOT_DIR/adapters/prometheus_summary.py" \
    --base-url "$PROM_BASE_URL" \
    --date "$DATE" \
    --queries "$QUERIES_PATH" \
    --output "$METRICS_LOG_PATH"
fi

if [[ -n "$OSQUERY_QUERIES" ]]; then
  FACTS_LOG_DIR="$RUN_DIR/logs/system_facts"
  FACTS_LOG_PATH="$FACTS_LOG_DIR/$DATE.jsonl"
  mkdir -p "$FACTS_LOG_DIR"
  python "$ROOT_DIR/adapters/osquery_poll.py" \
    --queries "$OSQUERY_QUERIES" \
    --output "$FACTS_LOG_PATH"
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

ROOT_DIR="$ROOT_DIR" \
DATE="$DATE" \
GIT_LOG_PATH="$GIT_LOG_PATH" \
BRIEF_PATH="$BRIEF_PATH" \
RETRO_PATH="$RETRO_PATH" \
STATE_PATH="$STATE_PATH" \
python - <<'PY'
import json
import os

from sb.fold import apply_minimal_fold, previous_date

date = os.environ["DATE"]
git_log_path = os.environ["GIT_LOG_PATH"]
brief_path = os.environ["BRIEF_PATH"]
retro_path = os.environ["RETRO_PATH"]
state_path = os.environ["STATE_PATH"]

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
        "- None",
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

with open(brief_path, "w", encoding="utf-8") as handle:
    handle.write(brief)
with open(retro_path, "w", encoding="utf-8") as handle:
    handle.write(retro)
with open(state_path, "w", encoding="utf-8") as handle:
    json.dump(state, handle, indent=2, sort_keys=True)
PY

echo "Wrote:"
echo "  $BRIEF_PATH"
echo "  $RETRO_PATH"
echo "  $STATE_PATH"
echo "  $LEDGER_PATH"
echo "  $SESSIONIZER_RUNTIME_PATH"
