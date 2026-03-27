# Changelog

## 2026-03-27
- Added an explicit Corkysoft -> StatiBaker seam on the SB side:
  - `sb.corkysoft_mcp` provides a read-only local bridge client for Corkysoft
    MCP v1 tools.
  - `sb.corkysoft_ingest` validates and persists reviewed Corkysoft downstream
    events as `corkysoft_review_event_v1` overlays.
- Extended `sb.dashboard_store_sqlite` and `sb.itir_ingest` so Corkysoft
  reviewed-event overlays retain family metadata, object refs, provenance refs,
  evidence refs, and compact payloads without weakening existing SB authority
  boundaries.
- Added `scripts/corkysoft_consume.py` as a practical SB-side consumer workflow
  for read-only Corkysoft MCP calls and reviewed-event ingest.
- Extended dashboard/query read-models so Corkysoft reviewed events are visible
  in dashboard payloads/HTML and queryable through `scripts/query_state.py
  corkysoft-reviews`.
- Added targeted regression coverage for the new MCP client, reviewed-event
  ingest/persistence path, dashboard exposure, and seeded end-to-end Corkysoft
  integration flow.

## 2026-03-24
- Added Google commitment ingest as a new SB observer lane:
  - `adapters/google_tasks.py` normalizes Google Tasks rows into
    `external_commitment_event_v1`
  - `adapters/google_keep_lists.py` normalizes Google Keep/list rows into the
    same family while preserving `source_kind`
  - `scripts/run_day.sh` now accepts arg 24 (`GOOGLE_TASKS_INPUT`) and arg 25
    (`GOOGLE_KEEP_LISTS_INPUT`) and appends both into
    `logs/commitments/<date>.jsonl`
- Extended daily dashboard payloads and HTML with:
  - external commitment summaries (total/open/completed/archived)
  - voice-origin and source-kind accounting
  - read-only projection lanes for commitment rows
  - `task_completion_candidate_v1` review surfaces
- Added a conservative SB-side completion-candidate generator that emits
  proposal-only candidates from explicit activity/title token matches without
  mutating source task systems.
- Added read-only query support for dashboard commitment feeds and completion
  candidates in `sb/query.py` and `scripts/query_state.py`.
- Updated docs/TODOs to document the new Google commitment connectors, the
  propose-only completion-candidate seam, and the continued non-authoritative
  Kanban/projection posture.
- Added regression coverage for Google commitment adapter normalization,
  dashboard aggregation/projection, and commitment/candidate query reads.

## 2026-03-20
- Tightened artifact-hygiene posture in `README.md` and
  `docs/activity_dashboard.md` to make private runs under `runs_local/` /
  `SB_RUNS_ROOT` the explicit default for contributors.
- Stopped treating `runs/dashboard.sqlite` as a normal tracked sample artifact:
  added it to `.gitignore` and removed it from git tracking so local/personal
  dashboard state stays private by default.

## 2026-03-11
- Clarified NotebookLM posture in docs: current `notes_meta` capture is a
  metadata/review/source lane, not honest waterfall/timeline activity parity.
  The dashboard may surface lifecycle counts, hour bins, synthetic tool-use
  family rows, and metadata-backed thread views, but fuller usage accounting
  is deferred until a separate interaction-grade NotebookLM capture contract
  exists.
- Added the first separate NotebookLM interaction lane without changing
  dashboard accounting semantics. `scripts/capture_notebooklm_activity.py`
  now captures bounded conversation-history and note observations,
  `adapters/notebooklm_activity.py` normalizes them under
  `signal: notebooklm_activity`, and `scripts/run_day_notebooklm_auto.sh`
  now emits raw/normalized interaction outputs beside the existing
  NotebookLM metadata artifacts while keeping them out of `run_day.sh`
  ingestion and sessionized usage accounting.
- Fixed Tool Use Summary hydration coupling at the SB reducer layer:
  - `Shell/hour` now bins agent `exec_command` tool messages by timestamp hour
    (in addition to host CLI logs).
  - `Input/hour` now bins agent `request_user_input` tool messages by timestamp
    hour (in addition to host input logs).
- Extended `tool_use_summary` payloads with:
  - `exec_command_hour_bins`
  - `request_user_input_count`
  - `request_user_input_hour_bins`
  - `notebooklm_meta_event_count`
  - `notebooklm_meta_hour_bins`
  - synthetic `families[].family = "notebooklm_meta_event"` entries derived
    from NotebookLM notes-meta events
- Updated dashboard daily summary fields to expose `input_events_host` and
  `input_events_agent_request_user_input`, with `input_events` representing the
  combined count.
- Added dashboard regression coverage for the new shell/input hour hydration
  behavior sourced from chat-archive tool messages.
- Assumption-stress `A2/Q2` fold hardening:
  - `sb.fold.apply_minimal_fold(...)` now emits explicit machine-readable
    `fold_policy` metadata with:
    - `policy_receipt` (`receipt_id`, `policy_id`, `applied_on`)
    - `mechanical_should_flags` (boolean-only fold controls)
    - explicit `loss_profile` declaration (`sb.fold.loss_profile.v1`)
  - Added anti-nudge red-team tests to ensure fold-policy/loss-profile surfaces
    do not drift into imperative free-text guidance.

## 2026-03-09
- Clarified the `fuzzymodo -> StatiBaker` boundary as observer-only and
  reference-heavy in `docs/interfaces.md` and
  `docs/tool_interop_observer_contract.md`, aligned to suite note
  `docs/planning/fuzzymodo_statiBaker_interface_20260309.md`.
- Added the parallel `casey-git-clone -> StatiBaker` boundary note and aligned
  SB interface/observer docs to treat Casey workspace/collapse/build receipts as
  DB-backed observer-class refs rather than mutable canonical state.

## 2026-03-08
- Extended the ITIR ingest boundary to accept a bounded mission/follow-up
  observer payload (`observer_kind = itir_mission_graph_v1`) so long as it
  stays reference-heavy (`mission_refs` + `evidence_refs`) and does not inject
  raw thread/event dumps or mutation-shaped fields.
- Added ingest/boundary tests covering acceptance of the new mission observer
  overlay and rejection of thread-dump attempts on that lane.
- Added DB-backed persistence for accepted ITIR mission observer overlays in
  `sb/dashboard_store_sqlite.py` via `sb_itir_overlays`,
  `sb_itir_mission_refs`, and `sb_itir_evidence_refs`, keeping the payload
  reference-heavy while making the SB side of the seam storage-backed too.
- Added the first fused mission-lens consumption path on the UI side: SB
  dashboard DB payloads can now be rendered alongside ITIR-owned mission
  planning artifacts in `itir-svelte` without making SB the planning authority.

## 2026-02-14
- Made SQLite the canonical dashboard store (DB-first) via `sb/dashboard_store_sqlite.py` (normalized tables; no persisted payload JSON blobs).
- Updated `scripts/build_dashboard.py` to persist daily/weekly/lifetime/costing payloads into `SB_RUNS_ROOT/dashboard.sqlite` by default.
- Added `scripts/query_dashboard_db.py` for deterministic DB-backed dashboard hydration (stdout JSON for callers; DB remains canonical).
- Updated docs/TODOs to treat `dashboard*.json` as legacy/regression/debug exports rather than canonical outputs.
- Added regression tests that round-trip DB persistence and (when present) compare against existing `runs/<date>/outputs/dashboard*_all.json` fixtures.

## 2026-02-11
- Extended NotebookLM snapshot capture (`scripts/capture_notebooklm_meta.py`)
  to ingest per-notebook artifact listings (`artifact_observed`) and optional
  source-guide snippets/keywords (`--with-source-guides`).
- Added capture controls for NotebookLM metadata breadth:
  `--no-artifacts`, `--with-source-guides`, and `--source-snippet-chars`.
- Updated NotebookLM normalization (`adapters/notebooklm_meta.py`) to preserve
  display fields for local UX (notebook/source/artifact title/type/status/url
  and snippet fields) while keeping hashed identifiers for join keys.
- Added adapter test coverage for NotebookLM display-field preservation and
  artifact event expansion (`tests/test_observed_signals_meta_only.py`).
- Updated NotebookLM ingestion docs/contracts (`docs/notebooklm_connector.md`,
  `INGESTION_FORMATS.md`, `README.md`) to document lifecycle + snippet-bearing
  metadata behavior.

## 2026-02-08
- Documented chat-flow visual semantics split:
  - current `Timeline Strip` mode (linear sequence),
  - planned true `Thread Lanes` alternate mode with connectors and dense-day fallback policy.
- Added lane-mode design spec in `docs/chat_flow_lane_mode.md`.
- Updated dashboard docs and references to use timeline-strip wording and link
  lane-mode spec (`docs/activity_dashboard.md`, `docs/dashboard_implementation_notes.md`,
  `docs/INDEX.md`, `README.md`).
- Added TODO execution track for lane-mode implementation milestones (`TODO.md`).
- Added cross-platform daemon/web control plane design spec in
  `docs/daemon_web_control_plane.md` (Linux/macOS/Windows service model,
  localhost control API, connector/job orchestration, and local SQLite state).
- Updated NotebookLM connector docs to position daemon-managed scheduling as the
  recommended target mode (`docs/notebooklm_connector.md`).
- Updated docs index/references to include daemon control plane design
  (`README.md`, `docs/INDEX.md`, `docs/collectors_index.md`).
- Added TODO execution track for `sb-supervisor` implementation and web-managed
  connector/job controls (`TODO.md`).
- Added process-lens dashboard contract in `docs/activity_dashboard.md` and
  linked it from `README.md` and `docs/INDEX.md`.
- Added `sb.dashboard` builder to compile day-scoped timeline/frequency views
  from chat, shell, input, window, git, git-branch, PR, and activity-ledger
  sources.
- Added `scripts/build_dashboard.py` to emit
  `runs/<date>/outputs/dashboard.json` and `dashboard.html`.
- Added `adapters/git_branch.py` to ingest local git reflog branch-history
  events by day.
- Added `adapters/pr_events.py` to normalize PR lifecycle events
  (receive/comment/review/merge/close) into metadata-only JSONL.
- Added `adapters/pr_events_github.py` to fetch PR lifecycle events directly
  from GitHub via `gh api`.
- Updated `scripts/run_day.sh` to emit `logs/git_branch/<date>.jsonl` and
  optionally ingest PR events into `logs/pr/<date>.jsonl` from either JSONL
  input (arg 18) or direct GitHub connector (arg 19: `auto` or `owner/repo`).
- Added dashboard test coverage in `tests/test_dashboard.py` for mixed-source
  aggregation and process-context artifact linkbacks.
- Added dashboard debug mode (`scripts/build_dashboard.py --debug`) to bypass
  `convo_ids` chat scoping and scan all chat threads for the selected date.
- Added optional weekly dashboard summary output via
  `scripts/build_dashboard.py --weekly --weekly-days <N>` producing
  `dashboard_weekly_<N>d.json/html`.
- Added tool-use summary extraction in dashboard output from chat `tool`
  messages (command family grouping, variant counts, and directories touched).
- Updated timeline rendering to improve signal density:
  source badges with hover-path metadata, explicit `chars` column, short thread
  IDs for untitled threads, and foldable long-detail rows.
- Added optional in-page timeline filters (kind/source/chat-role/text search)
  and reset controls for dense debug days.
- Added untitled-thread fallback naming from first user message preview plus
  thread-origin labeling (including explicit `codex-ingest` for codex source IDs).
- Updated tool-use `rg` variant rendering to group by mode (`--files`, `-n`)
  and list only the distinguishing arguments under each mode.
- Added dashboard implementation reproducibility guide in
  `docs/dashboard_implementation_notes.md` and linked it from docs index.
- Updated daily dashboard renderer for viewport safety: horizontal table
  containers plus dynamic waterfall segment scaling for dense message days.
- Added waterfall palette controls (`viridis`, `turbo`, `plasma`, `rdylgn`,
  and custom comma-separated CSS colors persisted in local storage).
- Added waterfall color-algorithm controls (`thread`, `hour`, `role`,
  `switch`) so palettes can be applied by thread identity, time-of-day, role,
  or switch-state.
- Updated waterfall rendering to scale block width by elapsed time to the next
  message (instead of fixed-width blocks), and clarified legend percentages as
  explicit share of total chat messages.
- Updated `Time of Day` coloring to use each thread's start hour so repeated
  messages in the same thread keep a stable color.
- Added NotebookLM metadata connector:
  - `scripts/capture_notebooklm_meta.py` to snapshot NotebookLM context,
    notebooks, and source metadata via `notebooklm --json`
  - `adapters/notebooklm_meta.py` to normalize snapshots into `notes_meta`
    records (`app: notebooklm`, hashed IDs only)
  - `scripts/run_day.sh` arg 20 (`NOTEBOOKLM_META_INPUT`) to ingest NotebookLM
    metadata alongside arg 14 notes metadata into one `logs/notes` stream.
- Added NotebookLM connector documentation in
  `docs/notebooklm_connector.md` and linked it from docs indexes.
- Added lifetime/global dashboard output via
  `scripts/build_dashboard.py --lifetime` producing
  `dashboard_lifetime.json/html` up to `--date`.
- Added lifetime state-volume metrics:
  estimated raw ingested events, junk (`low_signal`) counts, compressed event
  totals, `state.json` byte size, and compression/expansion ratios.
- Added per-thread chat context-usage estimates to daily dashboards:
  chars/tokens estimates, role-bucket token splits, default-context-window
  overflow counts/tokens, and explicit overflow summary cards.
- Added indicative API costing outputs for lifetime dashboards:
  `dashboard_costing.json/html` and `_all` variants with scenario presets and
  explicit non-authoritative caveats.
- Added costing/context methodology docs and references
  (`docs/api_costing_model.md`, updated dashboard docs/README/index) plus TODO
  follow-ups for future provider billing-log calibration.
- Added metadata-only context overlay adapters:
  - `adapters/inaturalist_stub.py` (iNaturalist biodiversity observations)
  - `adapters/mood_self_report_stub.py` (explicit mood self-report)
  - `adapters/pet_wearable_stub.py` (pet wearables / smart collar telemetry stub)
- Updated daily/weekly/lifetime dashboards to surface:
  - daily iNaturalist insect observation count + deterministic trend phase
    (`upward_knee|rising|peak|declining|stable`)
  - daily mood self-report count + latest mood code (self-report only)
- Added docs for these new lanes:
  - `docs/inaturalist_connector.md`
  - `docs/mood_self_report.md`
  - `docs/pet_wearables_stub.md`
- Added maps timeline overlay stub (Google Maps / Apple Maps):
  - `adapters/maps_timeline_stub.py` -> `context_type=location_timeline`
  - `docs/maps_timeline_stub.md`
- Updated `scripts/run_day.sh` to support context overlays:
  - arg 22 `CONTEXT_FIELD_APPEND_INPUT` (append pre-normalized `context_field` JSONL)
  - arg 23 `MEDICATION_TRACKER_INPUT` (normalize medication raw JSONL then append)

## 2026-02-07
- Synced context from ChatGPT conversation `Conductor vs SB/ITIR`
  (`6986c9f5-3988-839d-ad80-9338ea8a04eb`) and recorded the resulting boundary
  decisions in SB docs.
- Added `docs/tool_interop_observer_contract.md` to formalize read-only
  interoperability with orchestration/observability tools.
- Linked the new interop contract from `README.md` and `docs/INDEX.md`.
- Updated `CONTEXT.md` and `COMPACTIFIED_CONTEXT.md` with the 2026-02-07 sync
  note and cloud-as-observer stance.
- Added TODO follow-up items for observer event schema, read-only execution
  provenance ingest, workflow-enforcement rejection tests, and timeline-lens export.

## 2026-02-06
- Expanded red-team plan with path traversal, DoS/resource exhaustion, and
  blast-radius constraints.
- Updated failure modes with explicit blast-radius definition and limits.
- Added optional base-path guard to the CLI query surface.
- Extended ITIR ingest contract and validation with explicit forbidden fields.
- Added red-team tests for query path-escape refusal and overlay state-field
  injection.
- Added OpenClaw integration doc with execution envelope contract and truth-substrate doctrine.
- Documented tool execution envelope ingestion format and references in core docs.
- Added multi-modal system doctrine for epistemic modes and authority boundaries.
- Added lawyer/psychologist user story boundary narratives.
- Extended user stories with additional role stress tests (banker/CEO/manager/etc.).
- Added organization-level user story layer (teams/admins/regulators).
- Added public sector user story layer (police/EMS/health/government guardrails).
- Added modern org stack user story layer (dev/team/CEO/finance).
- Added air-gapped/battlefield/interop user story layer.
- Added "Against Victor's Memory" doctrine to `DESIGN.md`.
- Added panopticon refusal manifesto.
- Added state power/structural violence note to panopticon refusal.
- Added activist coordination user story layer.
- Added trauma/authoritarian pressure user story layer.
- Added access-scope and legal reconstruction user story layer.
- Added judicial-context user story layer (judges/staff/bailiffs/family).
- Added public-figure user story (Zohran Mamdani context collapse).
- Documented observed-signal scope for input activity, system logs, browser
  usage, AV status, cloud audit feeds, and notes metadata.
- Added meta-only adapters and tests for social feeds plus Windows/macOS
  event log stubs.
- Added social platform stubs (Bluesky, Twitter/X, Mastodon, Reddit) and
  red-team guard for content-to-embedding leakage.
- Added social stub collector guide and social redaction rules.

## 2026-02-05
- Added Recall/OpenRecall notes, activity event layer, and sessionization rules to `CONTEXT.md`.
- Removed OpenRecall's hard `python-doctr` git pin to avoid dependency conflicts; keep `python-doctr` optional.
- Locked authority split for activity_events across SB/ITIR/OpenRecall in `CONTEXT.md`.
- Documented Recall-class capture substrate and policy gates in `DESIGN.md`.
- Clarified activity_event ownership and ITIR ingest rules in `DESIGN.md`.
- Added optional Recall-class TODOs for capture, activity events, and timeline UX in `TODO.md`.
- Added sessionizer, ledger, and ITIR ingest adapter TODOs for activity_events in `TODO.md`.
- Drafted ADR 0002 for Recall-class capture + activity events.
- Added authority split to ADR 0002.
- Added snapshot and activity_event schema stubs to `STATE_SCHEMA.json`.
- Added ADR index and referenced it from `README.md`.
- Added sample `snapshots` and `activity_events` to `SAMPLE_STATE.json`.
- Refreshed `COMPACTIFIED_CONTEXT.md` with activity_event ownership and authority split.
- Added sessionization spec in `SESSIONIZATION_SPEC.md`.
- Added deterministic sessionizer stub in `sb/activity/sessionize.py` with fixtures and tests.
- Added `SESSIONIZER_CONFIG.json` and config support in sessionizer.
- Added `Makefile` targets for sessionizer and tests.
- Added config validation for sessionizer settings.
- Added `Justfile` targets for sessionizer and tests.
- Added config validation tests and CLI error handling for sessionizer.
- Added CLI exit-code test fixture for invalid config.
- Documented observability sources (Prometheus/Graphite/Grafana, optional InfluxDB) in `README.md`, `DESIGN.md`, and `COMPACTIFIED_CONTEXT.md`.
- Added observability source notes in `OBSERVED_SIGNALS.md` and `TODO.md`.
- Added rolling window carryover counts to minimal fold outputs and `STATE_SCHEMA.json`.
- Added carryover window counts to `SAMPLE_STATE.json`.
- Included carryover deltas and window counts in generated daily briefs (`scripts/run_day.sh`).
- Added guard tests to ensure folds do not mutate event content or inject summaries.
- Ran multi-day replay outputs for deterministic carryover aging (2026-02-06 to 2026-02-08).
- Added Wazuh lifecycle adapter for structured system events.
- Added HTTP `/metrics` server over baked state outputs.
- Added determinism tests for Wazuh adapter and Prometheus summaries.
- Added OCR/Android/query/ITIR ingest contract docs plus ITIR overlay validation helper.
- Added drift counters output (`runs/<date>/outputs/drift.json`) with `DRIFT_SIGNALS.md`.
- Added Phase-2 compression (collapse of repeated `low_signal=true` events).
- Added read-only query CLI (`scripts/query_state.py`) and query helpers.
- Added bundle export/verify tooling and bundle spec.
- Documented time hygiene policy and failure modes.
- Added red-team boundary tests (re-segmentation rejection).
- Expanded red-team plan with DoS, provenance laundering, temporal confusion, and systemic dependency failure.
- Added red-team tests for RCE payload inertness, metric smuggling shape, env leakage, and bundle tamper detection.
- Added empty-repo handling in git adapter and inactivity run test.
- Added bundle export + verify replay test.
- Added compression expansion test, loss profile doc, and agent containment doc.
- Added Prometheus failure handling + bad-data run tests with missing labels.

## 2026-02-03
- Expanded SB docs with context prosthesis/ADHD framing, SITREP naming, explicit loss profiles, and read-only agent query surface.
- Added core SB/SL/TIRC question split and SB context-prosthesis invariants to docs.
- Clarified SB as a temporal reducer over ITIR/TIRC/SL references in `README.md` and `DESIGN.md`.
- Made normalization/compression TODOs concrete with atom/handle definitions, temporal reduction rules, adapters, and guard tests.
- Documented project intent, inputs/outputs, and anti-enshit principles in `README.md`.
- Added architecture and MVP staging notes in `DESIGN.md`.
- Added initial plan and open questions in `TODO.md`.
- Added compactified project context in `COMPACTIFIED_CONTEXT.md`.
- Added daily brief template in `BRIEF_TEMPLATE.md`.
- Added machine state schema in `STATE_SCHEMA.json` with synthetic sample in `SAMPLE_STATE.json`.
- Added append-only ingestion formats in `INGESTION_FORMATS.md`.
- Consolidated `README.md` into a single authoritative overview.
- Added OCR/screen capture guardrails in `SAFETY_OCR.md` and referenced them in `README.md` and `DESIGN.md`.
- Refreshed `COMPACTIFIED_CONTEXT.md` with epistemic invariants.
- Expanded `TODO.md` with fold, ADR, and safety governance work.
- Added `.planning/phase-0-docs-foundation.md`.
