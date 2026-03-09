# TODO

## Completed (2026-02-03)
- Drafted human daily brief and retrospective templates (`BRIEF_TEMPLATE.md`)
- Defined machine state JSON schema (`STATE_SCHEMA.json`)
- Created synthetic sample state (`SAMPLE_STATE.json`)
- Specified append-only ingestion formats (`INGESTION_FORMATS.md`)

## Completed (2026-02-05)
- Drafted ADR for Recall-class capture + activity events
- Added snapshot and activity_event schema stubs to `STATE_SCHEMA.json`
- Drafted sessionization spec (`SESSIONIZATION_SPEC.md`)
- Implemented deterministic sessionizer stub with provenance ledger
- Added golden snapshot fixtures and tests for sessionization
- Added sessionizer config file and Makefile targets
- Added sessionizer config validation and Justfile targets
- Added config validation tests and CLI error handling
- Added CLI exit-code test for invalid config
- Added "core questions + context prosthesis" section to `CONTEXT.md`
- Added ADR: external signal condensers (Wazuh, osquery) are non-authoritative observers
- Implemented carryover window counts (7/14/30) in minimal fold + schema
- Included carryover deltas in generated daily brief
- Generated a sample daily brief from real logs
- Added guard tests for fold non-mutation and no content summarization.
- Ran multi-day replay (2026-02-06 to 2026-02-08) to validate deterministic carryover aging.
- Added Wazuh lifecycle adapter (structured, lifecycle-only).
- Added metrics HTTP server for `/metrics` over baked state outputs.
- Added determinism tests for adapter outputs and Prometheus summary helpers.
- Drafted OCR/Android/query/ITIR ingest contracts.
- Added ITIR overlay validation helper and tests.
- Implemented drift counters (separate `drift.json`) + drift doc.
- Implemented Phase-2 compression collapse for `low_signal=true` events.
- Added read-only query CLI (`scripts/query_state.py`).
- Added bundle export/verify tooling and spec.
- Documented time hygiene policy and failure modes.
- Added red-team boundary tests and bundle verification tests.
- Expanded red-team plan and added injection/RCE/metric-smuggling/env-leak tests.
- Added inactivity run test for empty git repositories.
- Added bundle export/replay test (export + verify).

## Completed (2026-02-06)
- Expanded red-team plan to cover DoS/resource exhaustion, path traversal, and
  blast-radius constraints.
- Updated failure-mode catalog with explicit blast-radius definition and limits.
- Added query base-path guard for safe reads with optional CLI enforcement.
- Extended ITIR ingest contract with explicit forbidden fields.

## Completed (2026-02-08)
- Added activity dashboard contract doc (`docs/activity_dashboard.md`) for
  read-only process-lens requirements and invariants.
- Implemented daily dashboard generation for chat/CLI/input/window/activity
  timelines with per-hour frequency summaries and artifact linkbacks.
- Added git branch history ingestion (`adapters/git_branch.py`) and integrated
  branch events into dashboard timeline/frequency summaries.
- Added PR lifecycle ingestion (`adapters/pr_events.py`) and integrated
  receive/comment/merge event counts into dashboard outputs.
- Added direct GitHub PR connector (`adapters/pr_events_github.py`) and wired
  `run_day.sh` arg 19 (`auto` or `owner/repo`) for day-scoped PR ingestion.
- Added static HTML and machine-readable JSON outputs under
  `runs/<date>/outputs/`.
- Added test coverage for mixed-source aggregation and context-link surfacing.
- Added optional weekly dashboard view to summarize daily dashboard outputs over
  rolling windows ending at a selected date.
- Added dashboard tool-use summary section that parses chat `tool` messages
  into grouped command variants and directory-touch counts.
- Tightened timeline UI for dense days with foldable long rows, source badges,
  and explicit `chars` display for chat events.
- Added optional timeline filters (kind/source/chat-role/text search) and
  untitled-thread fallback titles + origin labels (`codex-ingest`, etc).
- Grouped `rg` tool-use variants by mode (`--files`, `-n`) with only differing
  arguments shown per subgroup.

## In Progress (2026-02-08) - Media connectors + churn metrics
- [ ] Add unified `media_consumption` adapter contract (meta-only).
- [ ] Add stub connectors for YouTube, Spotify, VLC, and Last.fm export JSONL.
- [ ] Wire `run_day.sh` to ingest media input into `logs/media/<date>.jsonl`.
- [ ] Add daily/weekly/lifetime dashboard metrics:
  watch/listen seconds, completion ratio, churn events/rate.
- [ ] Add tests for adapter normalization and dashboard aggregation.
- [ ] Add docs for connector mappings and churn heuristic.

### Deferred / decisions needed
- [ ] Decide live API collectors scope (YouTube API, Spotify Web API, Last.fm API)
  vs export-file-only ingestion in default flow.
- [ ] Decide per-platform identity linkage policy (single person/account merge vs
  separate hashed identities).

## In Progress (2026-02-08) - Cross-platform daemon + web management
- [ ] Implement `sb-supervisor` local daemon skeleton with connector registry.
- [ ] Add localhost control API endpoints for connector/job management.
- [ ] Add web UI panel to manage connectors (enable/disable/schedule/run-now).
- [ ] Add cross-platform service installers:
  Linux systemd user service, macOS launchd agent, Windows service/task mode.
- [ ] Move NotebookLM wrapper flow under daemon jobs (capture/normalize/run_day).
- [ ] Add local SQLite persistence for daemon jobs/events/artifacts.
- [ ] Add retention policy and dedupe strategy for snapshot archival.

### Deferred / decisions needed
- [ ] Confirm auth model for localhost mutation endpoints.
- [ ] Confirm Windows service wrapper strategy.
- [ ] Confirm daemon log storage model (SQLite vs file+index).

## In Progress (2026-02-08) - Chat flow lane mode (alternate view)
- [ ] Add chat flow mode selector: `Auto / Timeline Strip / Thread Lanes`.
- [ ] Extend `chat_flow` payload with lane data (`lanes`, `lane_points`,
  `lane_edges`, availability/blockers).
- [ ] Render lane-mode SVG/canvas with message nodes and transition connectors.
- [ ] Emphasize cross-lane switch connectors while preserving switch counts.
- [ ] Add auto-fallback thresholds for dense days (message/thread counts).
- [ ] Add UI fallback reason text when lane mode is unavailable.
- [ ] Add tests for deterministic lane layout and mode-selection thresholds.

## In Progress (2026-02-08) - Chat context usage + indicative API costing
- [ ] Add per-chat context usage approximation (`chars -> tokens`) with
  per-thread usage/overflow estimates against configurable context windows.
- [ ] Add daily dashboard section for context usage and overflow diagnostics.
- [ ] Add lifetime costing page (`dashboard_costing(.json|.html)`) with
  scenario-based token/cost estimates (input vs output token buckets).
- [ ] Add warning/assumption text that costing is indicative and non-authoritative
  unless reconciled against provider billing logs.
- [ ] Add tests for token/context aggregation and costing page rendering.

### Deferred / decisions needed
- [ ] Ingest provider usage/billing logs when available (including historical
  Claude incidents) to calibrate estimate-vs-actual accuracy.
- [ ] Decide supported provider profile presets and where pricing assumptions are
  configured.
- [ ] Add benchmark target: demonstrate spend reduction via orchestration/state
  coordination improvements, even when base agent skill level is unchanged.

## Sprint plan references (2026-02-05)
- Sprint plan: `__CONTEXT/sprints/stati_baker_sprints.md`.
- Sprint 1 focus: guard tests + multi-day replay (see "Normalization and compression (Phase 1: minimal fold)").
- Sprint 2 focus: Wazuh lifecycle + Prometheus summaries + `/metrics` (see "Integration roadmap" and "Observability").
- Sprint 3 focus: OCR/Android/read-only contracts (see "Integration roadmap" and "Governance and safety").

## Define intent and scope
- Sprint plan reference: `__CONTEXT/sprints/stati_baker_sprints.md`.
- Review daily brief template and finalize fields
- Validate machine state JSON schema with real samples
- Confirm minimal event/thread/trajectory model
- Define and document epistemic layers in `STATE_SCHEMA.json`

## Normalization and compression (Phase 1: minimal fold)
- Define carryover thread detection
- Specify temporal reduction rules (carryover/new/resolved sets, age_days counters) for atoms and threads

## Normalization and compression (Phase 2: advanced)
- Define rules for event extraction and thread grouping
- Draft redundancy and failure-collapse heuristics
- Specify fold definitions and loss profiles (create `FOLDS.md`)
- Define SB atom/handle types (event_id, thread_id, atom_id, constraint_id, annotation_id) and allowed fields
- Define loss-profile metadata and expansion contract for SITREP lines (lossy index rules)
- Note: align compression diagnostics with SensibLaw work (entropy proxy + compression ratio guards, deterministic stability tests) to reuse methodology where applicable.

## Emission (early feedback loop)
- Produce a sample agent JSON state from real logs
- Define retrospective summary format for real data

## Integration roadmap (order by determinism)
- Git log ingestion adapter
- Calendar ingestion adapter
- Wazuh adapter (system lifecycle only)
- Prometheus adapter (summaries only; must not create/split activity_events)
- Input activity adapter (keyboard/mouse counts only)
- Window/app focus adapter (title hashed, no content)
- Browser usage adapter (domain hash + duration only)
- Antivirus/endpoint status adapter (counts only)
- Cloud audit adapters (Google Drive + MS365; read-only)
- Notes app metadata adapters (Obsidian + Evernote; file events only)
- Social feed adapters (Bluesky + other socials; meta-only)
- Android status adapter (ADB/Termux/Wazuh agent)
- Agent log adapters
- Tool execution envelope adapter (OpenClaw or similar; evidence-only)
- Smart home status adapter
- Pet wearable / smart collar stub adapter (meta-only context overlay)
- PR lifecycle adapter (receive/comment/review/merge events)
- TIRC event adapter (trajectory/open/closed signals as SB events)
- SL constraint adapter (rule/constraint IDs with refs only)
- ITIR overlay adapter (annotation IDs, no content)
  - current bounded extension: accept `itir_mission_graph_v1` observer overlays
    with `mission_refs` + `evidence_refs`, while still rejecting thread/event
    dumps and any mutation-shaped fields
  - [x] persist accepted ITIR mission observer overlays into DB-backed SB
    tables (`sb_itir_overlays`, `sb_itir_mission_refs`,
    `sb_itir_evidence_refs`) instead of leaving the lane validation-only
- [x] Start the fused mission-lens bridge from the SB side by rendering
  ITIR-owned mission/planning artifacts against canonical dashboard DB payloads
  rather than inventing a separate spend surface.
- Read-only query surface for agents (MCP or equivalent)

## Interop boundary follow-up (2026-02-07)
- Define a minimal observer event schema for external orchestration tools
  (`session_started`, `session_completed`, `pr_opened`, `pr_merged`, `ci_finished`).
- Add read-only ingest adapter for execution-plane provenance pointers
  (issue/PR/commit/CI run IDs only; no semantic authority).
- Add guard tests that reject workflow-enforcement fields and inferred goals.
- Add export view for timeline lens consumers (CodexMonitor-style panels) without
  granting mutation authority. (done: `scripts/build_dashboard.py`)

## Observability (Prometheus / Grafana)
- Define SB metrics surface (`/metrics`)
- Add a minimal HTTP metrics server for `sb.metrics.render_metrics`
- Specify allowed metric ingestion classes (numeric only)
- Add Prometheus adapter for time-window summaries
- Add determinism tests for adapter outputs (fixed inputs → stable JSONL)
- Define Grafana dashboards scoped to activity_event windows
- Grafana dashboard (current):
```
https://truenas.local:30037/d/truenas-overview4/truenas-scale-overview4
```
- Prometheus source: TrueNAS scrape with Graphite exporter metrics at `http://truenas.local:9109/metrics`
- InfluxDB (Home Assistant) is optional; requires confirmed credentials and live data
- Add guardrails: no semantic labels, no content promotion, and metrics must not create/split activity_events

## Observed capture / Recall-class substrate (optional)
- Define snapshot event schema for screen/app capture (append-only, content-addressed)
- Define `activity_event` schema and deterministic sessionization rules
- Implement SB sessionizer (deterministic, testable, golden snapshot fixtures)
- Emit SB activity_event ledger with provenance (algorithm, input hash, policy receipt)
- Add ITIR ingest adapter for SB activity_events (no re-segmentation)
- Document Wayland-first capture strategy with X11 legacy flag
- Specify OCR/embedding policy gates and redaction rules for sensitive apps
- Sketch timeline UI model: event cards + scrubber with event expansion
- Invariant: Recall-class capture is evidence-only and may not influence segmentation without SB policy

## External signal providers (reference index)
- Wazuh: lifecycle and failures; ignore alert semantics
- osquery: curated facts snapshots only
- Prometheus: numeric summaries only
- iNaturalist: biodiversity observation metadata (hashed IDs + coarse location only)
- OpenRecall: visual evidence only
  - keep raw OpenRecall rows out of SB direct ingest
  - prefer ITIR-normalized observer overlays if capture-derived signals ever
    need to cross into SB
- Android: coarse status only

## Governance and safety
- Create ADRs directory and add ADRs for folds and OCR guardrails
- Define promotion rules and consent UX copy in a canonical policy doc
- Add tests/fixtures for “no silent promotion” behavior

## Open questions
- How to represent and score drift signals
- What level of agent autonomy defaults are safe
- Which export format is the canonical portable bundle
- How to represent execution envelopes in `STATE_SCHEMA.json` without granting authority
- How to surface epistemic modes without implying promotion or authority

## UI Migration (SvelteKit)

This is not exercised today. Current dashboards are rendered by Python in
`sb/dashboard.py` and tested via `tests/test_dashboard.py`.

DB-first dashboard storage:
- Make SQLite the canonical dashboard store (e.g. `SB_RUNS_ROOT/dashboard.sqlite`).
- Stop writing new `dashboard*.json` files by default; keep JSON/HTML export only for regression/debug.
- Add regression tests that round-trip DB -> payload and compare against existing `runs/<date>/outputs/dashboard*_all.json` fixtures when present.

Sprint 0 (contracts + scaffold):
- Plan: `docs/sb_ui_migration_sprint_0.md`
- Migration overview: `docs/svelte_migration_sprint.md`
- Module boundaries: `docs/web_module_map.md`

Sprint 0 checklist:
- Add `DASHBOARD_SCHEMA.json` for `runs/<date>/outputs/dashboard.json`.
- Add payload fixtures under `fixtures/dashboard_payloads/`.
- Emit `payload_version` in dashboard JSON outputs (e.g. `"dashboard.v1"`).
- Scaffold `frontend/sb-dashboard` (SvelteKit) and load a real daily payload.
- Add runtime validation in the app (zod or schema validator) with a clear error panel.

## Sprint 4–6 (next arc)
- Sprint 4: run bad-data runs + manual brief review (drift counters done, bad-data tests added; manual review pending).
- Sprint 5: add expansion tests for Phase-2 compression and document loss profile usage.
- Sprint 6: add agent containment rules to docs and enforce ITIR overlay rejection on mutation attempts.

## Sprint 7–9 (next arc)
- Sprint 7: run bundle replay cross-host test (same outputs or explicit reject). (done)
- Sprint 8: implement carryover saturation label and inactivity stress runs. (done)
- Sprint 9: add metric-smuggling rejection tests (semantic labels) and document responses. (done)
- Sprint 9: add red-team tests for event injection, command/RCE payloads, and credential leakage. (done)
- Sprint 9: add tests for provenance laundering and systemic dependency failure. (done)
