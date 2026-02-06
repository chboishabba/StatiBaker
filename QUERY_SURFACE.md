# Read-Only Query Surface (Design-Only)

## Purpose
Expose SB state for agents without granting mutation rights.

## Required queries
- List `activity_events`.
- Fetch daily carryover summary.
- Retrieve provenance for a given state artifact.

## Rules
- Read-only access only.
- No mutation or re-segmentation.
- Queries return IDs and references, not content.
- Paths may be restricted to a base directory to prevent traversal.

## Canonical interface
- CLI returning JSON.
- Query parameters must be deterministic (no time-relative defaults).

## CLI entrypoint
- `scripts/query_state.py`
  - Optional `--base` constrains reads to a run directory.

## Output constraints
- `activity_events` are immutable once emitted.
- Responses include `source` and `provenance` metadata.
