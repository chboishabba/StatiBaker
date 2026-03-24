# StatiBaker
## Just old-fashioned organisation — with modern failure modes taken seriously.
**LLMs are like ogres; they like onions**

We don’t tell you what to do, who to be, or how to optimise.
We don’t infer preferences, goals, or intent.
We don’t act on your behalf.

**We help you remember what actually happened — so you can decide.**

StatiBaker is a **daily state distillation engine**.
It compiles human and machine state into a single, coherent brief with traceability
back to raw logs and actions.

StatiBaker is also a **context prosthesis** for ADHD support: a digital corkboard
that reassembles itself after context collapse so you can recover what happened,
what stalled, and what is still active.

This is **not** a chatbot.
It is **not** a planner.
It is **not** an assistant.

**It is a state compiler.**

---

## Core idea

StatiBaker ingests everything you generate or operate, then emits structured state views:

- **What happened**: observed events, ordered, with gaps preserved
- **What matters today**: active intersections, not priorities
- **What is unresolved**: open loops, blockers, carryovers
- **What agents should do next**: pending or blocked machine actions (not recommendations)

No judgement.
No optimisation.
No motivational framing.

---
<img width="926" height="1280" alt="image" src="https://github.com/user-attachments/assets/2e76f49d-4bf1-4cde-bfbd-fbe66919cf04" />
<img width="1287" height="946" alt="image" src="https://github.com/user-attachments/assets/94086272-c641-459d-afbb-7a9ff469b421" />
<img width="1310" height="843" alt="image" src="https://github.com/user-attachments/assets/f6879eef-aa7c-4a93-827f-4c25a7b72cc7" />
<img width="1002" height="807" alt="image" src="https://github.com/user-attachments/assets/acf88ca8-4d62-45b0-87a4-154b5057e7c0" />

## Current module features (what exists today)

### Monorepo Python imports
- From the ITIR-suite repo root, `import sb` and `python -m sb...` are supported via the lightweight shim package at `sb/__init__.py`.
- This avoids requiring installation/packaging just to run modules locally.

- **Run pipeline (append-only logs -> compiled state)**
  - A reference run script that collects inputs into a per-day run dir and writes outputs: `scripts/run_day.sh`
  - Pluggable adapters for common streams (git, filesystem meta, Prometheus, osquery, input/window focus, browser usage, notes meta, social/meta stubs, etc.): `adapters/`
- **Daily bake outputs**
  - Machine-readable state and supporting artifacts (runs under `runs_local/<YYYY-MM-DD>/outputs/` by default): `sb/`
  - Drift counters written as observational JSON: `sb/drift.py` (see `DRIFT_SIGNALS.md`)
- **Dashboards + web surfaces (current HTML, future Svelte)**
  - Dashboard builder that persists **canonically to SQLite** for daily/weekly/lifetime views: `scripts/build_dashboard.py`, `sb/dashboard.py`
    - Legacy JSON/HTML exports remain available for regression/debug, but are not the canonical store.
    - Default private runs root is `runs_local/` via `SB_RUNS_ROOT`; do not
      treat `runs/dashboard.sqlite` as a checked-in personal-data sample.
  - HTML renderer functions (embedded CSS + client-side JS for filtering/palette controls):
    `sb/dashboard.py` (`render_dashboard_html`, `render_weekly_dashboard_html`, `render_lifetime_dashboard_html`)
  - Web iteration map (UI contracts + safe edit zones): `docs/web_module_map.md`
  - Documented migration target for decomposing the monolithic renderer (SvelteKit + Tailwind): `docs/svelte_migration_sprint.md`
  - Minimal metrics HTTP server (`/metrics`, Prometheus text format): `sb/metrics_server.py`, `scripts/serve_metrics.py`
- **Portable bundles**
  - Bundle spec + build/verify scripts for sharing state snapshots with traceability: `BUNDLE_SPEC.md`, `sb/bundle.py`, `scripts/bundle_export.py`, `scripts/verify_bundle.py`
- **Query surface**
  - Read-only query module over compiled artifacts/state: `sb/query.py` (see `QUERY_SURFACE.md`)

---

## Inputs (state surface)

If it produces state, it can be baked.

### Human streams

- Journal entries
- TODOs / task ledgers (e.g., Vikunja)
- External commitments / task systems (e.g., Google Tasks)
- Notes and drafts
- Calendar events
- Questions-in-progress
- Sleep, activity, and capacity signals

### System and agent streams

- Agent logs and run states
- Tool outputs
- Git commits, diffs, CI results
- Automation outcomes
- Input activity (keyboard/mouse counts, focus/app metadata)
- System event logs (journald / Windows Event Log / macOS Unified Log)
- Antivirus/endpoint status summaries
- Browser usage metadata (domain-level, duration only)
- Cloud audit feeds (Google Drive, MS365)
- Notes app metadata (Obsidian, Evernote)
- Voice-capture list metadata (e.g., Google Keep list items / Google Home-originated
  "add to my to do list" flows)
- NotebookLM lifecycle metadata (context/notebook/source/artifact) with
  optional display snippets for local UX
- Media consumption metadata (YouTube/Spotify/VLC/Last.fm)
- Social feed metadata (Bluesky and other socials; hashes only)

### Environment and constraints

- Smart home status and alerts (e.g., HAOS)
- Deadlines and time locks
- External dependencies
- Environmental conditions affecting capacity

**All inputs are append-only.**
Nothing is rewritten. Nothing is inferred.

---

## Outputs (the daily bake)

### Human-readable daily brief (SITREP / morning)

A compact reconstruction of state:

- what changed
- what carried over
- what is blocked
- where attention last went

Every line can be traced back to raw events.

### Machine-readable state (JSON)

A strict, schema’d representation of:

- active items
- unresolved loops
- blockers
- eligible actions

This is what agents and automation query.
It is **read-only** and **non-authoritative**.

External commitments remain authoritative in their source systems. SB may
project them, correlate them with evidence, and emit completion candidates, but
it does not become the task board of record.

### Retrospective summary (evening)

A fold over the day that:

- preserves gaps
- marks uncertainty
- records collapse without judgement

### Drift counters (read-only)

Written to `<runs-root>/<date>/outputs/drift.json` as observational counters only. Default runs root is `runs_local/` (override with `SB_RUNS_ROOT`).
See `DRIFT_SIGNALS.md`.

---

## Epistemic rules (non-negotiable)

- **Declared state is authoritative** (tasks, notes, logs, commits).
- **Observed state is evidentiary** (screens, sensors, passive signals).
- **Derived artifacts are provisional** (OCR, transcripts, transforms).
- **Derived artifacts never become state without an explicit act.**

For OCR and screen capture guardrails, see `SAFETY_OCR.md`.

---

## Key artifacts

- `BRIEF_TEMPLATE.md` (human brief and retrospective format)
- `STATE_SCHEMA.json` (machine-readable state contract)
- `SAMPLE_STATE.json` (synthetic example)
- `INGESTION_FORMATS.md` (append-only event formats)
- `docs/social_audit_redaction.md` (social feed redaction rules)
- `docs/social_stub_collectors.md` (per-platform stub inputs)
- `docs/notebooklm_connector.md` (NotebookLM connector setup + ingest flow)
- `docs/google_commitment_connectors.md` (Google Tasks + Google Keep/list commitment connectors)
- `docs/daemon_web_control_plane.md` (cross-platform daemon + web-managed control plane spec)
- `docs/media_connectors.md` (media connector mappings + churn heuristic)
- `docs/inaturalist_connector.md` (iNaturalist meta-only biodiversity connector + trend phases)
- `docs/mood_self_report.md` (explicit mood self-report lane; non-inferential)
- `docs/pet_wearables_stub.md` (pet wearables/smart collar meta-only stub)
- `docs/maps_timeline_stub.md` (Google/Apple maps timeline meta-only stub)
- `docs/collectors_index.md` (collector/adapters index)
- `docs/INDEX.md` (doc index)
- `docs/observed_signals.md` (meta-only signal catalog)
- `docs/activity_dashboard.md` (read-only process-lens dashboard contract)
- `docs/api_costing_model.md` (context usage + indicative API costing model)
- `docs/chat_flow_lane_mode.md` (planned true lane chart mode for chat flow)
- `DESIGN.md` (architecture notes and invariants)
- `CONTEXT.md` (context-layering and divergence notes)
- `COMPACTIFIED_CONTEXT.md` (portable project summary)
- `OCR_ADAPTER_CONTRACT.md` (design-only OCR boundary)
- `ANDROID_STATUS_CONTRACT.md` (design-only mobile status boundary)
- `QUERY_SURFACE.md` (read-only query surface spec)
- `ITIR_INGEST_CONTRACT.md` (read-only ITIR ingest boundary)
- `DRIFT_SIGNALS.md` (read-only drift counters)
- `FAILURE_MODES.md` (boundary lock + red-team catalog)
- `TIME_HYGIENE.md` (time-decay policy)
- `BUNDLE_SPEC.md` (portable bundle layout)
- `LOSS_PROFILES.md` (explicit compression loss profiles)
- `AGENT_CONTAINMENT.md` (read-only agent boundaries)
- `docs/multimodal_system_doctrine.md` (multi-modal doctrine and epistemic modes)
- `docs/openclaw_integration.md` (agent execution envelope + truth substrate)
- `docs/tool_interop_observer_contract.md` (read-only interop with orchestration tools)
- `docs/user_stories.md` (lawyer/psychologist boundary test narratives)
- `docs/panopticon_refusal.md` (refusal of coercive memory / surveillance defaults)
- `docs/red_team.md` (red-team scenarios and considerations)
- `TODO.md` (plan and open questions)
- `ADRs/README.md` (architecture decision record index)

---

## Design principles (anti-enshittification)

These are **enforced constraints**, not aspirations.
They reflect the failure modes documented in `ITIR - anti-enshit.pdf`.

1. **User utility over extractive optimisation**
2. **Transparent, traceable compression**
3. **Append-only state, no memory rewriting**
4. **Verification remains human and local**
5. **Exit is cheap**

---

## Non-goals

StatiBaker explicitly does **not** aim to be:

- A generic conversational assistant
- A planner or task optimiser
- A goal-setting or motivation tool
- An AI that “knows you”
- A system that rewrites history into cleaner stories

If you want advice or recommendations, those belong in **separate, optional layers**.

---

## Relationship to ITIR

- **StatiBaker** handles time and state
- **ITIR** handles meaning and interpretation
- **TIRC** handles disagreement and plural readings
- **SL** handles normative structure and constraints

Boundary clarification:
- StatiBaker is a personal state compiler feeding TiRC/ITIR and adjacent suite
  surfaces.
- SB may use or extend SL-owned lexer/compression outputs where shared
  canonical text handling is needed.
- That reuse does not transfer semantic or legal authority into SB.
- Legal-looking canonical IDs or fixtures reaching SB are opaque upstream
  payloads to preserve, not content for SB to interpret.

StatiBaker never interprets content.
ITIR never manages lived context.
They integrate via **context envelopes**, not shared logic.

SB ingests **references only** (IDs/URIs) from TIRC/SL/ITIR and compiles
temporal deltas (carryover/new/resolved). It does not read or summarize
artifact content.
Agentic systems should query SB via a read-only interface (CLI for now) before
acting.

## Observability sources
- Prometheus is the primary numeric source (includes Graphite exporter metrics).
- Grafana is a UI lens, not a data source.
- InfluxDB (Home Assistant) is optional and only via curated summaries.

## Core differentiation (questions)
- **StatiBaker:** Where am I and what happened? (lived time, state reconstruction)
- **SensibLaw:** What does this mean? (normative reasoning)
- **TIRC:** How else can this be interpreted? (contested narratives, evidentiary integrity)

## SB-only invariants (context prosthesis)
- No agency: SB never initiates actions, messages, or nudges.
- Append-only reality: gaps and contradictions are preserved as first-class objects.
- Explicit compression: summaries declare loss profiles and remain expandable.
- Deterministic replay: the same event log yields the same bake.

---

## Current status

**Implementation exists, but remains pre-1.0 and contract-first.**
Core pipeline pieces (ingest/adapters, bake outputs, dashboards, bundles, and tests) are present, but interfaces and payload contracts are still being hardened and should be treated as unstable until explicitly frozen in docs/ADRs.

The goal at this stage is to:

- lock invariants
- prevent architectural drift
- make future enshittification structurally difficult

---

## The point, stated plainly

> **StatiBaker is not here to make life easier.
> It is here to make reality harder to lose.**
