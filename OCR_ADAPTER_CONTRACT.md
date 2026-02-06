# OCR Adapter Contract (Design-Only)

## Purpose
Define the OCR boundary so extracted text never becomes SB state without explicit
promotion.

## Inputs
- Snapshots with content-addressed IDs.
- Snapshot metadata only (timestamp, source, app/window identifiers).

## Outputs
- Derived artifacts in a separate store (not in `STATE_SCHEMA.json`).
- Records must reference snapshot IDs and include a policy receipt.

## Hard rules
- OCR output is never written into folds or summaries.
- OCR output never creates or splits `activity_events`.
- Promotion from OCR to state requires an explicit, audited step.

## Required fields
- `snapshot_id`
- `ts`
- `source`
- `policy_receipt`
- `text_hash`
- `text_bytes`

## Allowed usage
- Evidence rendering only (OpenRecall or equivalent).
- Optional downstream analysis that stays outside SB state.

## Prohibited usage
- Any semantic labeling or classification in SB core.
- Any implicit state updates.
