# Observed Signals (Meta-Only)

StatiBaker ingests **observed signals** as append-only JSONL. These signals are
structural metadata only and must not include content.

Core rules:
- Meta only: no free text, no document bodies, no message content.
- Hashes are allowed to reference content stored elsewhere.
- Provenance is required on every record.
- Absence is explicit (use `missing_*` fields, never implicit).

## Scope (current)
All sources below are supported as **metadata-only** streams. Linux is the first
implementation target; macOS and Windows are stubbed via normalized formats.
Cloud connectors are read-only audit feeds.

### Input activity (keyboard/mouse)
- Signal: `input`
- Required fields: `ts`, `focus_app`, `keys`, `mouse`, `provenance`
- Allowed fields:
  - `keys`: counts only (e.g., `text`, `nav`, `control`)
  - `mouse`: counts only (e.g., `moves`, `clicks`, `scroll`)

### Window/app focus
- Signal: `window_focus`
- Required fields: `ts`, `app_id`, `window_title_hash`, `provenance`
- Allowed fields: `duration_ms`, `workspace`, `display`

### Command history (CLI)
- Signal: `cli`
- Required fields: `ts`, `cmd_hash`, `cwd_hash`, `exit`, `provenance`
- Allowed fields: `duration_ms`, `shell` (no raw command lines)

### Git branch history
- Signal: `git_branch`
- Required fields: `ts`, `event_type`, `repo`, `ref`, `provenance`
- Allowed fields: `commit_hash`, `event_hash`, `from_ref`, `to_ref`
- Events are metadata-only branch transitions (no commit body text).

### Pull request lifecycle
- Signal: `pr_event`
- Required fields: `ts`, `event_type`, `repo`, `pr_number`, `provenance`
- Allowed fields: `state`, `actor_hash`, `pr_key_hash`
- Typical event types: `pr_received`, `pr_opened`, `pr_commented`, `pr_merged`

### System event logs
- Signal: `system`
- Required fields: `ts`, `platform`, `event_id`, `severity`, `provenance`
- Allowed fields: `source`, `category`, `count`
- Linux source: journald adapter (curated event mapping)
- macOS/Windows: normalized event log format (stubbed adapters)

### Antivirus / endpoint status
- Signal: `av_status`
- Required fields: `ts`, `engine`, `status`, `provenance`
- Allowed fields: `signature_age_days`, `threat_count` (no threat names)

### Browser usage stats
- Signal: `browser_usage`
- Required fields: `ts`, `browser`, `domain_hash`, `duration_ms`, `provenance`
- Allowed fields: `profile_id`, `tab_count`

### Cloud audit feeds (Google Drive / MS365)
- Signal: `cloud_audit`
- Required fields: `ts`, `provider`, `event_type`, `resource_id_hash`, `provenance`
- Allowed fields: `actor_hash`, `ip_hash`, `device_hash`
- Read-only: no content, no file bodies

### Notes apps (Obsidian / Evernote)
- Signal: `notes_meta`
- Required fields: `ts`, `app`, `note_id_hash`, `event`, `provenance`
- Allowed fields: `vault_id_hash`, `notebook_id_hash`
- NotebookLM connector emits into this same signal with `app: notebooklm`.

### WorldMonitor capture bridge
- Signal: `worldmonitor_capture`
- Required fields: `ts`, `signal`, `event_type`, `capture_id_hash`, `source_kind`, `provenance`
- Allowed fields: `import_run_id_hash`, `source_file_hash`, `source_row_id_hash`,
  `captured_date`, `row_label_hash`, `status`
- Constraint: metadata only; no raw source paths, titles, or text payloads.
- Use this stream when exporting WorldMonitor captures from ITIR/SL into SB
  logs under `logs/worldmonitor/YYYY-MM-DD.jsonl`.

### Social feeds (Bluesky, Twitter/X, Mastodon, Reddit, FB Messenger, Telegram, WhatsApp)
- Signal: `social_feed`
- Required fields: `ts`, `platform`, `event_type`, `post_id_hash`, `provenance`
- Allowed fields: `author_hash`, `thread_id_hash`

### Media consumption feeds (YouTube, Spotify, VLC, Last.fm)
- Signal: `media_consumption`
- Required fields: `ts`, `platform`, `event_type`, `item_id_hash`, `provenance`
- Allowed fields: `item_title_hash`, `artist_hash`, `channel_hash`,
  `consumed_seconds`, `content_duration_seconds`, `completion_ratio`,
  `session_id_hash`
- Meta only: no media text/transcripts/lyrics/titles in cleartext.

### Living environment / aquaponics / crops (non-authoritative overlays)
- Signal: `context_field`
- Required fields: `ts`, `context_type`, `event_type`, `provenance`
- Allowed fields:
  - living environment: `temp_c`, `humidity_pct`, `co2_ppm`, `pm25_ug_m3`,
    `voc_index`, `noise_db`, `light_lux`, hashed zone/scenario IDs
  - aquaponics: `water_temp_c`, `ph`, `ec_ms_cm`, `dissolved_o2_mg_l`,
    `ammonia_mg_l`, `nitrite_mg_l`, `nitrate_mg_l`, `flow_l_min`, hashed IDs
  - crops: `stage_code`, `canopy_pct`, `soil_moisture_pct`,
    `irrigation_liters`, `nutrient_ec_ms_cm`, `brix`, hashed plot/crop IDs
- Constraint: these remain context overlays and must not be used for behavioural
  inference or automatic prioritisation.

### Medication tracker overlays (non-authoritative)
- Signal: `context_field`
- Required fields: `ts`, `context_type=medication`, `event_type`, `provenance`
- Allowed fields:
  - hashed IDs: `tracker_id_hash`, `medication_id_hash`, `schedule_id_hash`,
    `intake_id_hash`
  - numeric/categorical telemetry: `dose_amount`, `dose_unit`, `route_code`,
    `adherence_flag`, `missed_flag`, `prn_flag`, `delay_minutes`,
    `symptom_score`, `side_effect_flag`
- Constraint: no medication names, notes, or free-text symptom narratives in
  cleartext; this remains a metadata-only overlay lane.

### Mood self-report overlays (non-authoritative)
- Signal: `context_field`
- Required fields: `ts`, `context_type=mood`, `event_type`, `mood_code`, `provenance`
- Allowed fields: numeric scales only (`valence_score`, `stress_score`, etc) and
  `note_id_hash` pointers.
- Constraint: mood is self-report only; SB must not infer mood from other lanes.
  No free text in this lane.

### iNaturalist biodiversity overlays (non-authoritative)
- Signal: `context_field`
- Required fields: `ts`, `context_type=inaturalist`, `event_type`, `taxon_id_hash`, `provenance`
- Allowed fields: `place_id_hash`, `project_id_hash`, `quality_grade_code`,
  `iconic_taxon_code`, `obs_count`, `insect_flag`
- Constraint: minimize location precision; no raw GPS or species text.

### Pet wearables / smart collar overlays (non-authoritative)
- Signal: `context_field`
- Required fields: `ts`, `context_type=pet_wearable`, `event_type`, `device_id_hash`, `pet_id_hash`, `provenance`
- Allowed fields: `activity_index`, `steps_count`, `sleep_minutes`, `hr_bpm`,
  `location_cell_hash`, `battery_pct`
- Constraint: no raw GPS tracks, pet names, owner names, or household address.

### Maps timeline overlays (Google/Apple) (non-authoritative)
- Signal: `context_field`
- Required fields: `ts`, `context_type=location_timeline`, `event_type`, `timeline_provider`, `provenance`
- Allowed fields:
  - hashed IDs: `device_id_hash`, `timeline_id_hash`, `place_id_hash`, `visit_id_hash`, `segment_id_hash`
  - hashed coarse location: `location_cell_hash`
  - numeric/categorical metadata: `duration_minutes`, `travel_mode_code`, `confidence_code`, `start_ts`, `end_ts`
- Constraint: no raw coordinates, addresses, place names, or free-text notes.

## Platform notes
- Linux: journald + collectors emit normalized records.
- macOS/Windows: stub adapters emit normalized records from external exports.
- Cloud: audit feeds are read-only and must be hashed.

## Sample run_day wiring (meta-only)
Example using pre-exported JSONL files (no live collection):

```bash
./scripts/run_day.sh 2026-02-06 \
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
  /tmp/macos_unified.jsonl \
  /tmp/pr_events.jsonl \
  "" \
  /tmp/media_consumption.jsonl \
  /tmp/context_fields.jsonl \
  /tmp/medication_raw.jsonl
```

All inputs are optional; missing files are skipped with warnings.
`logs/git_branch/<date>.jsonl` is emitted automatically from local git reflog.
For direct GitHub PR ingestion (no JSONL input file), pass positional arg 19
to `run_day.sh` as `auto` or `owner/repo`.
For NotebookLM metadata snapshots, pass positional arg 20 to `run_day.sh` as
`NOTEBOOKLM_META_INPUT` (see `docs/notebooklm_connector.md`).
For media consumption snapshots, pass positional arg 21 as
`MEDIA_CONSUMPTION_INPUT` (see `docs/media_connectors.md`).
For context-field overlays, either:
- pass a pre-normalized `context_field` JSONL as positional arg 22
  (`CONTEXT_FIELD_APPEND_INPUT`) to append into `logs/context/<date>.jsonl`, or
- pass a medication tracker raw JSONL as positional arg 23
  (`MEDICATION_TRACKER_INPUT`) and `run_day.sh` will normalize it via
  `adapters/medication_tracker_stub.py` and append it into `logs/context/<date>.jsonl`.

For WorldMonitor captures, run
`scripts/export_worldmonitor_observed.py --itir-db-path ... --output ...`
and place the output under `logs/worldmonitor/<date>.jsonl`. `run_day.sh`
already picks up JSONL files anywhere under `logs/`.

For the full bounded bridge, use
`scripts/run_worldmonitor_bridge.py --date ...` to:
1. import WorldMonitor into ITIR via SensibLaw,
2. export the SB-safe `worldmonitor_capture` JSONL,
3. run `run_day.sh`, and
4. emit SensibLaw worldmonitor summary and chronology readouts beside the run.

If `--source-path` is omitted, the bridge defaults to the sibling
`../worldmonitor/data` tree. Optional helper flags:

- `--bootstrap-worldmonitor` to run `npm install` in the sibling repo first
- `--smoke-worldmonitor-dev` to verify the local WorldMonitor app boots before ingest

If the WorldMonitor data tree is unchanged and the importer de-duplicates to
zero new captures, the bridge reuses the latest populated import run for that
same resolved source path so the SL summary/chronology and SB export remain
useful on repeated local runs.

The bridge exports the whole effective import run by default. Only pass
`--captured-date YYYY-MM-DD` when you intentionally want the SB JSONL to be
restricted to one WorldMonitor source date.

## Social stub collectors
See `docs/social_stub_collectors.md` for per-platform stub inputs.

## Provenance
Every record must include:
- `provenance.source` (collector or adapter name)
- `provenance.collected_at` (UTC ISO8601)
- Optional `provenance.policy_receipt` (if gated by consent)

## Forbidden fields (non-exhaustive)
Any of the following must be rejected:
- `text`, `content`, `body`, `message`, `summary`, `tokens`
- raw URLs, raw file paths, raw titles (use hashes)

## Storage
Observed signals are append-only JSONL under `logs/<signal>/YYYY-MM-DD.jsonl`.
See `INGESTION_FORMATS.md` for per-signal schemas.
