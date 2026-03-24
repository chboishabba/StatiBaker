# Google Commitment Connectors

This note defines the v1 Google commitment ingest posture for StatiBaker.

## Purpose

Support usable Google/Home-originated task capture without turning SB into the
place where commitments are managed.

## Scope

V1 supports two source paths:
- Google Tasks (`source_kind = google_tasks_task`)
- Google Keep/list items (`source_kind = google_keep_list_item`)

Both normalize into `signal: external_commitment` rows under
`logs/commitments/YYYY-MM-DD.jsonl`.

## Boundary

- Source systems remain authoritative for canonical task state.
- SB may project commitments, correlate them with evidence, and emit
  `task_completion_candidate_v1` rows.
- SB must not claim, schedule, drag/drop, or silently complete tasks.
- Completion candidates are proposal artifacts only.

## Normalized ingest shape

Required fields:
- `ts`
- `signal = external_commitment`
- `version = external_commitment_event_v1`
- `source_system`
- `source_kind`
- `external_account_id`
- `external_list_id`
- `external_item_id`
- `title`
- `status`
- `provenance`

Optional but expected when available:
- `notes_excerpt`
- `due_at`
- `voice_origin`
- `source_created_at`
- `source_updated_at`
- `raw_locator`

## Voice-origin policy

`voice_origin` is descriptive only. V1 uses:
- `tasks_command`
- `keep_list`
- `unknown`

If the source does not expose enough metadata to classify voice origin, leave it
as `unknown` rather than inferring.

## Completion-candidate policy

SB may emit `task_completion_candidate_v1` rows under
`logs/task_candidates/YYYY-MM-DD.jsonl` when there is explicit evidence that an
open commitment appears to have been satisfied.

Required fields:
- `candidate_id`
- `target_system`
- `target_kind`
- `external_item_id`
- `proposed_action = mark_complete`
- `candidate_status = proposed`
- `reason_codes`
- `generator`
- `generated_at`
- `evidence_refs`

V1 is propose-only. No Google mutation path ships in this slice.

## UI posture

SB may render:
- commitment feed
- stale/open/completed counts
- voice-origin slices
- read-only Kanban-shaped projection lanes
- completion-candidate review surfaces

SB must not render a mutable board of record.
