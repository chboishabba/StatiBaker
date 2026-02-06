# Failure Modes (Boundary Lock)

## Re-segmentation attempts
- Symptom: external tool tries to modify `activity_events`.
- Response: hard reject (validation error).

## Summary injection
- Symptom: derived summary fields appear in SB state.
- Response: guardrail test fails.

## Metric smuggling
- Symptom: metrics include semantic labels or content.
- Response: reject in adapter or flag as invalid.

## Drift override
- Symptom: drift counters injected into `state.json`.
- Response: hard reject; drift must live in `drift.json`.

## Provenance laundering
- Symptom: forged manifest or bundle content.
- Response: `verify-bundle` fails loudly; bundle rejected.

## Systemic dependency failure
- Symptom: upstream observers fail simultaneously.
- Response: explicit absence and saturation signals; no invented continuity.

## Maximum acceptable blast radius
Failures must not propagate beyond the current `runs/<date>/` output directory.
Bundles must verify or be rejected; no partial load.

### Definition
Blast radius is the maximum scope of state or output that can be corrupted,
misleading, or non-replayable due to a failure.

### Hard limits
1. Per-run containment. A failure must not affect any run other than the
   current `runs/<date>/` output directory.
2. No silent degradation. Missing, malformed, or saturated inputs must be
   surfaced explicitly. SB must not invent continuity, labels, or confidence.
3. Verify-or-refuse. Bundles must either fully verify or be rejected.
4. No cross-source authority escalation. External observers may not induce
   time segmentation changes or overwrite SB boundaries.
5. Deterministic recovery. Given the same inputs, reruns must yield identical
   outputs or refuse with an explicit reason.

### Soft limits
- Input caps may be applied to prevent resource exhaustion.
- When caps trigger, SB must record that capping occurred and what was capped
  (counts only), while keeping outputs replayable.

### Success condition
A global upstream outage must manifest as explicit missing signals,
stable activity_event boundaries (or explicit refusal), no historical
corruption, and no increase in authority granted to external tools.
