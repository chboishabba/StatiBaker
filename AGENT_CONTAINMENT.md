# Agent Containment Rules

## Purpose
Agents may read SB state but must never mutate time, meaning, or provenance.

## Allowed
- Read-only queries of SB outputs.
- Annotation overlays in ITIR (IDs only, no content injection).
- Execution envelopes may be recorded as evidence only (see `docs/openclaw_integration.md`).

## Forbidden
- Re-segmentation of `activity_events`.
- Writing summaries back into SB state.
- Injecting drift or compression metadata.
- Altering prior runs or bundles.

## Enforcement
- ITIR overlays are validated and rejected on mutation attempts.
- SB outputs are append-only and verified via bundle manifests.
