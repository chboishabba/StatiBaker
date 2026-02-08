# iNaturalist Connector (Metadata-Only)

This document defines StatiBaker ingestion for iNaturalist exports or API
snapshots as **meta-only** context overlays.

Goal: answer questions like:
- "Are local insect observations rising (upward knee), peaking, or declining?"
- "Should I expect to see more insects soon?"

This connector is observer-class only. It does not ingest text bodies, species
descriptions, or precise GPS coordinates.

## Unified signal

iNaturalist rows are normalized into:
- `signal: "context_field"`
- `context_type: "inaturalist"`

## Required fields (output)
- `ts`
- `signal` (`context_field`)
- `context_type` (`inaturalist`)
- `event_type` (default: `observation_observed`)
- `taxon_id_hash`
- `provenance`

## Optional fields (output)
- `place_id_hash` (hashed place/cell key, not raw coordinates)
- `project_id_hash`
- `quality_grade_code` (`research|needs_id|casual|unknown`)
- `iconic_taxon_code` (e.g. `insecta|plantae|aves|mammalia|unknown`)
- `obs_count` (default: `1`)
- `insect_flag` (`0|1`)

## Input expectations (JSONL)
Inputs vary by export method. The adapter accepts any of:
- `ts` / `timestamp`
- `observed_at` / `time_observed_at`
- `created_at`

Taxon/place fields are accepted as IDs or names but are **hashed on output**.

## Trend summary model (dashboard)

StatiBaker computes a deterministic trend phase over a rolling window of daily
insect observation counts (default window: 42 days):
- `upward_knee`: rapid acceleration from low baseline
- `rising`: clear increase vs prior week
- `peak`: near window maximum and flattening
- `declining`: clear decrease vs prior week and peak behind us
- `stable`: no clear slope
- `no_activity`: all-zero window
- `insufficient_data`: not enough days

Expectation codes:
- `expect_more` (upward_knee/rising)
- `at_or_near_peak` (peak)
- `expect_less` (declining)
- `stable_or_unclear` (stable/no_activity)
- `insufficient_data`

This is a heuristic for "what to expect next", not a causal model.

## Safety / sovereignty notes
- Follow `docs/planning/indigenous_data_sovereignty_connector_guardrails_20260208.md`
  when iNaturalist signals are used near Indigenous knowledge or community
  stewardship contexts.
- Location precision must be minimized by default (hash + coarse region/cell).

