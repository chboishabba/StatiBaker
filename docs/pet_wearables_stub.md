# Pet Wearables / Smart Collar Stub (Metadata-Only)

Some households have pet wearables (smart collars) that generate high-frequency
telemetry: activity, sleep, heart rate, and coarse location.

StatiBaker treats these as **non-authoritative context overlays**.

## Unified signal
- `signal: "context_field"`
- `context_type: "pet_wearable"`

## Required fields (output)
- `ts`
- `signal` (`context_field`)
- `context_type` (`pet_wearable`)
- `event_type` (default: `telemetry_observed`)
- `device_id_hash`
- `pet_id_hash`
- `provenance`

## Optional fields (output)
- `activity_index` (numeric)
- `steps_count` (integer)
- `rest_minutes` (integer)
- `sleep_minutes` (integer)
- `hr_bpm` (integer)
- `location_cell_hash` (coarse hash; do not store raw GPS)
- `battery_pct` (numeric)

## Privacy boundary
- No raw GPS tracks by default.
- No pet names, owner names, or household address.
- Any narrative notes must be stored elsewhere and referenced only by hash.

