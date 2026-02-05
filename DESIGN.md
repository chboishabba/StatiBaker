# StatiBaker Design Notes

## Purpose
StatiBaker compiles daily state across human and machine signals into a concise,
traceable brief for a single human and multiple agents.
It acts as an observability-style reducer for lived time, not an assistant.

## Conceptual model
- Events: timestamped, atomic facts or actions
- Threads: related events grouped by topic or goal
- Trajectories: thread histories over time

## Epistemic layers and promotion
- Declared state is authoritative (tasks, notes, logs, commits).
- Observed state is evidentiary (screens, sensors).
- Derived artifacts are provisional (OCR, transcripts).
- Derived artifacts never become state without explicit promotion.
- Screen capture and OCR guardrails live in `SAFETY_OCR.md`.

## Recall-class observed capture (optional substrate)
If SB adopts a Recall/OpenRecall-style substrate, it remains **observed evidence**
with strict policy gates:
- Wayland-first capture (PipeWire + portal), X11 fallback only by explicit flag.
- No silent OCR; extraction is policy-gated and redaction-first.
- Append-only snapshots; derived signals are recomputable.
- Add an **activity_event** layer to segment snapshots into deterministic timeline
  units ("then this → then this"), without contaminating raw evidence.

## Observed signal streams
SB can ingest additional **observed signals** (input activity, system events,
CLI activity, metric summaries) as append-only JSONL. These streams are
structural only and never include content. See `OBSERVED_SIGNALS.md`.

SB consumes curated facts, never raw logs.

## Observability sources (current)
- Prometheus (TrueNAS scrape, includes Graphite exporter metrics) is the primary
  numeric source for SB metric summaries.
- Grafana is a visualization lens only (dashboard scoped to activity windows).
- InfluxDB (Home Assistant) may be added when credentials and live data are
  confirmed; SB should consume curated summaries, not raw series.

## Pipeline
1. Ingestion (append-only)
   - Capture raw logs and inputs without rewriting history.
   - See `INGESTION_FORMATS.md` for canonical log formats.
2. Normalization
   - Convert text to events.
   - Assemble events into threads.
3. Compression (the bake)
   - Temporal reduction over canonical artifacts (no re-tokenization).
   - Carryover/new/resolved sets for atoms, threads, and constraints.
   - Collapse repeated failures without rewriting provenance.
4. Emission
   - Human brief (language)
   - Agent brief (JSON) -> `STATE_SCHEMA.json`
   - Optional task/knowledge graph

## Daily outputs
A. Morning brief (human)
- Context snapshot
- Top priorities
- Open questions
- Agent actions queued
- Template: `BRIEF_TEMPLATE.md`

B. Machine state (agents)
- Day state, energy, blockers, carryover threads
- Agent permissions for autonomous runs
- Schema: `STATE_SCHEMA.json`

C. Evening retrospective
- Completed, partial, missed tasks
- Drift signals and constraints
- Template: `BRIEF_TEMPLATE.md`

## Differentiators
- Structured state over chat snippets
- Temporal accountability over reactive replies
- Canonical logs over ephemeral conversation

## Core questions (suite split)
- SB: Where am I and what happened? (lived time, state reconstruction)
- SL: What does this mean? (normative reasoning)
- TIRC: How else can this be interpreted? (contested narratives)

## Context prosthesis (SB-only invariants)
- No agency: SB never initiates actions or messages.
- Append-only reality: gaps and contradictions remain first-class.
- Explicit compression: folds declare loss profiles and remain expandable.
- Deterministic replay: the same event log yields the same bake.

## ITIR/TIRC/SL integration contract
- SB is the time-axis: it compiles daily state deltas from append-only events.
- SB owns activity_events (deterministic segmentation of observed snapshots).
- Inputs are references, not content:
  - TIRC: activity signals and trajectory IDs.
  - SL: constraints and rule IDs.
  - ITIR: overlays and annotation IDs.
- ITIR ingests activity_events and never re-segments time.
- SB never re-canonicalizes text, promotes phrases, or interprets meaning.
- SB stores refs (IDs/URIs) and emits temporal deltas only.

## MVP staging (proposed)
Week 1
- Markdown journal + TODO + agent logs
- One daily summary
- One nightly retrospective

Week 2
- Calendar + git integration
- Agent task queue
- Carryover threads

Week 3
- Smart home hooks
- Energy/alert annotations
- Drift detection

## Anti-enshit safeguards
- Prioritize user utility, not engagement
- Provide data export and portability
- Avoid platform lock-in by design
