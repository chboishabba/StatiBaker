# SB Frontend Migration Sprint (Svelte Componentization)

## Decision Check

Thread `69882c94-3094-839a-b539-15529d7e9c6c` shows the practical choice as:
- `SvelteKit + Tailwind` for rapid visual iteration.
- `React + Vite + Tailwind` as fallback for ecosystem depth.

For this migration plan, treat `SvelteKit + Tailwind` as the working target.

Immediate next sprint (actionable checklist from the current repo state):
- `docs/sb_ui_migration_sprint_0.md`

## Current Constraint (Why migration is needed)

Current dashboard rendering is monolithic in `sb/dashboard.py`:
- `render_dashboard_html(...)` in `sb/dashboard.py:1842`
- `render_weekly_dashboard_html(...)` in `sb/dashboard.py:3314`
- `render_lifetime_dashboard_html(...)` in `sb/dashboard.py:3461`

Data compile + render are coupled in the same module:
- `build_dashboard(...)` in `sb/dashboard.py:2751`
- `build_weekly_dashboard(...)` in `sb/dashboard.py:2926`
- `build_lifetime_dashboard(...)` in `sb/dashboard.py:3086`

Layout contract already exists and should drive component boundaries:
- `docs/dashboard_implementation_notes.md:77`

## Target Architecture

Keep Python as data compiler. Move UI to Svelte.

```text
raw logs/artifacts -> sb.dashboard build_* -> dashboard*.json
                                      -> (legacy html stays during transition)

dashboard*.json -> SvelteKit loaders -> typed stores -> Svelte components
```

## Component Map (1:1 with current page contract)

1. `DashboardHeader.svelte`
2. `SummaryCards.svelte`
3. `FrequencyBars.svelte`
4. `ArtifactLinks.svelte`
5. `ChatThreadsTable.svelte`
6. `ChatFlowWaterfall.svelte`
7. `ToolUseSummary.svelte`
8. `TimelinePanel.svelte`
9. `WarningsPanel.svelte`

Cross-cutting:
- `DashboardShell.svelte` (layout)
- `FilterBar.svelte` (timeline filters/search)
- `useWaterfallColors.ts` (palette + algo + localStorage)
- `types/dashboard.ts` (payload contracts)

## Sprint Plan

## Sprint 0 (2-3 days): Freeze Contracts + Bootstrap Svelte

- Lock payload fields consumed by UI (`summary`, `chat_flow`, `timeline`, etc.).
- Add JSON schema for dashboard payload (or zod runtime validation).
- Scaffold `frontend/sb-dashboard` with `SvelteKit + Tailwind`.
- Add data adapter that loads existing `runs/<date>/outputs/dashboard*.json`.

Done when:
- Svelte app loads a real `dashboard.json` and validates payload shape.

## Sprint 1 (4-5 days): Daily View Component Parity (No Behavior Changes)

- Implement components 1-5 and 9.
- Reproduce visual section order from `docs/dashboard_implementation_notes.md:79`.
- Keep CSS behavior equivalent (table scroll, responsive containers).

Done when:
- Daily page static parity achieved for key sections.

## Sprint 2 (4-5 days): Interactive Panels Port

- Implement `ChatFlowWaterfall.svelte`, `ToolUseSummary.svelte`, `TimelinePanel.svelte`.
- Port current inline JS behavior from `sb/dashboard.py` to Svelte stores/actions:
  - timeline filters/search/reset
  - waterfall palette/algo/custom colors + localStorage persistence
- Add timeline row virtualization if needed for large runs.

Done when:
- Svelte interactions match existing HTML behavior on a known run date.

## Sprint 3 (3-4 days): Weekly/Lifetime Pages + Routing

- Add weekly and lifetime routes/components.
- Reuse shared metric/table components where possible.
- Keep link semantics to daily artifacts consistent.

Done when:
- `daily`, `weekly`, and `lifetime` pages all run from existing JSON outputs.

## Sprint 4 (2-3 days): Backend Decoupling Cleanup

- Split `sb/dashboard.py` into:
  - `sb/dashboard_loaders.py`
  - `sb/dashboard_metrics.py`
  - `sb/dashboard_render_legacy.py` (temporary)
- Keep `write_*_outputs` writing JSON; legacy HTML becomes optional/deprecated.

Done when:
- UI team can iterate in Svelte without touching backend render code.

## Migration Risk Controls

- Keep JSON outputs as source of truth during transition.
- Keep legacy HTML generation until Svelte parity sign-off.
- Add fixture snapshots for daily/weekly/lifetime payloads.
- Gate with existing tests + new payload contract tests.

## Minimal Acceptance Gate

1. Existing `tests/test_dashboard.py` pass.
2. New frontend contract test passes against sampled payloads.
3. Svelte daily route renders a real date without runtime errors.
4. Timeline filters and waterfall color controls are functionally equivalent.
