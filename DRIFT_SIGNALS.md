# Drift Signals (Read-Only)

## Purpose
Drift signals are **observational counters** that surface potential instability or
loss of continuity. They never act, decide, or modify SB state.

## What drift is (and is not)
- Drift is a **signal**, not a diagnosis.
- Drift is **not** an error or failure.
- Drift is a way to highlight potential attention loss or data gaps.

## Output location
- Stored separately in `runs/<date>/outputs/drift.json`.
- Not embedded in `state.json`.

## Default counters (v1)
- `stale_carryover_threads`: carryover threads with age ≥ 7 days.
- `low_signal_events`: count of events marked `low_signal=true`.
- `low_signal_runs`: count of consecutive low-signal sequences ≥ 3.
- `event_source_diversity`: number of unique event sources.
- `dominant_thread_fraction`: share of events tied to the leading thread; large values signal collapsed context surfaces.
- `dominant_thread_id`: identifier for the leading thread when available.
- `high_activity_low_diversity`: flag when events ≥ 20 and diversity ≤ 1.
- `context_dominance`: flag when one thread supplies ≥ 85% of the events (configurable via `context_dominance_threshold`).

## Non-goals
- No scoring.
- No prioritization.
- No semantic labeling.
- No automation.
