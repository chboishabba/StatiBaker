# OpenClaw Integration (SB/ITIR Truth Substrate)

## Framing

OpenClaw is a goal-seeking action engine. StatiBaker/ITIR is a time-bounded
truth substrate.

- OpenClaw answers: "What should I do next to achieve X?"
- SB/ITIR answers: "What happened, when, under what authority, and with what loss?"

The goal is not to make SB smarter. The goal is to make agent activity
legible, bounded, and reversible without granting SB/ITIR authority.

## Likely Integration Patterns

### Pattern A: SB as Agent Memory / Journal
- Every agent action becomes an SB `activity_event`.
- Every goal becomes an SB annotation.
- Every failure becomes a drift signal.

SB should expect high-frequency, low-signal events and partial execution
chains. SB should record `agent_id`, `goal_id`, and non-completion as a
first-class state.

### Pattern B: SB as Safety Governor
- OpenClaw proposes a plan.
- SB exposes scope and blast-radius context.
- Humans decide whether to proceed.

SB should distinguish `proposal_event` vs `execution_event`, and log rejection
reasons without rewriting history.

### Pattern C: SB as Retrospective Truth Source
- The agent is unconstrained at runtime.
- Later, humans ask: "Why did this happen?"

SB must separate agent explanations from observed timelines and require
provenance hashes for prompts, plans, and executions. No retroactive edits.

### Pattern D: SB as Multi-Agent Arbiter
- Multiple OpenClaw agents run in parallel.

SB should isolate agent identities, log inter-agent references, and avoid
automatic conflict resolution.

## What SB Must Log (Evidence-Only)

SB should log what regulators or incident responders would later ask for,
without providing agent decision support.

### Execution envelope
- start/end time
- host identity
- toolchain versions
- prompt hash
- declared intent label (human supplied)

### Scope declaration (critical)
Scope is declared, not enforced. This enables later auditing.

```
scope:
  filesystem: read-only
  network: internal-only
  devices: ["x32_mixer"]
  credentials_used: false
```

### Failure and interruption events
- partial execution
- retries
- aborts
- human overrides
- external system errors

## What SB Must Not Do

SB must not:
- infer agent intent
- summarize agent reasoning
- collapse agent chains into one event
- resolve agent conflicts
- optimize agent behavior

ITIR must not:
- auto-generate prompts
- auto-trigger executions
- close the loop on agent behavior

Humans decide. SB and ITIR remain evidentiary.

## Truth Substrate Doctrine

SB/ITIR does not decide what is true. It decides what claims must answer to.

- SB records evidence.
- ITIR surfaces tension between claims and evidence.
- Neither system acts or optimizes.

## Execution Envelope Contract

This is the atomic unit SB should ingest from OpenClaw.

### Required fields

```json
{
  "execution_id": "uuid",
  "tool": "openclaw",
  "started_at": "2026-02-19T03:12:44Z",
  "ended_at": "2026-02-19T03:13:21Z",
  "host": {
    "hostname": "builder-07",
    "os": "linux",
    "arch": "x86_64"
  },
  "toolchain": {
    "openclaw_version": "0.4.2",
    "runtime": "python3.12",
    "container_hash": "sha256:…"
  },
  "prompt": {
    "hash": "sha256:…",
    "length_chars": 1832
  },
  "declared_intent": {
    "label": "deploy hotfix",
    "supplied_by": "human"
  }
}
```

### Prompt hash vs prompt text
Prompt text is optional and should be stored only as content-addressed
artifacts. SB should treat prompt content as Recall-class evidence, not
activity-event content.

## Activity-event subtype (suggested)

```json
{
  "activity_event": {
    "kind": "tool_execution",
    "tool": "openclaw",
    "execution_envelope": { "...": "..." },
    "artifacts": [
      "artifact://prompt-text/sha256:..."
    ]
  }
}
```

SB owns time boundaries and envelope integrity. ITIR owns longitudinal
comparison and tension surfacing. OpenClaw owns behavior and outcomes.

## Integration Questions This Enables

- Which prompt revisions correlate with aborts or retries?
- Does this take longer on a specific host or toolchain?
- Is this drift (persistent change) or a one-off?
- What patterns exist without acting on them?

ITIR answers with pattern evidence only. It does not recommend action.

## Doctrine Sentence

OpenClaw may decide what to do. SB decides what happened. ITIR decides what
questions can be asked.
