# StatiBaker Design Notes

## Purpose
StatiBaker compiles daily state across human and machine signals into a concise,
traceable brief for a single human and multiple agents.

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

## Pipeline
1. Ingestion (append-only)
   - Capture raw logs and inputs without rewriting history.
   - See `INGESTION_FORMATS.md` for canonical log formats.
2. Normalization
   - Convert text to events.
   - Assemble events into threads.
3. Compression (the bake)
   - Remove redundancy.
   - Collapse repeated failures.
   - Preserve causal links.
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
