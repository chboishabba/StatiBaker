# Collectors Index

This index lists all supported collectors/adapters and their expected inputs.
Collectors are metadata-first by default. Only explicitly documented personal
observer lanes may emit bounded preview text.

## Core system collectors
- `adapters/gitlog.py` (git commits)
- `adapters/git_branch.py` (git branch history via reflog)
- `adapters/fs_meta.py` (filesystem metadata)
- `adapters/prometheus_summary.py` (metrics summaries)
- `adapters/journald.py` (Linux system events)
- `adapters/osquery_poll.py` (system facts)
- `adapters/wazuh_lifecycle.py` (Wazuh lifecycle events)

## Input / activity
- `adapters/input_activity.py` (keyboard/mouse counts)
- `adapters/window_focus.py` (app focus + title hash)
- `adapters/cli_meta.py` (CLI command hash + cwd hash)

## Security / endpoint
- `adapters/av_status.py` (AV/endpoint status summaries)

## Browser / apps
- `adapters/browser_usage.py` (domain hash + duration)
- `adapters/notes_meta.py` (Obsidian/Evernote metadata)
- `adapters/notebooklm_meta.py` (NotebookLM notebook/source metadata snapshots)
- `adapters/openrecall_activity.py` (OpenRecall `recall.db` -> bounded activity-indicator rows + deep links)
- `adapters/google_tasks.py` (Google Tasks -> external_commitment normalization)
- `adapters/google_keep_lists.py` (Google Keep/list items -> external_commitment normalization)
- `scripts/capture_notebooklm_meta.py` (NotebookLM CLI snapshot collector)
- `adapters/media_consumption.py` (unified media watch/listen metadata)
- `adapters/youtube_watch_stub.py` (YouTube export stub -> media_consumption)
- `adapters/spotify_history_stub.py` (Spotify export stub -> media_consumption)
- `adapters/vlc_history_stub.py` (VLC export stub -> media_consumption)
- `adapters/lastfm_scrobble_stub.py` (Last.fm export stub -> media_consumption)
- `adapters/living_environment_simulator_stub.py` (living-environment snapshots -> context_field)
- `adapters/aquaponics_calculator_stub.py` (aquaponics telemetry -> context_field)
- `adapters/crops_stub.py` (crop-cycle telemetry -> context_field)
- `adapters/medication_tracker_stub.py` (medication adherence telemetry -> context_field)
- `adapters/mood_self_report_stub.py` (mood self-report -> context_field)
- `adapters/inaturalist_stub.py` (iNaturalist observations -> context_field)
- `adapters/pet_wearable_stub.py` (pet wearable / smart collar telemetry -> context_field)
- `adapters/maps_timeline_stub.py` (Google/Apple maps timeline exports -> context_field)

## Cloud audit feeds
- `adapters/cloud_audit.py` (Google Drive / MS365 audit logs)
- `adapters/pr_events.py` (pull request lifecycle event normalization)
- `adapters/pr_events_github.py` (direct GitHub PR lifecycle collection via `gh`)

## Social feed stubs
- `adapters/social_feed.py` (generic meta-only social events)
- `adapters/social_bluesky_stub.py`
- `adapters/social_twitter_stub.py`
- `adapters/social_mastodon_stub.py`
- `adapters/social_reddit_stub.py`
- `adapters/social_facebook_messenger_stub.py`
- `adapters/social_telegram_stub.py`
- `adapters/social_whatsapp_stub.py`

## OS stubs
- `adapters/windows_event_stub.py`
- `adapters/macos_unified_log_stub.py`

## Related docs
- `INGESTION_FORMATS.md`
- `docs/observed_signals.md`
- `docs/social_audit_redaction.md`
- `docs/social_stub_collectors.md`
- `docs/notebooklm_connector.md`
- `docs/google_commitment_connectors.md`
- `docs/daemon_web_control_plane.md`
- `docs/media_connectors.md`
