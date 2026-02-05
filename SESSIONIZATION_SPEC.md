# SB Sessionization Spec (v0)

This defines deterministic rules for converting observed `snapshots[]` into
`activity_events[]`. The output is **recomputable**, **auditable**, and **stable**
for identical inputs.

## Inputs

`snapshots[]` are ordered by `ts` (tie-breaker: `id`).
Each snapshot may include:
- `id` (string, required)
- `ts` (RFC3339 timestamp, required)
- `app_id` (string, optional)
- `window_title` (string, optional)
- `display_id` (string, optional)
- `hash` (string, optional; `phash:<hex>` preferred)
- `policy_flags` (string array, optional)
- `redacted` (boolean, optional)

## Outputs

`activity_events[]` are deterministic segments:
- `id`
- `t_start`, `t_end`
- `snapshot_ids[]`
- `primary_app` (most frequent `app_id`, tie -> latest)
- `title` (best-effort, explainable)
- `confidence` (0..1, simple heuristic)
- `policy_flags[]` (union)
- `derived_from[]` (snapshot ids)

## Deterministic ordering

- Sort snapshots by `ts` ascending, then `id`.
- Events emit in chronological order.
- Event ids use a stable, zero-padded sequence: `act-000001`, `act-000002`, ...

## Sessionization rules (v0)

### Hard breaks (always split)

- **Idle gap**: `ts_delta >= 300s`
- **App change**: `app_id` differs and both are non-empty
- **Display change**: `display_id` differs and both are non-empty

### Soft breaks (score-based)

Compute soft break score as the sum of triggered conditions:

- **Title drift**: token Jaccard similarity < 0.3  -> +1
- **Hash jump**: perceptual hash Hamming distance >= 12 -> +1

If soft score >= 2, split.

### Merge rule (adjacent snapshots)

If none of the hard or soft split rules fire, merge into current event.

## Configuration

Sessionization uses a JSON config with defaults:
- `idle_gap_s` (default 300)
- `title_jaccard_min` (default 0.3)
- `phash_jump_min` (default 12)
- `app_label_map` (optional map of app_id -> label)

The config is advisory and must never introduce non-determinism.
Values are validated at load time (types and ranges).

## Title selection (explainable)

Priority:
1. Latest non-empty `window_title`, cleaned.
2. `app_id` mapped to label via `app_label_map` (optional).
3. Default: "Using <app_id>".
4. Fallback: "Activity".

Cleaning:
- lowercase
- strip surrounding whitespace
- collapse internal whitespace

## Confidence (v0 heuristic)

Start at 0.5, then adjust:
- +0.2 if event has >= 3 snapshots
- +0.1 if title derived from window_title
- -0.2 if any snapshot is `redacted: true`
Clamp to [0, 1].

## Provenance (optional envelope)

When exporting as a ledger:
```
{
  "activity_events": [...],
  "provenance": {
    "algorithm": "sb.sessionize.v0",
    "input_hash": "<sha256 of snapshot ids+ts>",
    "policy_receipt": "<policy id or hash>"
  }
}
```
