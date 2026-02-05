# Changelog

## 2026-02-05
- Added Recall/OpenRecall notes, activity event layer, and sessionization rules to `CONTEXT.md`.
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
