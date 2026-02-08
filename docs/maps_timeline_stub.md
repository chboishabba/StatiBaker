# Maps Timeline Connector Stub (Google Maps / Apple Maps) (Metadata-Only)

This stub normalizes personal location timeline exports into **meta-only**
`context_field` overlays.

It is designed to support:
- coarse “where was I around then” reconstruction
- cross-tool timeline alignment (without pulling addresses into SB)
- optional integration with Indigenous data sovereignty guardrails

Non-goals:
- navigation, routing, or “life logging”
- inferring mood/intent/relationships from location

## Output signal

All rows normalize into:
- `signal: "context_field"`
- `context_type: "location_timeline"`

## Allowed fields (output)

Required:
- `ts` (ISO8601)
- `signal="context_field"`
- `context_type="location_timeline"`
- `event_type` (e.g. `visit_observed`, `path_segment_observed`, `location_observed`)
- `timeline_provider` (label only, e.g. `google_maps`, `apple_maps`)
- `provenance.source`, `provenance.collected_at`

Allowed (all optional):
- hashed IDs: `device_id_hash`, `timeline_id_hash`, `place_id_hash`, `visit_id_hash`, `segment_id_hash`
- hashed coarse location: `location_cell_hash`
- numeric/categorical metadata: `duration_minutes`, `travel_mode_code`, `confidence_code`
- time bounds: `start_ts`, `end_ts`

Forbidden:
- raw `lat`/`lon`
- place names, addresses, free-text notes
- URLs, raw file paths

## Usage

Normalize an exported JSONL into a safe overlay stream:

```bash
python adapters/maps_timeline_stub.py \
  --input /tmp/maps_timeline_raw.jsonl \
  --output /tmp/context_location_timeline.jsonl \
  --provider google_maps
```

Then append via `run_day.sh` positional arg 22 (`CONTEXT_FIELD_APPEND_INPUT`) or
append directly into:
- `runs/<date>/logs/context/<date>.jsonl`

## Location minimization

If the raw export includes `lat`/`lon`, the adapter:
- quantizes them into a coarse grid cell (default `--grid-deg 0.01`, approx ~1km)
- stores only `location_cell_hash`
- drops raw coordinates from the output

## Indigenous guardrails

Location trails can intersect with Indigenous places, communities, and sensitive
knowledge. This connector must follow:
- `docs/planning/indigenous_data_sovereignty_connector_guardrails_20260208.md`

Default stance:
- coarse location only
- no place naming
- no promotion across authority lanes without explicit receipts + policy receipt

