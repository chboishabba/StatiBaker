#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_REPO_PATH="$(cd "$ROOT_DIR/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"
RUNS_ROOT="${SB_RUNS_ROOT:-$ROOT_DIR/runs_local}"

DATE="$(date +%F)"
REPO_PATH="$DEFAULT_REPO_PATH"
NOTEBOOKLM_BINARY="${NOTEBOOKLM_BINARY:-notebooklm}"
NOTEBOOK_LIMIT="${NOTEBOOKLM_NOTEBOOK_LIMIT:-0}"
HISTORY_LIMIT="${NOTEBOOKLM_HISTORY_LIMIT:-10}"
NOTE_LIMIT="${NOTEBOOKLM_NOTE_LIMIT:-20}"
PREVIEW_CHARS="${NOTEBOOKLM_PREVIEW_CHARS:-280}"
INCLUDE_SOURCES=1
INCLUDE_ACTIVITY=1
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_day_notebooklm_auto.sh [options] [run_day_args_3_to_19...]

Purpose:
  One-command daily flow:
    1) capture NotebookLM metadata snapshot (raw)
    2) normalize NotebookLM metadata (validation artifact)
    3) optionally capture/normalize bounded NotebookLM interaction observations
    4) call scripts/run_day.sh with raw snapshot passed as positional arg 20

Options:
  --date YYYY-MM-DD       Run date (default: today)
  --repo PATH             Repo path for run_day arg2 (default: parent of StatiBaker)
  --binary PATH           notebooklm binary path (default: notebooklm or $NOTEBOOKLM_BINARY)
  --notebook-limit N      Cap notebooks queried in capture step (default: 0 = all)
  --history-limit N       Max conversation-history rows per notebook (default: 10)
  --note-limit N          Max notes per notebook (default: 20)
  --preview-chars N       Max chars for interaction previews (default: 280)
  --no-sources            Skip per-notebook source listing during capture
  --no-activity           Skip bounded interaction capture/normalization
  --dry-run               Print commands only, do not execute
  -h, --help              Show this help

Notes:
  - Remaining positional args are forwarded as run_day positional args 3..19.
  - If fewer than 17 forwarded args are provided, missing ones are padded as empty.
  - If NOTEBOOKLM_HOME is set, notebooklm auth/context paths come from that directory.
EOF
}

FORWARDED_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)
      shift
      DATE="${1:-}"
      ;;
    --repo)
      shift
      REPO_PATH="${1:-}"
      ;;
    --binary)
      shift
      NOTEBOOKLM_BINARY="${1:-}"
      ;;
    --notebook-limit)
      shift
      NOTEBOOK_LIMIT="${1:-0}"
      ;;
    --history-limit)
      shift
      HISTORY_LIMIT="${1:-10}"
      ;;
    --note-limit)
      shift
      NOTE_LIMIT="${1:-20}"
      ;;
    --preview-chars)
      shift
      PREVIEW_CHARS="${1:-280}"
      ;;
    --no-sources)
      INCLUDE_SOURCES=0
      ;;
    --no-activity)
      INCLUDE_ACTIVITY=0
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        FORWARDED_ARGS+=("$1")
        shift
      done
      break
      ;;
    *)
      FORWARDED_ARGS+=("$1")
      ;;
  esac
  shift || true
done

if [[ -z "$DATE" ]]; then
  echo "error: --date cannot be empty" >&2
  exit 2
fi
if [[ -z "$REPO_PATH" ]]; then
  echo "error: --repo cannot be empty" >&2
  exit 2
fi
if ! [[ "$NOTEBOOK_LIMIT" =~ ^[0-9]+$ ]]; then
  echo "error: --notebook-limit must be a non-negative integer" >&2
  exit 2
fi
if ! [[ "$HISTORY_LIMIT" =~ ^[0-9]+$ ]]; then
  echo "error: --history-limit must be a non-negative integer" >&2
  exit 2
fi
if ! [[ "$NOTE_LIMIT" =~ ^[0-9]+$ ]]; then
  echo "error: --note-limit must be a non-negative integer" >&2
  exit 2
fi
if ! [[ "$PREVIEW_CHARS" =~ ^[0-9]+$ ]]; then
  echo "error: --preview-chars must be a non-negative integer" >&2
  exit 2
fi

if [[ "${#FORWARDED_ARGS[@]}" -gt 17 ]]; then
  echo "error: too many forwarded arguments (${#FORWARDED_ARGS[@]}). Maximum is 17 (run_day args 3..19)." >&2
  exit 2
fi

while [[ "${#FORWARDED_ARGS[@]}" -lt 17 ]]; do
  FORWARDED_ARGS+=("")
done

NLM_OUT_DIR="$RUNS_ROOT/$DATE/outputs/notebooklm"
RAW_PATH="$NLM_OUT_DIR/notebooklm_meta_raw.jsonl"
NORMALIZED_PATH="$NLM_OUT_DIR/notebooklm_meta_normalized.jsonl"
ACTIVITY_RAW_PATH="$NLM_OUT_DIR/notebooklm_activity_raw.jsonl"
ACTIVITY_NORMALIZED_PATH="$NLM_OUT_DIR/notebooklm_activity_normalized.jsonl"

CAPTURE_CMD=(
  python "$ROOT_DIR/scripts/capture_notebooklm_meta.py"
  --binary "$NOTEBOOKLM_BINARY"
  --output "$RAW_PATH"
  --notebook-limit "$NOTEBOOK_LIMIT"
)
if [[ "$INCLUDE_SOURCES" -eq 0 ]]; then
  CAPTURE_CMD+=(--no-sources)
fi

NORMALIZE_CMD=(
  python "$ROOT_DIR/adapters/notebooklm_meta.py"
  --input "$RAW_PATH"
  --output "$NORMALIZED_PATH"
)

ACTIVITY_CAPTURE_CMD=(
  python "$ROOT_DIR/scripts/capture_notebooklm_activity.py"
  --output "$ACTIVITY_RAW_PATH"
  --notebook-limit "$NOTEBOOK_LIMIT"
  --history-limit "$HISTORY_LIMIT"
  --note-limit "$NOTE_LIMIT"
  --preview-chars "$PREVIEW_CHARS"
)

ACTIVITY_NORMALIZE_CMD=(
  python "$ROOT_DIR/adapters/notebooklm_activity.py"
  --input "$ACTIVITY_RAW_PATH"
  --output "$ACTIVITY_NORMALIZED_PATH"
)

RUN_DAY_CMD=(
  "$ROOT_DIR/scripts/run_day.sh"
  "$DATE"
  "$REPO_PATH"
  "${FORWARDED_ARGS[@]}"
  "$RAW_PATH"
)

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "NOTEBOOKLM_HOME=${NOTEBOOKLM_HOME:-<default>}"
  printf 'CAPTURE: '
  printf '%q ' "${CAPTURE_CMD[@]}"
  echo
  printf 'NORMALIZE: '
  printf '%q ' "${NORMALIZE_CMD[@]}"
  echo
  if [[ "$INCLUDE_ACTIVITY" -eq 1 ]]; then
    printf 'ACTIVITY_CAPTURE: '
    printf '%q ' "${ACTIVITY_CAPTURE_CMD[@]}"
    echo
    printf 'ACTIVITY_NORMALIZE: '
    printf '%q ' "${ACTIVITY_NORMALIZE_CMD[@]}"
    echo
  fi
  printf 'RUN_DAY: '
  printf '%q ' "${RUN_DAY_CMD[@]}"
  echo
  exit 0
fi

mkdir -p "$NLM_OUT_DIR"
echo "NOTEBOOKLM_HOME=${NOTEBOOKLM_HOME:-<default>}"
echo "Capturing NotebookLM metadata -> $RAW_PATH"
"${CAPTURE_CMD[@]}"

echo "Normalizing NotebookLM metadata -> $NORMALIZED_PATH"
"${NORMALIZE_CMD[@]}"

if [[ "$INCLUDE_ACTIVITY" -eq 1 ]]; then
  echo "Capturing NotebookLM interactions -> $ACTIVITY_RAW_PATH"
  "${ACTIVITY_CAPTURE_CMD[@]}"

  echo "Normalizing NotebookLM interactions -> $ACTIVITY_NORMALIZED_PATH"
  "${ACTIVITY_NORMALIZE_CMD[@]}"
fi

echo "Running daily ingest with NotebookLM arg20 -> $RAW_PATH"
"${RUN_DAY_CMD[@]}"

echo "done"
echo "raw=$RAW_PATH"
echo "normalized=$NORMALIZED_PATH"
if [[ "$INCLUDE_ACTIVITY" -eq 1 ]]; then
  echo "activity_raw=$ACTIVITY_RAW_PATH"
  echo "activity_normalized=$ACTIVITY_NORMALIZED_PATH"
fi
