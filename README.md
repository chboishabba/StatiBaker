# StatiBaker

**Just old-fashioned organisation — with modern failure modes taken seriously.**

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

## Inputs (state surface)

If it produces state, it can be baked.

### Human streams

- Journal entries
- TODOs / task ledgers (e.g., Vikunja)
- Notes and drafts
- Calendar events
- Questions-in-progress
- Sleep, activity, and capacity signals

### System and agent streams

- Agent logs and run states
- Tool outputs
- Git commits, diffs, CI results
- Automation outcomes

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

### Retrospective summary (evening)

A fold over the day that:

- preserves gaps
- marks uncertainty
- records collapse without judgement

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
- `DESIGN.md` (architecture notes and invariants)
- `CONTEXT.md` (context-layering and divergence notes)
- `COMPACTIFIED_CONTEXT.md` (portable project summary)
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

StatiBaker never interprets content.
ITIR never manages lived context.
They integrate via **context envelopes**, not shared logic.

SB ingests **references only** (IDs/URIs) from TIRC/SL/ITIR and compiles
temporal deltas (carryover/new/resolved). It does not read or summarize
artifact content.
Agentic systems should query SB via a read-only interface (e.g., MCP) before
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

**Docs-only foundation.**
No implementation yet — deliberately.

The goal at this stage is to:

- lock invariants
- prevent architectural drift
- make future enshittification structurally difficult

---

## The point, stated plainly

> **StatiBaker is not here to make life easier.
> It is here to make reality harder to lose.**
