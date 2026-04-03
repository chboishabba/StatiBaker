# StatiBaker

StatiBaker is a daily state compiler.

It is built to reconstruct what actually happened across tools, logs, and
activity traces without pretending to be an assistant, planner, or life coach.

In plain language:

- it compiles state
- it preserves gaps and contradictions
- it produces traceable summaries and machine-readable outputs
- it helps recover continuity after interruption or context collapse

## What StatiBaker Does

StatiBaker ingests append-only signals and emits bounded state views such as:

- what changed
- what carried over
- what is unresolved
- what actions or machine states are pending

It treats those outputs as read-only reconstruction, not as a replacement for
the source systems that generated them.

## What You Can Do With It Today

### 1. Compile a daily state view from real traces

Current inputs can include:

- git and filesystem activity
- process and system metadata
- browser/app usage metadata
- notes/task metadata
- machine and agent logs

Current outputs include:

- human-readable daily brief material
- machine-readable state artifacts
- suite-normalized compiled-state artifact wrappers for portable handoff
- drift counters
- dashboard/database artifacts
- portable bundles for later inspection
- bounded external reviewed-state overlays such as Corkysoft planner /
  reconciliation review events

### 2. Preserve reality instead of smoothing it away

StatiBaker is designed so that:

- append-only history stays append-only
- contradictions remain visible
- compression is explicit rather than hidden
- replay remains deterministic

That is the practical difference between "state compiler" and "assistant."

### 3. Provide a read-only state surface for other tools

StatiBaker sits beside the rest of the suite as a context/state layer.

That means it can feed later review or orchestration without claiming semantic
or legal authority over the underlying content.

## Proven Abilities

The current repo already contains:

- a run pipeline that collects inputs and writes per-day outputs
- dashboard builders that persist canonical state to SQLite
- read-only query surfaces over compiled artifacts
- portable export/verify bundle paths
- explicit drift counters and failure-mode docs

What that means in practice:

- the project already has real append-only state compilation paths
- it already produces inspectable outputs, not just design notes
- the repo is opinionated about boundaries: no silent rewriting, no fake
  certainty, no hidden "AI knows best" layer

## Quick Start

StatiBaker is usually worked on inside the top-level `ITIR-suite` workspace.

From the repo root:

```bash
./env_init.sh
source .venv/bin/activate
```

Then use the current project scripts from the `StatiBaker` directory.

Common entry points:

```bash
cd StatiBaker
python scripts/build_dashboard.py --help
python scripts/serve_metrics.py --help
python scripts/bundle_export.py --help
python scripts/verify_bundle.py --help
```

If you want the canonical dashboard/state path, start by reading:

- [docs/activity_dashboard.md](docs/activity_dashboard.md)
- [QUERY_SURFACE.md](QUERY_SURFACE.md)
- [BUNDLE_SPEC.md](BUNDLE_SPEC.md)

## Common Workflows

### Daily bake / state compilation

Use the run pipeline when you want to collect inputs into a per-day run
directory and produce compiled state outputs.

Relevant surface:

- `scripts/run_day.sh`

### Dashboard and state inspection

Use the dashboard builders when you want a human-readable lens over compiled
state while still keeping SQLite as the canonical backing store.

Relevant surfaces:

- `scripts/build_dashboard.py`
- `sb/dashboard.py`
- [docs/activity_dashboard.md](docs/activity_dashboard.md)
- `scripts/corkysoft_consume.py`

### Portable bundle export and verification

Use bundle export when you want to preserve a snapshot with traceability.

Relevant surfaces:

- `scripts/bundle_export.py`
- `scripts/verify_bundle.py`
- [BUNDLE_SPEC.md](BUNDLE_SPEC.md)

Bundle exports now also emit `suite_normalized_artifact.json` as the
suite-level normalized wrapper for the compiled `state.json` surface. That
keeps `StatiBaker` in its own lane: it still owns compiled state, but it can
now hand that state to root-suite consumers without inventing a second
reducer in another repo.

## Core Rules

These are the project’s important non-negotiables.

- no agency: StatiBaker does not initiate actions or messages
- append-only reality: history is preserved rather than rewritten
- explicit compression: summaries should declare loss rather than hide it
- deterministic replay: the same event log should yield the same bake

## Relationship To The Rest Of The Suite

StatiBaker handles time and state.

It sits beside:

- `tircorder-JOBBIE`, which handles capture
- `SensibLaw`, which handles deterministic normative/provenance review
- broader ITIR orchestration surfaces, which coordinate work across projects

Boundary summary:

- StatiBaker may preserve upstream identifiers and artifacts
- it does not take over semantic or legal interpretation
- it is a read-only state layer, not the source of truth for external systems
- Corkysoft remains authoritative for removals workflow state even when SB
  stores reviewed Corkysoft overlays or reads Corkysoft MCP summaries

## Where To Find Things

### Start here

- collectors/adapters index:
  [docs/collectors_index.md](docs/collectors_index.md)
- observed signals:
  [docs/observed_signals.md](docs/observed_signals.md)
- activity dashboard:
  [docs/activity_dashboard.md](docs/activity_dashboard.md)
- query surface:
  [QUERY_SURFACE.md](QUERY_SURFACE.md)

### Boundaries and invariants

- agent containment:
  [AGENT_CONTAINMENT.md](AGENT_CONTAINMENT.md)
- failure modes:
  [FAILURE_MODES.md](FAILURE_MODES.md)
- drift counters:
  [DRIFT_SIGNALS.md](DRIFT_SIGNALS.md)
- time hygiene:
  [TIME_HYGIENE.md](TIME_HYGIENE.md)

### Export and bundle docs

- bundle format:
  [BUNDLE_SPEC.md](BUNDLE_SPEC.md)
- loss profiles:
  [LOSS_PROFILES.md](LOSS_PROFILES.md)
- ITIR ingest boundary:
  [ITIR_INGEST_CONTRACT.md](ITIR_INGEST_CONTRACT.md)

## What StatiBaker Is Not

StatiBaker is not:

- a chatbot
- a planner
- a motivation tool
- a system that silently rewrites reality into a cleaner story

Its job is narrower and more defensible:

to make state harder to lose.
