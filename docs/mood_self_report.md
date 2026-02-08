# Mood Self-Report (Metadata-Only)

This document defines a policy-safe mood tracking lane for StatiBaker.

Core principle: SB may store **self-reported** mood metadata as an overlay, but
must not infer mood from other signals (chat volume, sleep, medication, etc.).

## Unified signal
- `signal: "context_field"`
- `context_type: "mood"`

## Required fields (output)
- `ts`
- `signal` (`context_field`)
- `context_type` (`mood`)
- `event_type` (default: `report_logged`)
- `mood_code` (small closed set; see below)
- `provenance`

## Optional fields (output)
- `valence_score` (0..10 or 0..100; caller-defined scale, numeric only)
- `arousal_score` (numeric only)
- `energy_score` (numeric only)
- `stress_score` (numeric only)
- `anxiety_score` (numeric only)
- `note_id_hash` (hash pointer to a private note stored elsewhere)

## Forbidden
- Free-text narratives or journal bodies.
- Raw note titles or paths.
- Derived mood labels computed from other lanes.

## mood_code
The adapter normalizes to a compact set to keep UI consistent:
- `calm`
- `neutral`
- `good`
- `joyful`
- `sad`
- `angry`
- `stressed`
- `anxious`
- `overwhelmed`
- `tired`
- `sick`
- `unknown`

If a caller provides a value outside the set, it becomes `unknown`.

