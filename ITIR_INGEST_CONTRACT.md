# ITIR Ingest Contract (Design-Only)

## Purpose
Allow ITIR to consume SB outputs without mutating SB boundaries.

## Inputs
- SB `activity_events` and daily `state.json` outputs.

## Rules
- `activity_events` are immutable; ITIR may not re-segment time.
- ITIR adds overlays by reference (annotation IDs only).
- SB never ingests ITIR content fields.

## Required fields
- `activity_event_id`
- `sb_state_id` or `state_date`
- `annotation_id`
- `provenance` (who/when)

## Prohibited behavior
- Any attempt to replace or merge SB events.
- Any unreferenced, free-form content injection.
- Any attempt to submit `activity_events`, `events`, `threads`, `snapshots`,
  `state`, `activity_ledger`, or `drift` fields.
