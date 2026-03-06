# Dashboard Implementation Notes (Repro Guide)

This note documents how the SB dashboard is built and laid out so others can
reproduce the same behavior/functionality.

For module ownership and safe iteration boundaries, see
`docs/web_module_map.md`.

## Build flow

1. `scripts/build_dashboard.py` parses CLI args (`--date`, `--debug`, `--weekly`,
   `--weekly-days`, custom output paths).
2. It calls `sb.dashboard.build_dashboard(...)` for the target day.
3. Daily payload is persisted canonically to SQLite via `sb/dashboard_store_sqlite.py`:
   - default DB: `SB_RUNS_ROOT/dashboard.sqlite`
   - keyed by `(date, view, scope, window_days)`
   Legacy JSON/HTML exports via `write_dashboard_outputs(...)` remain available for
   regression/debug only (opt-in flags).
4. If `--weekly` is set, `build_weekly_dashboard(...)` aggregates day payloads and
   persists a weekly payload to the same SQLite DB (with `view=weekly` and
   `window_days=<N>`). Optional legacy JSON/HTML exports remain opt-in.
5. If `--lifetime` is set, `build_lifetime_dashboard(...)` scans available
   `runs/YYYY-MM-DD` directories up to `--date` and writes
   a lifetime payload into the same SQLite DB (`view=lifetime`). Optional legacy
   JSON/HTML exports remain opt-in.
6. If `--lifetime` is set, `build_lifetime_costing_payload(...)` writes an
   indicative costing page:
   - persisted into SQLite (`view=costing`)
   - optional legacy JSON/HTML exports remain opt-in

## Data flow and source precedence

Chat ingestion precedence in `build_dashboard(...)`:

1. sqlite archive: `~/.chat_archive.sqlite`
2. chat export JSONs: `chat_exports/*.json`
3. resolver sync files: `__CONTEXT/last_sync/*`

Other daily signals:
- `runs/<date>/logs/cli/<date>.jsonl`
- `runs/<date>/logs/input/<date>.jsonl`
- `runs/<date>/logs/windows/<date>.jsonl`
- `runs/<date>/logs/git/<date>.jsonl`
- `runs/<date>/logs/git_branch/<date>.jsonl`
- `runs/<date>/logs/pr/<date>.jsonl`
- `runs/<date>/outputs/activity_ledger.json`

## Scope model (important)

- Default mode is `scoped`: chat is filtered using `__CONTEXT/convo_ids.md`.
- Debug mode (`--debug`) is `all`: scope filter disabled.

Weekly behavior:
- scoped weekly links each day to `runs/<date>/outputs/dashboard.html`
- all-chat weekly links each day to `runs/<date>/outputs/dashboard_all.html`

This prevents mismatches where weekly all-scope numbers link to scoped daily pages.

Lifetime behavior:
- Uses existing daily payloads from the canonical dashboard DB when present;
  otherwise builds missing daily payloads on demand.
- Includes aggregate state-volume metrics from each day `outputs/state.json`:
  - `raw_events` (estimated pre-compression via `collapsed_count`/`collapsed_ids`)
  - `compressed_events` (stored `events[]` length)
  - `junk_events_*` (`low_signal=true`)
  - compression ratio (`compressed/raw`)

## Metric model

Core chat context metrics:
- `context_switch_rate` (`switches / (messages - 1)`)
- `switches_per_active_hour`
- `messages_per_chat`
- `top_thread_share`
- `shell_commands` (combined):
  - host shell log events from `logs/cli/*.jsonl`
  - plus structured agent `exec_command` run requests parsed from chat tool rows
  - excludes printed/plain-text command mentions

Companion structures:
- `summary` (headline metrics)
- `chat_flow` (thread distribution + timeline strip sequence)
- `chat_context_trailing` (7-day prior baseline and deltas)

Cost/context estimate metrics:
- `chat_tokens_est` (chars/4 approximation)
- `chat_input_tokens_est` (user role bucket)
- `chat_output_tokens_est` (assistant+tool role bucket)
- `chat_context_overflow_threads` (threads over default context window)
- `chat_context_overflow_tokens` (overflow amount over default window)
- `chat_context_max_thread_usage_pct` (max thread usage vs default window)

Model details and caveats:
- `docs/api_costing_model.md`

## Daily page layout contract

Section order is stable:
1. Header meta
2. Summary cards
3. Frequency bars
4. Artifact links
5. Chat thread table
6. Chat flow timeline strip + legend
7. Tool-use summary
8. Timeline + filters
9. Warnings

If new sections are added, append rather than reorder existing sections unless
there is a migration reason.

## Responsive/typesetting behavior

Daily page responsiveness is intentionally handled in renderer CSS:
- `main` width clamps to viewport (`min(1200px, calc(100vw - ...))`)
- all large tables are wrapped in `.table-scroll` containers
- timeline strip uses dynamic segment sizing via CSS vars:
  - `--wf-seg-w`
  - `--wf-seg-h`
- segment size scales down as rendered message count increases
- timeline strip color mapping is runtime-selectable via palette control:
  - built-ins: `viridis`, `turbo`, `plasma`, `rdylgn`
  - custom: comma-separated CSS colors (`custom`)
  - selection/custom values persist in browser local storage
- timeline strip color algorithm is runtime-selectable:
  - `thread`
  - `hour` (time of day)
  - `role`
  - `switch` (switch vs stay)
  - selection persists in browser local storage

This keeps viewport overflow manageable on laptop/mobile while preserving
timeline sequence semantics.

## Alternate lane mode (planned)

The strip remains the dense-day default. A true lane chart mode is planned as
an alternate visual mode.

Specification:
- `docs/chat_flow_lane_mode.md`

Implementation target:
- add `Auto / Timeline Strip / Thread Lanes` selector,
- render lane nodes on thread rows with message-to-message connectors,
- auto-fallback to strip when thread/message density exceeds thresholds.

## Repro commands

Daily (scoped):

```bash
python scripts/build_dashboard.py --date 2026-02-08
```

Daily (all chat):

```bash
python scripts/build_dashboard.py --date 2026-02-08 --debug \
  --json-out runs/2026-02-08/outputs/dashboard_all.json \
  --html-out runs/2026-02-08/outputs/dashboard_all.html
```

Weekly (scoped):

```bash
python scripts/build_dashboard.py --date 2026-02-08 --weekly --weekly-days 14
```

Weekly (all chat):

```bash
python scripts/build_dashboard.py --date 2026-02-08 --weekly --weekly-days 14 --debug \
  --weekly-json-out runs/2026-02-08/outputs/dashboard_weekly_14d_all.json \
  --weekly-html-out runs/2026-02-08/outputs/dashboard_weekly_14d_all.html
```

Lifetime (scoped):

```bash
python scripts/build_dashboard.py --date 2026-02-08 --lifetime
```

Lifetime (all chat):

```bash
python scripts/build_dashboard.py --date 2026-02-08 --lifetime --debug \
  --lifetime-json-out runs/2026-02-08/outputs/dashboard_lifetime_all.json \
  --lifetime-html-out runs/2026-02-08/outputs/dashboard_lifetime_all.html
```
