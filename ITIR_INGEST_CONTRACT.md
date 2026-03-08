# ITIR Ingest Contract (Design-Only)

## Purpose
Allow ITIR to consume SB outputs without mutating SB boundaries.

## Inputs
- SB `activity_events` and daily `state.json` outputs.

## Rules
- `activity_events` are immutable; ITIR may not re-segment time.
- ITIR adds overlays by reference (annotation IDs only).
- SB never ingests ITIR content fields.
- Bounded exception: mission/follow-up observer overlays may include compact
  mission refs and evidence refs, but they must stay reference-heavy and may
  not inject raw thread/event dumps.

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

## Current observer extension
- `observer_kind = itir_mission_graph_v1`
- required extras:
  - `mission_refs`
  - `evidence_refs`
- accepted overlays may be persisted in SB-owned SQLite tables as observer-only
  imports; this does not grant ITIR authority to mutate SB canonical state
- still prohibited:
  - raw thread/message dumps
  - full semantic report payloads
  - any state rewrite semantics
