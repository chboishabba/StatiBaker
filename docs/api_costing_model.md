# Chat Context + API Costing Model (Indicative)

This document defines the **non-authoritative** estimation model used by SB for:

- per-chat context usage approximation,
- context window overflow approximation,
- indicative API cost projections.

These estimates are for planning and comparison only, not billing truth.

## Why this exists

Large-agent workflows can burn cost quickly when context/state is unmanaged.
SB should make this visible and support orchestration choices that reduce waste,
even without any increase in base model skill.

## Inputs

- Daily chat events already ingested by SB (`kind=chat`).
- Metadata fields where available:
  - `role`
  - `chars`
  - `thread_id` / `thread_title`

No API provider billing logs are required for the estimate baseline.

## Token estimation rule

Default approximation:

- `estimated_tokens = max(1, round(chars / 4.0))`

Role buckets:

- `input_tokens_est`: user role
- `output_tokens_est`: assistant and tool roles
- `other_tokens_est`: all remaining roles

## Per-thread context usage approximation

For each thread (day-scoped events):

- `thread_tokens_est` = sum of estimated tokens in that thread
- `usage_pct = thread_tokens_est / context_window_tokens`
- `overflow_tokens = max(0, thread_tokens_est - context_window_tokens)`

Default context window:

- `context_window_tokens = 128000`

Reference windows for comparison:

- `32000`
- `128000`
- `200000`

## Indicative API costing rule

Cost projection uses role-bucket token estimates:

- `cost_est = (input_tokens_est / 1_000_000 * input_usd_per_mtok) + (output_tokens_est / 1_000_000 * output_usd_per_mtok)`

SB ships non-provider-specific example profiles only.
Rates are editable assumptions, not live provider pricing.

## Output surfaces

- Daily dashboard:
  - context usage summary cards
  - per-thread context usage table (estimated)
- Lifetime costing page:
  - period totals and per-day token/cost estimates
  - editable profile assumptions and formula disclosure

## Known limitations

- Day-scoped only; full-thread lifetime context may be higher.
- Char-based token estimation is approximate.
- Role attribution depends on source quality.
- No direct reconciliation with provider invoices unless billing logs are ingested.

## Planned evidence upgrade

When available, ingest historical provider usage/billing logs (including Claude
spend incidents) to reconcile estimate-vs-actual and calibrate heuristics.

Goal remains:

- reduce unnecessary spend through state coordination/orchestration,
- avoid uncontrolled context replay loops,
- preserve auditability for cost drivers.
