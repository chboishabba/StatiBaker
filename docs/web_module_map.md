# SB Web Module Map (Current Implementation)

This guide is for frontend/web contributors who need to iterate quickly without
breaking the state pipeline.

## TL;DR Boundaries

- Treat `<runs-root>/<date>/outputs/dashboard*.json` as your primary UI contract.
- For UI-only changes, stay in renderer functions in `sb/dashboard.py`.
- For metric logic changes, edit `build_*_dashboard` in `sb/dashboard.py` and tests.
- For new signal lanes, add/normalize data in adapters and loaders first.

Runs root:
- Default: `runs_local/` (to avoid committing personal artifacts)
- Override: set `SB_RUNS_ROOT` or pass `--runs-root` to `scripts/build_dashboard.py`

## Execution Graph

```text
raw inputs -> adapters/* -> <runs-root>/<date>/logs/*.jsonl
snapshots  -> sb.activity.sessionize -> outputs/activity_ledger.json

logs + outputs + chat sources
  -> sb.dashboard.build_dashboard/build_weekly_dashboard/build_lifetime_dashboard
  -> <runs-root>/<date>/outputs/dashboard*.json
  -> <runs-root>/<date>/outputs/dashboard*.html
```

Primary entrypoints:
- `scripts/run_day.sh`: ingest + state artifact generation.
- `scripts/build_dashboard.py`: dashboard compile/render CLI.

## Module Responsibilities

### Dashboard Compiler and Renderer

- `sb/dashboard.py`
  - Role: Loads chat/log/activity artifacts, computes summaries, builds payloads,
    renders HTML for daily/weekly/lifetime dashboards, writes JSON/HTML outputs.
  - Key functions:
    - `build_dashboard(...)`
    - `build_weekly_dashboard(...)`
    - `build_lifetime_dashboard(...)`
    - `render_dashboard_html(...)`
    - `render_weekly_dashboard_html(...)`
    - `render_lifetime_dashboard_html(...)`
    - `write_*_outputs(...)`
  - Current client-side behavior (embedded JS in the HTML output):
    - Timeline filtering/search/reset (operates on the rendered table/rows; no server)
    - Chat-flow waterfall palette + algorithm selection (persists settings via `localStorage`)
  - Complexity note: this is currently a monolith (data loading + metrics + HTML +
    client JS) and is the main iteration bottleneck.

### State Pipeline Modules (Upstream of Dashboard)

- `sb/activity/sessionize.py`
  - Deterministic snapshot -> activity event sessionization.
  - Output consumed via `outputs/activity_ledger.json`.

- `sb/observed_ingest.py`
  - Converts observed log JSONL into safe event stubs for state assembly.

- `sb/fold.py`
  - Carryover fold logic across days (`carryover_*`, age windows).

- `sb/compress.py`
  - Low-signal event collapse/expand; writes compression loss profiles.

- `sb/drift.py`
  - Drift counters/flags from compiled state.

### Query, Packaging, and Metrics

- `sb/query.py` + `scripts/query_state.py`
  - Read-only query surface for activity/carryover/provenance.

- `sb/bundle.py` + `scripts/bundle_export.py` + `scripts/verify_bundle.py`
  - Bundle manifest/hash integrity.

- `sb/metrics.py` + `scripts/serve_metrics.py`
  - Minimal Prometheus-like metrics surface.

### Ingest Boundary Validation

- `sb/itir_ingest.py`
  - Validates overlay records crossing into SB surfaces.

## Web Iteration Surfaces

### Surface A: Styling/Markup only (low risk)

Edit only:
- `sb/dashboard.py` renderer functions (`render_*_html`).

Do not edit:
- loader/summary functions unless data semantics must change.

### Surface B: Metric cards/tables (medium risk)

Edit:
- `build_dashboard(...)` or weekly/lifetime aggregators.
- corresponding HTML rendering blocks.
- tests in `tests/test_dashboard.py`.

### Surface C: New timeline lane/signal (higher risk)

Typical chain:
1. Add/normalize adapter output in `adapters/*.py`.
2. Add loader in `sb/dashboard.py` (`_load_*_events`).
3. Merge into `all_events` + `frequency_by_hour` + summary fields.
4. Add UI rendering and tests.

## Data Contracts Web Team Should Rely On

Daily dashboard payload keys (stable in practice):
- `date`, `generated_at`, `chat_source`, `chat_scope_mode`
- `summary`
- `frequency_by_hour`
- `chat_flow`
- `chat_threads`
- `tool_use_summary`
- `notes_meta_summary`
- `timeline`
- `artifact_links`
- `warnings`

Weekly/lifetime payloads:
- `period_start`, `period_end`, `days`, `generated_at`, `chat_scope_mode`
- `totals`, `averages_per_day`, `chat_context_averages`
- `daily`, `warnings`
- `weekday_hour_heatmaps` (weekday x hour heatmap aggregates; includes lanes, labels, totals, default selection; used for "When You Work" views)
- Lifetime adds state-volume blocks: `state_totals`, `state_averages_per_day`,
  `state_ratios`, `state_definitions`.

## Change Safety Checklist

Before merging dashboard changes:
1. Run `tests/test_dashboard.py`.
2. If state semantics changed, also run `tests/test_fold.py`,
   `tests/test_compress_expand.py`, `tests/test_drift.py`.
3. Rebuild at least one real day:
   - `python scripts/build_dashboard.py --date YYYY-MM-DD`
4. Verify both:
   - DB-backed payload fields expected by UI still exist (canonical store: `SB_RUNS_ROOT/dashboard.sqlite`).
   - Optional legacy HTML export still loads with timeline filtering and waterfall controls (if you rely on it).

## Immediate Refactor Targets (to reduce web iteration friction)

1. Extract chat/log loaders from `sb/dashboard.py` into `sb/dashboard_loaders.py`.
2. Extract metric assembly into `sb/dashboard_metrics.py`.
3. Keep renderers in `sb/dashboard_render.py` and weekly/lifetime renderers separate.
4. Add a lightweight schema file for `dashboard.json` output to protect UI contracts.
   - DB-first: keep the schema as the canonical contract for DB reconstruction, even
     if JSON files are no longer written by default.

This keeps frontend iteration mostly isolated to rendering and stable payload
contracts, instead of forcing edits across ingestion and metric internals.

For Svelte component migration sequencing, see:
- `docs/svelte_migration_sprint.md`
