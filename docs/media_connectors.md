# Media Connectors (Metadata-Only)

This document defines StatiBaker media ingestion for:
- YouTube watch history exports
- Spotify play history exports
- VLC session/history exports
- Last.fm scrobble exports

The goal is to produce comparable **meta-only** telemetry:
- consumed/watch/listen time
- completion ratio
- churn events/rate

No content text bodies are ingested.

## Unified signal

All connectors emit `signal: "media_consumption"` rows.

Required fields:
- `ts`
- `signal` (`media_consumption`)
- `platform` (`youtube`, `spotify`, `vlc`, `lastfm`, or other)
- `event_type` (`playback_observed` default)
- `item_id_hash`
- `provenance`

Optional fields:
- `item_title_hash`
- `artist_hash`
- `channel_hash`
- `app`
- `consumed_seconds`
- `content_duration_seconds`
- `completion_ratio` (if missing, computed from consumed/content duration)
- `session_id_hash`

## Churn model (dashboard)

Daily churn is derived from ordered `media_consumption` rows:
- Candidate churn event:
  - item has `completion_ratio < 0.35` (or derived equivalent)
  - next observed item has a different `item_id_hash`
  - next item arrives within `900s` of current row timestamp
- `media_churn_rate = media_churn_events / media_items_observed`

This is a heuristic, not a semantic intent model.

## Connector mapping notes

### YouTube
- Input fields may include: video id/url, watch time, title, channel, duration.
- Adapter hashes IDs/titles/channels and emits consumed/duration/completion fields.

### Spotify
- Input fields may include: track URI/name, artist, ms played, duration.
- Adapter maps play rows to consumed seconds and completion ratio.

### VLC
- Input fields may include: media path/URI hashable ID, playback position/duration.
- Adapter maps to consumed and duration where available.

### Last.fm
- Scrobble-style rows usually imply completed plays.
- If duration is missing, adapter emits consumed only and leaves completion ratio optional.

## Privacy boundary

- Never emit raw titles, URLs, paths, lyrics, transcript text, or message content.
- Use hashes for identifiers and labels.
- Keep provenance on every record.
