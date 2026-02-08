# NotebookLM Connector (Metadata-Only)

This connector ingests NotebookLM activity as `notes_meta` records with
`app: "notebooklm"`. It captures IDs/status only (no notebook/source content).

## 1) Prerequisites

Use the vendored `notebooklm-py` submodule, or install from PyPI:

```bash
pip install "notebooklm-py[browser]"
playwright install chromium
```

Authentication options:
- Interactive: `notebooklm login`
- Non-interactive:
  - `NOTEBOOKLM_AUTH_JSON` expects inline JSON content (not a file path)
  - or set `NOTEBOOKLM_HOME` to a directory containing `storage_state.json`

Examples:
```bash
# If storage_state.json is in the ITIR-suite root
export NOTEBOOKLM_HOME=/home/c/Documents/code/ITIR-suite
notebooklm auth check --json

# If you prefer env-only auth for CI, NOTEBOOKLM_AUTH_JSON must be raw JSON
export NOTEBOOKLM_AUTH_JSON="$(cat /path/to/storage_state.json)"
```

Connectivity check:
```bash
notebooklm auth check --test --json
```

## 2) Capture raw NotebookLM metadata snapshot

```bash
cd StatiBaker
python scripts/capture_notebooklm_meta.py --output /tmp/notebooklm_meta.jsonl
```

### One-command daily wrapper (capture -> normalize -> run_day arg20)

```bash
cd StatiBaker
export NOTEBOOKLM_HOME=/home/c/Documents/code/ITIR-suite
scripts/run_day_notebooklm_auto.sh --date 2026-02-08 --repo /home/c/Documents/code/ITIR-suite
```

Wrapper behavior:
- writes raw capture to `runs/<date>/outputs/notebooklm/notebooklm_meta_raw.jsonl`
- writes normalized preview to `runs/<date>/outputs/notebooklm/notebooklm_meta_normalized.jsonl`
- calls `scripts/run_day.sh` with the raw capture as positional arg 20 (`NOTEBOOKLM_META_INPUT`)
  and can optionally append context overlays via args 22/23
  (`CONTEXT_FIELD_APPEND_INPUT`, `MEDICATION_TRACKER_INPUT`).

## Daemon-managed mode (recommended target)

For cross-platform always-on operation, run NotebookLM capture under the
daemon/web control plane instead of host-specific cron wrappers.

See:
- `docs/daemon_web_control_plane.md`

Expected behavior in daemon mode:
- scheduled NotebookLM captures managed in the web UI,
- run state and failures visible in web job history,
- local archival + dedupe of snapshots for trend queries.

Preview only:
```bash
scripts/run_day_notebooklm_auto.sh --dry-run --date 2026-02-08 --repo /home/c/Documents/code/ITIR-suite
```

Output lines are metadata-only events:
- `context_observed`
- `notebook_observed`
- `source_observed`

## 3) Normalize into SB notes signal

```bash
cd StatiBaker
python adapters/notebooklm_meta.py \
  --input /tmp/notebooklm_meta.jsonl \
  --output /tmp/notebooklm_notes.jsonl
```

Normalized output schema:
- `signal: notes_meta`
- `app: notebooklm`
- hashed IDs: `notebook_id_hash`, `note_id_hash`
- `event`: `context_observed` / `notebook_observed` / `source_observed`

## 4) Ingest through `run_day.sh`

`run_day.sh` arg 20 is `NOTEBOOKLM_META_INPUT` and appends normalized records
into `runs/<date>/logs/notes/<date>.jsonl` (together with arg 14 `NOTES_META_INPUT` if set).

When calling `run_day.sh`, pass `/tmp/notebooklm_meta.jsonl` as positional arg
20 (immediately after arg 19 `PR_EVENTS_REPO`).

If you already have an app-notes feed for arg 14, pass both:
- arg 14: `/tmp/notes_meta.jsonl`
- arg 20: `/tmp/notebooklm_meta.jsonl`

## 5) Privacy boundary

- Do not emit NotebookLM prompt/answer text bodies.
- Only metadata IDs/timestamps/status fields are allowed.
- Keep provenance on every record (`source`, `collected_at`).
