# NotebookLM Connector (Metadata + Display Snippets)

This connector ingests NotebookLM activity as `notes_meta` records with
`app: "notebooklm"`.

Default intent:
- capture lifecycle metadata (context/notebook/source/artifact observed)
- preserve display-safe fields users expect to see in the UI (titles/types/status/timestamps/URLs)
- optionally capture short source-guide snippets (summary + keywords)
- avoid storing full notebook/source bodies by default

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

## 2) Capture raw NotebookLM snapshot

```bash
cd StatiBaker
python scripts/capture_notebooklm_meta.py --output /tmp/notebooklm_meta.jsonl
```

Optional richer capture:
```bash
python scripts/capture_notebooklm_meta.py \
  --output /tmp/notebooklm_meta.jsonl \
  --with-source-guides \
  --source-snippet-chars 600
```

Optional artifact-only reductions:
```bash
# Skip artifact listing
python scripts/capture_notebooklm_meta.py --output /tmp/notebooklm_meta.jsonl --no-artifacts

# Skip source listing (status + notebooks only)
python scripts/capture_notebooklm_meta.py --output /tmp/notebooklm_meta.jsonl --no-sources
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

Output lines include event records such as:
- `context_observed`
- `notebook_observed`
- `source_observed`
- `artifact_observed`

`source_observed` can include display fields (`source_title`, `source_type`,
`source_status`, `source_url`) and optional snippet fields
(`source_summary`, `source_keywords`).

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
- `event`: `context_observed` / `notebook_observed` / `source_observed` / `artifact_observed`
- preserved display fields when present:
  - notebook: `notebook_title`
  - source: `source_title`, `source_type`, `source_status`, `source_url`,
    optional `source_summary`, `source_keywords`
  - artifact: `artifact_title`, `artifact_type`, `artifact_status`,
    `artifact_created_at`

## 4) Ingest through `run_day.sh`

`run_day.sh` arg 20 is `NOTEBOOKLM_META_INPUT` and appends normalized records
into `runs/<date>/logs/notes/<date>.jsonl` (together with arg 14 `NOTES_META_INPUT` if set).

When calling `run_day.sh`, pass `/tmp/notebooklm_meta.jsonl` as positional arg
20 (immediately after arg 19 `PR_EVENTS_REPO`).

If you already have an app-notes feed for arg 14, pass both:
- arg 14: `/tmp/notes_meta.jsonl`
- arg 20: `/tmp/notebooklm_meta.jsonl`

## 5) Privacy boundary

- Do not emit full NotebookLM prompt/answer/source bodies by default.
- Display fields and short snippets are allowed for local-user UX parity.
- If a stricter posture is needed, disable source-guide capture and rely on
  hashed IDs + lifecycle status only.
- Keep provenance on every record (`source`, `collected_at`).

## Current suite posture

NotebookLM is currently standardized as a **metadata/review/source** lane, not
as a full SB activity/session lane.

What the current lane supports:
- lifecycle counters and hour bins
- notebook/source/artifact review surfaces
- bounded snippet/keyword capture for local UX
- source-local text reuse in downstream ITIR/SensibLaw reporting

What it does not yet support honestly:
- waterfall/timeline usage parity with chat/shell
- sessionized NotebookLM duration accounting
- strong mission-lens actual attribution from NotebookLM alone

Those later capabilities require a separate interaction-grade capture contract
for NotebookLM events, rather than reinterpretation of `notes_meta` snapshots.

## Next additive lane: interaction capture

The suite now also ships a separate interaction contract, not a redefinition
of `notes_meta`.

Raw event families:
- `conversation_observed`
- `note_observed`

Normalized posture:
- `signal: notebooklm_activity`
- `app: notebooklm`
- hashed notebook/note/conversation IDs
- bounded previews only

Outputs under `runs/<date>/outputs/notebooklm/`:
- `notebooklm_activity_raw.jsonl`
- `notebooklm_activity_normalized.jsonl`

Example commands:
```bash
cd StatiBaker
python scripts/capture_notebooklm_activity.py --output /tmp/notebooklm_activity.jsonl
python adapters/notebooklm_activity.py \
  --input /tmp/notebooklm_activity.jsonl \
  --output /tmp/notebooklm_activity_normalized.jsonl
```

This lane is intended for:
- query/read-model parity
- bounded note/conversation review
- source-local text reuse

Repo-local operation helper:
- `../scripts/notebooklm_clarify.py`
- use this when the suite needs a minimal in-repo NotebookLM ask/clarify path
  for structured `category:text` prompts
- do not confuse it with this connector:
  - the connector is capture/observer infrastructure
  - the clarify helper is operation ingress

It is still not, by itself:
- sessionized NotebookLM usage
- waterfall/timeline accounting
- mission actual-side authority
