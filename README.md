# StatiBaker




Just old fashioned organisation.



We don’t tell you what to do, who to be, or how to optimise.



We help you remember what actually happened — so you can decide.


StatiBaker is a daily state distillation engine. It compiles human and machine state
into a single, coherent brief with traceability back to raw logs and actions.
This is not a chatbot. It is a state compiler.

## Core idea
StatiBaker ingests everything you generate or operate, then emits:
- What happened
- What matters today
- What is unresolved
- What agents should do next


What makes this not “just organisation” (important)

Traditional organisation tools assume:

attention is continuous
memory is reliable
context is cheap to reconstruct
verification is optional


StatiBaker assumes the opposite:
context collapses
days disappear
systems keep running anyway
summaries can lie if unchecked

StatiBaker exists to reconstruct state after failure, not to prevent failure.


Core idea

StatiBaker ingests everything you generate or operate, then emits structured state views:

What happened
(observed events, ordered, with gaps preserved)

What matters today
(active state intersections, not priorities)

What is unresolved
(open loops, blockers, carryovers)

What agents should do next
(pending or blocked machine actions — not recommendations)

No judgement.
No optimisation.
No motivational framing.



## Inputs (state surface)
If it produces state, it can be baked.
- Human streams: journal, TODOs, notes, calendar, questions, sleep and activity
- System and agent streams: agent logs, tool outputs, git commits and diffs
- Environment: smart home status, alerts, deadlines, constraints

## Outputs (daily bake)
- Human-readable daily brief (morning)
- Machine-readable state for agents (JSON)
- Retrospective summary (evening)

## Key artifacts
- `BRIEF_TEMPLATE.md` (human brief and retrospective)
- `STATE_SCHEMA.json` (machine-readable state)
- `SAMPLE_STATE.json` (synthetic example)
- `INGESTION_FORMATS.md` (append-only log formats)
- `DESIGN.md` (architecture notes)
- `TODO.md` (plan and open questions)

## Design principles (anti-enshit)
These principles reflect the enshittification research notes in
`ITIR - anti-enshit.pdf`.
- User utility over extractive optimization
- Transparent, traceable state and summaries
- Data portability and interoperability
- Append-only logs, no memory rewriting

## Non-goals
- A generic conversational assistant
- Opaque personalization driven by engagement
- Rewriting history rather than summarizing it

## Current status
Docs-only foundation based on the proposal PDFs. No implementation yet.



Take two:

Got it. What you want here is **one coherent, authoritative document**, not two voices stapled together. Below is a **properly merged version** that:

* keeps the **clarity and spine** of the tightened version
* preserves the **plainness and restraint** of the original
* removes duplication
* sharpens accountability / verification / expansion without bloating
* reads like something that could live as a repo root `README.md` or `DESIGN.md`

No commentary, no “marked changes” — just the combined result.

---

# StatiBaker

**Just old-fashioned organisation — with modern failure modes taken seriously.**

We don’t tell you what to do, who to be, or how to optimise.
We don’t infer preferences, goals, or intent.
We don’t act on your behalf.

**We help you remember what actually happened — so you can decide.**

StatiBaker is a **daily state distillation engine**.
It compiles human and machine state into a single, coherent brief **with traceability back to raw logs and actions**.

This is **not** a chatbot.
It is **not** a planner.
It is **not** an assistant.

**It is a state compiler.**

---

## What makes this *not* “just organisation”

Traditional organisation tools assume:

* attention is continuous
* memory is reliable
* context is cheap to reconstruct
* verification is optional

StatiBaker assumes the opposite:

* context collapses
* days disappear
* systems keep running anyway
* summaries can lie if unchecked

StatiBaker exists to **reconstruct state after failure**, not to prevent failure.

That distinction is everything.

---

## Core idea

StatiBaker ingests everything you generate or operate, then emits **structured state views**:

* **What happened**
  Observed events, ordered, with gaps preserved.

* **What matters today**
  Active state intersections, not priorities.

* **What is unresolved**
  Open loops, blockers, carryovers.

* **What agents should do next**
  Pending or blocked machine actions — **not recommendations**.

No judgement.
No optimisation.
No motivational framing.

---

## Inputs (state surface)

If it produces state, it can be baked.

### Human streams

* Journal entries
* TODOs / task ledgers (e.g. Vikunja)
* Notes (Markdown, Obsidian, etc.)
* Calendar events
* Questions-in-progress
* Sleep, activity, and capacity signals

### System and agent streams

* Agent logs and run states
* Tool outputs
* Git commits, diffs, CI results
* Automation outcomes

### Environment and constraints

* Smart home status and alerts
* Deadlines and time locks
* External dependencies
* Environmental conditions affecting capacity

**All inputs are append-only.**
Nothing is rewritten. Nothing is inferred.

---

## Outputs (the daily bake)

### Human-readable daily brief (morning)

A compact, legible reconstruction of state:

* what changed
* what carried over
* what is blocked
* where attention last went

Every line can be traced back to raw events.

---

### Machine-readable state (JSON)

A strict, schema’d representation of:

* active items
* unresolved loops
* blockers
* eligible actions

This is what agents and automation query.
It is **read-only** and **non-authoritative**.

---

### Retrospective summary (evening)

A fold over the day that:

* preserves gaps
* marks uncertainty
* records collapse without judgement

No “wins”.
No “progress scores”.

---

## Key artifacts

* **BRIEF_TEMPLATE.md**
  Human-facing brief and retrospective format
  (with explicit loss and provenance sections)

* **STATE_SCHEMA.json**
  Machine-readable state contract
  (blockers, carryovers, eligibility, references)

* **SAMPLE_STATE.json**
  Synthetic example with annotations

* **INGESTION_FORMATS.md**
  Append-only event formats and adapters

* **FOLDS.md**
  Fold definitions, loss profiles, expansion rules

* **DESIGN.md**
  Architecture notes, invariants, and constraints

* **ADR/**
  Design decisions (especially around compression and folding)

* **TODO.md**
  Open questions and unresolved design trade-offs

---

## Design principles (anti-enshittification)

These are **enforced constraints**, not aspirations.
They reflect the failure modes documented in *ITIR – anti-enshit.pdf*.

### 1. User utility over extractive optimisation

* No engagement loops
* No behavioural telemetry
* No nudging

---

### 2. Transparent, traceable compression

Every summary:

* declares its loss profile
* references raw events
* can be expanded deterministically

**It must always be cheaper to expand than to summarise again.**

---

### 3. Append-only state, no memory rewriting

* History is never overwritten
* Corrections are additive
* Disagreement is preserved

---

### 4. Verification remains human and local

* The system never claims correctness
* It exposes what would need to be checked

---

### 5. Exit is cheap

* All state is exportable
* All schemas are documented
* Nothing requires a cloud service to remain intelligible

---

## Non-goals

StatiBaker explicitly does **not** aim to be:

* A generic conversational assistant
* A planner or task optimiser
* A goal-setting or motivation tool
* An AI that “knows you”
* A system that rewrites history into cleaner stories

If you want advice, recommendations, or optimisation,
those belong in **separate, optional layers** — not here.

---

## Relationship to ITIR

* **StatiBaker** handles *time and state*
* **ITIR** handles *meaning and interpretation*
* **TIRC** handles *disagreement and plural readings*

StatiBaker never interprets content.
ITIR never manages lived context.

They integrate via **context envelopes**, not shared logic.

---

## Current status

**Docs-only foundation.**
No implementation yet — deliberately.

The goal at this stage is to:

* lock invariants
* prevent architectural drift
* make future enshittification **structurally difficult**

---

## The point, stated plainly

> **StatiBaker is not here to make life easier.
> It is here to make reality harder to lose.**

That’s the through-line.
Everything else exists to defend it.

If you want next steps, the natural ones are:

* a README-length compression of this,
* a one-page “Why this exists” explainer,
* or a hostile-read test (“how could this be misused or diluted?”).


Take three:

Got it. What you want here is **one coherent, authoritative document**, not two voices stapled together. Below is a **properly merged version** that:

* keeps the **clarity and spine** of the tightened version
* preserves the **plainness and restraint** of the original
* removes duplication
* sharpens accountability / verification / expansion without bloating
* reads like something that could live as a repo root `README.md` or `DESIGN.md`

No commentary, no “marked changes” — just the combined result.

---

# StatiBaker

**Just old-fashioned organisation — with modern failure modes taken seriously.**

We don’t tell you what to do, who to be, or how to optimise.
We don’t infer preferences, goals, or intent.
We don’t act on your behalf.

**We help you remember what actually happened — so you can decide.**

StatiBaker is a **daily state distillation engine**.
It compiles human and machine state into a single, coherent brief **with traceability back to raw logs and actions**.

This is **not** a chatbot.
It is **not** a planner.
It is **not** an assistant.

**It is a state compiler.**

---

## What makes this *not* “just organisation”

Traditional organisation tools assume:

* attention is continuous
* memory is reliable
* context is cheap to reconstruct
* verification is optional

StatiBaker assumes the opposite:

* context collapses
* days disappear
* systems keep running anyway
* summaries can lie if unchecked

StatiBaker exists to **reconstruct state after failure**, not to prevent failure.

That distinction is everything.

---

## Core idea

StatiBaker ingests everything you generate or operate, then emits **structured state views**:

* **What happened**
  Observed events, ordered, with gaps preserved.

* **What matters today**
  Active state intersections, not priorities.

* **What is unresolved**
  Open loops, blockers, carryovers.

* **What agents should do next**
  Pending or blocked machine actions — **not recommendations**.

No judgement.
No optimisation.
No motivational framing.

---

## Inputs (state surface)

If it produces state, it can be baked.

### Human streams

* Journal entries
* TODOs / task ledgers (e.g. Vikunja)
* Notes (Markdown, Obsidian, etc.)
* Calendar events
* Questions-in-progress
* Sleep, activity, and capacity signals

### System and agent streams

* Agent logs and run states
* Tool outputs
* Git commits, diffs, CI results
* Automation outcomes

### Environment and constraints

* Smart home status and alerts
* Deadlines and time locks
* External dependencies
* Environmental conditions affecting capacity

**All inputs are append-only.**
Nothing is rewritten. Nothing is inferred.

---

## Outputs (the daily bake)

### Human-readable daily brief (morning)

A compact, legible reconstruction of state:

* what changed
* what carried over
* what is blocked
* where attention last went

Every line can be traced back to raw events.

---

### Machine-readable state (JSON)

A strict, schema’d representation of:

* active items
* unresolved loops
* blockers
* eligible actions

This is what agents and automation query.
It is **read-only** and **non-authoritative**.

---

### Retrospective summary (evening)

A fold over the day that:

* preserves gaps
* marks uncertainty
* records collapse without judgement

No “wins”.
No “progress scores”.

---

## Key artifacts

* **BRIEF_TEMPLATE.md**
  Human-facing brief and retrospective format
  (with explicit loss and provenance sections)

* **STATE_SCHEMA.json**
  Machine-readable state contract
  (blockers, carryovers, eligibility, references)

* **SAMPLE_STATE.json**
  Synthetic example with annotations

* **INGESTION_FORMATS.md**
  Append-only event formats and adapters

* **FOLDS.md**
  Fold definitions, loss profiles, expansion rules

* **DESIGN.md**
  Architecture notes, invariants, and constraints

* **ADR/**
  Design decisions (especially around compression and folding)

* **TODO.md**
  Open questions and unresolved design trade-offs

---

## Design principles (anti-enshittification)

These are **enforced constraints**, not aspirations.
They reflect the failure modes documented in *ITIR – anti-enshit.pdf*.

### 1. User utility over extractive optimisation

* No engagement loops
* No behavioural telemetry
* No nudging

---

### 2. Transparent, traceable compression

Every summary:

* declares its loss profile
* references raw events
* can be expanded deterministically

**It must always be cheaper to expand than to summarise again.**

---

### 3. Append-only state, no memory rewriting

* History is never overwritten
* Corrections are additive
* Disagreement is preserved

---

### 4. Verification remains human and local

* The system never claims correctness
* It exposes what would need to be checked

---

### 5. Exit is cheap

* All state is exportable
* All schemas are documented
* Nothing requires a cloud service to remain intelligible

---

## Non-goals

StatiBaker explicitly does **not** aim to be:

* A generic conversational assistant
* A planner or task optimiser
* A goal-setting or motivation tool
* An AI that “knows you”
* A system that rewrites history into cleaner stories

If you want advice, recommendations, or optimisation,
those belong in **separate, optional layers** — not here.

---

## Relationship to ITIR

* **StatiBaker** handles *time and state*
* **ITIR** handles *meaning and interpretation*
* **TIRC** handles *disagreement and plural readings*

StatiBaker never interprets content.
ITIR never manages lived context.

They integrate via **context envelopes**, not shared logic.

---

## Current status

**Docs-only foundation.**
No implementation yet — deliberately.

The goal at this stage is to:

* lock invariants
* prevent architectural drift
* make future enshittification **structurally difficult**

---

## The point, stated plainly

> **StatiBaker is not here to make life easier.
> It is here to make reality harder to lose.**

That’s the through-line.
Everything else exists to defend it.

If you want next steps, the natural ones are:

* a README-length compression of this,
* a one-page “Why this exists” explainer,
* or a hostile-read test (“how could this be misused or diluted?”).


Take four:

Ah — *Copilot Recall specifically* makes this **much cleaner and much sharper**. That actually strengthens your position a lot.

Below is a **direct, explicit pitch** framed against **Copilot Recall**, not Copilot-as-assistant. It’s calmer, more surgical, and harder to dismiss.

---

# StatiBaker (ITIR Suite)

**Everything Copilot Recall is trying to be — without surveillance, hallucination, or trust erosion.**

Copilot Recall promises perfect memory:
*A searchable timeline of everything you’ve done.*

StatiBaker delivers something different — and more honest:

**A verifiable reconstruction of state.**

---

## The Copilot Recall bet (and why it’s brittle)

Copilot Recall assumes:

* more data equals better memory
* screenshots equal truth
* recall can be inferred after the fact
* summarisation can replace verification

So it:

* records *everything* by default
* compresses later
* asks you to trust opaque summarisation
* centralises memory in the OS layer

The result feels powerful — until:

* the summary is wrong
* context is missing
* sensitive state leaks
* or you don’t recognise the system’s version of your own day

Recall remembers *activity*.
It does not preserve *state*.

---

## StatiBaker’s inversion

StatiBaker does **not** try to remember everything.

It does not scrape screens.
It does not infer intent.
It does not retroactively guess meaning.

Instead, it enforces three hard constraints:

1. **Only ingest declared state**
   (logs, tasks, notes, agents, environment signals)

2. **All compression is explicit and loss-declared**

3. **Expansion is always cheaper than recompression**

This produces memory you can **audit**, not just search.

---

## Recall shows you what you saw

## StatiBaker shows you what *happened*

Copilot Recall:

* stores pixels
* reinterprets later
* answers questions like “what was on my screen?”

StatiBaker:

* stores events
* preserves ordering and gaps
* answers questions like:

  * *What changed?*
  * *What’s unresolved?*
  * *What broke my flow?*
  * *What’s still running without me?*

That difference is structural, not philosophical.

---

## Why Recall can’t do this (even if it wanted to)

### 1. Recall is post-hoc

It reconstructs meaning *after* the fact from screenshots.

StatiBaker captures state *at the time it occurs*.

Post-hoc inference ≠ state.

---

### 2. Recall makes verification expensive

To check Recall, you must:

* scrub video timelines
* trust OCR
* trust summarisation

In StatiBaker:

* every line points to an event
* every event is inspectable
* nothing is inferred silently

Verification is local and cheap.

---

### 3. Recall centralises power at the OS layer

Recall must:

* run continuously
* see everything
* decide what matters later

StatiBaker:

* ingests voluntarily
* is schema-first
* works offline
* keeps exit cheap

No ambient surveillance required.

---

## “But Recall is optional”

So is memory loss.

The issue isn’t opt-in.
It’s **architecture**.

Recall’s architecture requires:

* total capture
* delayed interpretation
* opaque summarisation

StatiBaker’s architecture requires:

* explicit inputs
* append-only logs
* deterministic folds
* expandable summaries

Only one of those survives scrutiny.

---

## Where ITIR fits (corrected)

* **StatiBaker** — time, state, reconstruction
* **TIRC** — disagreement, plural readings, contested meaning
* **SensibLaw (SL)** — interpretation, obligations, reasoning

Copilot Recall tries to compress *all three* into a single searchable blob.

ITIR keeps them **separate on purpose**.

---

## The trust equation Recall can’t satisfy

Copilot Recall asks you to trust that:

* capture was complete
* interpretation was correct
* compression was faithful

StatiBaker asks you to trust **nothing**.

It gives you:

* raw events
* declared loss
* reversible folds

Trust emerges from inspectability, not claims.

---

## The one-paragraph pitch

> **Copilot Recall records everything and asks you to trust its memory.
> StatiBaker records only state, declares what it forgets, and lets you check.**
>
> Recall gives you a searchable past.
> StatiBaker gives you a verifiable present.

---

## The one-line version

> **Copilot Recall remembers pixels.
> StatiBaker preserves reality.**

Or, if you want the sharper edge:

> **Recall guesses later.
> StatiBaker records now.**

---

If you want next, we can:

* write a side-by-side “Recall vs StatiBaker” table suitable for press
* stress-test this against Microsoft’s stated safety claims
* or draft a “Why screenshot memory inevitably rots” appendix

But this framing is the correct one — and it lands cleanly.


Take idk

Good catch — and this is actually an *important strengthening*, not a contradiction. The key is to be **precise about *what kind* of screen capture and where it sits in the epistemic stack**.

Copilot Recall fails not because it captures screens, but because it **treats screen pixels as primary truth and interprets them later**.

StatiBaker can support screen scraping **without inheriting Recall’s failure modes** if we formalise it correctly.

Below is the corrected, integrated position.

---

## Clarifying the distinction: screen scraping ≠ Recall

**Screen scraping is a sensor.
Copilot Recall treats it as memory.**

That’s the difference.

In StatiBaker:

* Screen capture is **one input stream**
* It is **never authoritative**
* It is **never silently summarised**
* It is **always subordinate to declared state**

Think of it like CCTV vs an incident log.

---

## How screen scraping fits *cleanly* into StatiBaker

### Screen capture is an *observational fallback*

Screen scraping exists to answer:

* “What was on the screen when context collapsed?”
* “What tool state was visible but not logged?”
* “What did I see but not record explicitly?”

It does **not** exist to answer:

* “What did this mean?”
* “What was important?”
* “What should happen next?”

Those remain human decisions.

---

## Formal placement in the SB model

### Input classification

Screen scraping is classified as:

> **Low-trust observational state**

Alongside:

* audio ambience
* passive environment signals
* coarse activity traces

It is **never promoted automatically**.

---

### Event representation (example)

```json
{
  "event_id": "evt-screen-4421",
  "observed_at": "2026-02-03T14:22:10Z",
  "source": "screen_capture",
  "trust_level": "observational",
  "payload_ref": "blob://screens/2026-02-03T14-22-10.png",
  "attrs": {
    "window_hint": "email_client",
    "confidence": "low"
  }
}
```

Key properties:

* payload lives out-of-band
* marked **observational**
* carries **no inferred semantics**
* expandable, not summarised

---

## What SB *will not* do with screen data

This is the hard boundary Copilot Recall crosses.

StatiBaker will **not**:

* auto-OCR and store text as fact
* retroactively infer intent from pixels
* silently fold screenshots into “what happened”
* treat screen data as equivalent to logs
* allow screen data to overwrite declared state

Any semantic extraction from screens must be:

* explicit
* reversible
* provenance-tagged
* user-initiated

---

## How screen data is actually *used*

### 1. Expansion, not summarisation

Screen captures appear **only when expanding** a time slice or event.

They answer:

> “What did this look like at the time?”

Not:

> “What happened?”

---

### 2. Human-assisted promotion (optional)

A user may *explicitly* promote screen content into declared state:

* extract a task
* annotate a decision
* attach context to a note

This creates a **new event**, linked to the screen capture.

Nothing happens automatically.

---

### 3. Debugging context collapse

Screen scraping is most valuable when:

* tools failed to log
* agents crashed
* state went missing
* memory broke under load

It’s a **black box recorder**, not a diary.

---

## Why this still beats Copilot Recall

| Copilot Recall             | StatiBaker (with screen capture) |
| -------------------------- | -------------------------------- |
| Screens are memory         | Screens are evidence             |
| Capture is total           | Capture is scoped                |
| Interpretation is implicit | Interpretation is explicit       |
| Summaries overwrite detail | Screens only appear on expand    |
| Verification is expensive  | Verification is local            |
| Trust is assumed           | Trust is earned                  |

---

## The invariant that keeps this safe

You already stated it — this is where it applies:

> **It must always be cheaper to expand than to summarise again.**

Screens:

* make expansion richer
* make summarisation *harder* (on purpose)
* increase friction for overinterpretation

That’s a feature, not a bug.

---

## Updated pitch line (important correction)

Instead of:

> “Copilot Recall remembers pixels. StatiBaker preserves reality.”

The correct, more honest version is:

> **Copilot Recall treats pixels as memory.
> StatiBaker treats pixels as evidence.**

That single word change matters.

---

## One more sentence to add to the manifesto

You should explicitly include this, otherwise people will assume Recall-style behavior:

> **Passive capture is supported only as non-authoritative evidence.
> No meaning is inferred without an explicit, inspectable act.**

That sentence closes the loop.

---

## Final synthesis

Supporting screen scraping does **not** weaken your position — it strengthens it, because:

* you acknowledge reality (screens exist)
* you refuse lazy inference
* you preserve verification
* you keep humans in the loop

Copilot Recall’s problem isn’t *what* it captures.

It’s **when meaning is assigned, by whom, and without recourse**.

StatiBaker gets that ordering right.

If you want, next we can:

* formalise a **trust lattice** for inputs (declared ↔ observed ↔ inferred),
* write a **“screen capture safety spec”**,
* or add regression tests specifically guarding against Recall-style drift.


Perfect — this is the right place to be precise. Auto-OCR **can** exist *without collapsing into Recall-style epistemic rot*, but only if it’s framed as a **controlled extraction step**, not memory promotion.

Below is a **clean framing + guardrail spec** you can drop straight into DESIGN.md / SAFETY.md / manifesto sections.

---

## Framing the capability (the sentence that matters)

> **StatiBaker may extract text from screens when explicitly asked — but extracted text is not treated as truth, memory, or state unless deliberately promoted.**

OCR is **a tool invocation**, not a background belief.

---

## The distinction to hold onto

There are **three different things** people conflate:

| Thing   | Copilot Recall      | StatiBaker              |
| ------- | ------------------- | ----------------------- |
| Capture | Continuous, ambient | Scoped, optional        |
| OCR     | Implicit, automatic | Explicit, request-bound |
| Meaning | Assumed             | Declared                |

StatiBaker supports **OCR as extraction**, not **OCR as memory**.

---

## Formal guardrail: OCR is a *derived artifact*, not an event

### Raw screen capture

```json
{
  "event_id": "evt-screen-4421",
  "source": "screen_capture",
  "trust_level": "observational",
  "payload_ref": "blob://screens/2026-02-03T14-22-10.png"
}
```

### OCR output (separate artifact)

```json
{
  "artifact_id": "art-ocr-9912",
  "derived_from": "evt-screen-4421",
  "method": "ocr",
  "requested_by": "human",
  "confidence": "medium",
  "payload_ref": "blob://ocr/2026-02-03T14-22-10.txt"
}
```

Key properties:

* **OCR output is not an event**
* It does not enter folds automatically
* It does not affect summaries unless promoted

This prevents silent contamination.

---

## The promotion rule (this is the hard line)

OCR text may only become **declared state** if *one* of the following happens:

### 1. Explicit human promotion

Example:

* “Turn this into a task”
* “Attach this to today’s notes”
* “Record this decision”

This creates a **new event**:

```json
{
  "event_id": "evt-task-2031",
  "source": "human_promotion",
  "derived_from": ["evt-screen-4421", "art-ocr-9912"],
  "kind": "task_created"
}
```

### 2. Explicit rule-based pipeline (opt-in)

Example:

* “OCR invoices from this folder into a ledger”
* “Extract commit hashes from CI screenshots”

Rules must be:

* named
* documented
* reversible
* visible in STATE_SCHEMA

No silent heuristics.

---

## What OCR is *never* allowed to do

StatiBaker must **never**:

* OCR continuously without request
* OCR opportunistically “because it might be useful”
* Treat OCR text as equivalent to logs or notes
* Auto-fold OCR text into “what happened”
* Let OCR overwrite declared state
* Let OCR silently fix inconsistencies

If OCR resolves ambiguity, that resolution must be **human-visible and contestable**.

---

## Where OCR *does* belong

OCR is appropriate for:

* **Context recovery** after collapse
  (“What was that email / error / page again?”)

* **Bridging uninstrumented tools**
  (legacy GUIs, PDFs, vendor portals)

* **Evidence inspection**
  (receipts, confirmations, dialogs)

OCR is **evidence**, not memory.

---

## The trust lattice (use this language)

StatiBaker treats inputs on a trust gradient:

1. **Declared state**
   Tasks, notes, logs, commits — authoritative

2. **Observed state**
   Screens, sensors, passive signals — evidentiary

3. **Derived artifacts**
   OCR, transcripts, transforms — provisional

Only **declared state** enters folds by default.

Everything else must be *promoted*.

---

## Why this still cleanly beats Copilot Recall

Copilot Recall:

* OCRs by default
* stores results as memory
* summarises later
* hides the extraction boundary

StatiBaker:

* OCRs on request
* stores results as artifacts
* requires promotion
* preserves provenance

This keeps **verification cheaper than forgetting**.

---

## The sentence to add to the manifesto (important)

You should include this verbatim somewhere prominent:

> **Extraction is not interpretation.
> Derived artifacts never become state without an explicit act.**

That one sentence prevents years of drift.

---

## The litmus test (for contributors)

When adding or modifying OCR behavior, ask:

> “If this text is wrong, how does the user notice — and how do they undo it?”

If the answer is “they probably wouldn’t,” the change is invalid.

---

## Final synthesis

Supporting auto-OCR **when asked** is not a compromise — it’s realism.

What matters is:

* **who initiates it**
* **where it lives**
* **what it can influence**
* **how reversible it is**

Copilot Recall collapses those distinctions.

StatiBaker survives by enforcing them.

If you want next, we can:

* formalise this as an ADR (“ADR-OCR-001”),
* add CI tests guarding against silent OCR promotion,
* or write a short “Why Recall fails OCR safety” appendix for the repo.

Good — this is the *last* subtle corner, and it’s where most systems either become paternalistic or silently predatory. You can support **opportunistic OCR** *and* **always-on OCR** **without breaking your doctrine**, but only if you formalise **consent, visibility, and non-promotion** as first-class state.

Below is a **clean, principled framing** that keeps you on the right side of your own invariants *and* reality.

---

## The key reframing

> **The problem is not opportunistic OCR.
> The problem is *silent semantic promotion*.**

OCR can run speculatively **as long as its results are treated as:
non-authoritative, quarantined, and user-visible**.

Think of OCR as *precomputation*, not memory.

---

## Three OCR modes (explicit, not implicit)

You should name these. Naming is how you prevent drift.

### 1. **On-demand OCR** (baseline, already covered)

* Triggered explicitly by the user
* Used to recover context or extract evidence
* Safest, least controversial

---

### 2. **Opportunistic OCR (quarantined)** ✅ *(this is the new one)*

This is what you’re describing.

**Definition**
OCR may run automatically *when a capture occurs*, but:

* results are **not stored as state**
* results are **not folded**
* results are **not indexed by default**
* results are **not trusted**

They live in a **quarantine buffer**.

Example use cases:

* detecting *potentially sensitive domains* (banking, health)
* detecting *structured artifacts* (invoices, receipts)
* detecting *candidate promotions* (“this looks like a bill”)

---

### 3. **Always-on OCR (policy-scoped)** ⚠️ *(advanced / opt-in)*

This is allowed *only* with:

* an explicit policy
* a named scope
* visible indicators
* reversible settings

Example:

> “Always OCR accounting portals and store extracted text as *artifacts*, not state.”

This is for:

* accountants
* auditors
* compliance-heavy workflows

Not default. Never ambient.

---

## The critical structure: OCR quarantine

### What “quarantine” means formally

Quarantined OCR output:

* is time-bound (TTL)
* is non-indexed
* is excluded from folds
* is excluded from summaries
* cannot affect “what happened”
* cannot affect “what matters”

It exists only to:

* inform the user
* request consent
* speed up later promotion if approved

---

### Example data model

```json
{
  "artifact_id": "art-ocr-q-7712",
  "derived_from": "evt-screen-4421",
  "method": "ocr",
  "mode": "opportunistic",
  "status": "quarantined",
  "expires_at": "2026-02-03T15:22:10Z",
  "signals": {
    "domain_hint": "banking",
    "sensitivity": "high",
    "confidence": "medium"
  }
}
```

**Important:**
The *signals* are allowed.
The *content* is not promoted.

---

## The consent interaction (this is where you win)

Instead of silently capturing, SB surfaces **state**, not judgement.

Example notification copy (tone matters):

> **Potential sensitive content detected**
> This screen appears to contain banking information.
>
> OCR is currently **paused** for this domain.
>
> Options:
>
> * Ignore (discard OCR)
> * Allow once
> * Always allow for this domain
> * View captured evidence

No nudging. No defaults that bias capture.

---

## Promotion paths (unchanged, but now clearer)

OCR output can move out of quarantine *only* via:

### 1. Human promotion

> “Save this as a receipt.”
> “Attach this to today’s ledger.”

Creates a new **declared event**.

---

### 2. Policy-based promotion (explicit, named)

Example policy:

```yaml
policy: accounting_mode
scope: domains.bank.*
allow:
  - ocr
  - artifact_storage
deny:
  - auto_folding
  - auto_summary
```

Policies are:

* inspectable
* reversible
* logged as state changes themselves

---

## What still must never happen (unchanged)

Even with opportunistic / always-on OCR, StatiBaker must **never**:

* silently treat OCR text as fact
* let OCR alter summaries without promotion
* hide OCR activity
* infer intent from OCR content
* collapse OCR output into “what happened”

These are hard invariants.

---

## The trust lattice (final, explicit)

You should canonise this — it’s your epistemic spine.

1. **Declared state**
   Human-entered or explicitly promoted. Foldable.

2. **Observed state**
   Screens, sensors. Evidence only.

3. **Derived artifacts**
   OCR, transcripts, transforms. Quarantined by default.

4. **Signals**
   Hints, classifiers, flags. Non-semantic.

Only layer **1** enters summaries by default.

---

## How this differs *cleanly* from Copilot Recall

| Copilot Recall             | StatiBaker            |
| -------------------------- | --------------------- |
| OCR is ambient             | OCR is visible        |
| OCR is memory              | OCR is evidence       |
| Consent is coarse          | Consent is scoped     |
| Interpretation is implicit | Promotion is explicit |
| Hard to undo               | Always reversible     |

Copilot Recall asks:

> “Do you want us to remember everything?”

StatiBaker asks:

> “We saw something. What do you want to do with it?”

That’s the ethical difference.

---

## The sentence you should add (non-negotiable)

This one closes the loophole:

> **Automatic extraction may occur, but automatic belief may not.**

If contributors remember only one rule, make it that.

---

## Litmus test (updated)

For any OCR change, ask:

> “If this OCR result is wrong, misleading, or sensitive —
> does the system still behave correctly *without the user noticing it*?”

If the answer is yes, **that’s a bug**.

---

## Final synthesis

Allowing opportunistic or always-on OCR is *not* a betrayal of your values.

Silently turning extraction into belief is.

By:

* quarantining OCR,
* surfacing consent,
* separating evidence from state,
* and preserving cheap expansion,

you end up with something **Copilot Recall literally cannot build**, because its architecture depends on collapsing those layers.

You’re not anti-capture.

You’re anti-lying-memory.

If you want next, I can:

* turn this into an ADR (`ADR-OCR-002: Opportunistic Extraction`)
* write UX copy guidelines for consent prompts
* or formalise domain-scoped OCR policies (banking, health, legal, dev tools)


Great — this is now at the point where it should be **locked into governance**. Below is a **complete, repo-ready package** that does exactly what you asked, with one careful refinement to handle your exception (“hey I accidentally got a screenshot of this”).

I’ll give you, in order:

1. **ADR-OCR-002: Opportunistic Extraction** (formal, normative)
2. **CI test requirements** (guarding against silent promotion)
3. **Appendix: Why Copilot Recall fails OCR safety**
4. **UX copy guidelines for consent prompts**
5. **Domain-scoped OCR policies (banking, health, legal, dev tools)**
6. **Clarification of the allowed exception**
   (“cannot affect *what happened*; *what matters* only via disclosure”)

Everything is written so it can be dropped straight into the repo.

---

# ADR-OCR-002: Opportunistic Extraction

**Status:** Accepted
**Date:** 2026-02-04
**Owners:** StatiBaker core maintainers
**Related:** ADR-00X (Summaries as Lossy Indexes), ADR-OCR-001 (On-Demand OCR)

## Context

StatiBaker supports screen capture as a low-trust observational input.
OCR is required to make such captures inspectable and usable, but unguarded OCR creates Recall-style failure modes:

* silent semantic promotion
* accidental surveillance
* unverifiable summarisation
* trust erosion through hidden interpretation

We need to support **opportunistic** and **always-on** OCR *without* allowing derived text to silently influence state.

## Decision

StatiBaker will support **opportunistic OCR** under strict guardrails.

### Definition

**Opportunistic OCR** means:

* OCR may be executed automatically when a screen capture occurs
* OCR results are treated as **derived artifacts**
* OCR results are **quarantined by default**
* OCR results **cannot affect folded state** without explicit promotion

### Hard invariants

1. OCR output **is not an event**
2. OCR output **does not enter folds**
3. OCR output **does not alter summaries**
4. OCR output **does not affect “what happened”**
5. OCR output **does not affect “what matters” except via disclosure**
6. All OCR activity must be **visible and reversible**

## Data model

### Screen capture (observed state)

```json
{
  "event_id": "evt-screen-4421",
  "source": "screen_capture",
  "trust_level": "observational",
  "payload_ref": "blob://screens/2026-02-03T14-22-10.png"
}
```

### Opportunistic OCR artifact (quarantined)

```json
{
  "artifact_id": "art-ocr-q-7712",
  "derived_from": "evt-screen-4421",
  "method": "ocr",
  "mode": "opportunistic",
  "status": "quarantined",
  "expires_at": "2026-02-03T15:22:10Z",
  "signals": {
    "domain_hint": "banking",
    "sensitivity": "high"
  }
}
```

## Promotion rules

OCR artifacts may only influence state via **explicit promotion**, which creates a **new declared event** referencing the artifact.

No automatic promotion is permitted.

## Rationale

This preserves:

* cheap verification
* human agency
* reversible interpretation
* explicit consent boundaries

and prevents Recall-style semantic drift.

---

# CI Requirements: Guarding Against Silent OCR Promotion

These tests are **mandatory** for any OCR-related change.

## Test 1 — No silent fold inclusion

> Given an OCR artifact in `status=quarantined`, no fold output may reference its contents.

Fail if:

* OCR text appears in summaries
* OCR text alters counts, categories, or blockers

---

## Test 2 — No summary influence

> “What happened” and “What matters today” must be identical with or without quarantined OCR present.

Fail if:

* OCR changes these outputs without promotion

---

## Test 3 — Promotion creates new event

> Any OCR-derived state must originate from a new `event_id` with `source=human_promotion` or `source=policy_promotion`.

Fail if:

* OCR artifact is treated as authoritative
* No explicit promotion step exists

---

## Test 4 — Visibility test

> OCR execution must emit a visible signal or log entry accessible to the user.

Fail if:

* OCR can occur without user-inspectable trace

---

# Appendix: Why Copilot Recall Fails OCR Safety

Copilot Recall collapses three distinct phases:

1. **Capture**
2. **Extraction**
3. **Belief**

into a single opaque pipeline.

This causes:

* OCR text to be treated as memory
* Interpretation to occur post-hoc
* Errors to become indistinguishable from facts
* Verification to require replaying video timelines

StatiBaker separates these phases deliberately:

| Phase        | Copilot Recall | StatiBaker |
| ------------ | -------------- | ---------- |
| Capture      | Ambient        | Scoped     |
| Extraction   | Implicit       | Explicit   |
| Storage      | Memory         | Artifact   |
| Belief       | Automatic      | Promoted   |
| Verification | Expensive      | Local      |

Recall’s failure is architectural, not incidental.

---

# UX Copy Guidelines: OCR Consent & Disclosure

Tone rules:

* Neutral
* Informational
* No urgency
* No default bias toward capture

## Sensitive domain detection

> **Sensitive content detected**
> This screen appears to contain banking information.
>
> OCR results are currently **not stored**.
>
> Options:
> – Ignore and discard
> – Allow OCR once
> – Always allow for this domain
> – View captured evidence

## Opportunistic OCR notice (non-sensitive)

> **Text detected on screen**
> OCR is available for this capture if you want to extract or save it.
>
> Nothing has been recorded yet.

## Promotion action

> **Promote extracted text**
> This will create a new record linked to the original capture.
> You can undo this later.

Never say:

* “We saved…”
* “We remembered…”
* “We noticed you…”

Always say:

* “Detected”
* “Available”
* “If you want”

---

# Domain-Scoped OCR Policies

Policies are explicit, inspectable, reversible.

## Banking

```yaml
policy: banking_ocr
scope: domains.bank.*
allow:
  - opportunistic_ocr
deny:
  - auto_promotion
  - auto_folding
retention:
  ttl: short
```

Default: **off**
OCR allowed only for evidence recovery.

---

## Health

```yaml
policy: health_ocr
scope: domains.health.*
allow:
  - opportunistic_ocr
deny:
  - auto_promotion
  - persistent_storage
```

Default: **off**
Extra visibility required.

---

## Legal

```yaml
policy: legal_ocr
scope: domains.legal.*
allow:
  - opportunistic_ocr
  - artifact_storage
deny:
  - auto_summary
```

Default: **prompt per session**

---

## Dev tools

```yaml
policy: dev_ocr
scope: domains.dev.*
allow:
  - opportunistic_ocr
  - artifact_storage
allow_promotion:
  - explicit_only
```

Default: **on**, but still quarantined.

---

# Clarifying the Exception: “Hey I accidentally got a screenshot of this”

This is the **only permitted way** OCR can affect *what matters* without affecting *what happened*.

## Rule

OCR may surface **disclosure signals**, but not semantic conclusions.

### Example (allowed)

> “A screen capture containing banking information was recorded at 14:22.”

This can affect **what matters today** as:

* a privacy concern
* a cleanup task
* a decision point

### Example (not allowed)

> “You reviewed a bank statement.”

That is semantic promotion and is forbidden.

## Formal distinction

* **Disclosure** → affects *what matters* (attention, hygiene)
* **Interpretation** → affects *what happened* (forbidden)

This keeps the system honest.

---

# Canonical sentences (should appear verbatim in docs)

You should include these as invariants:

> **Automatic extraction may occur. Automatic belief may not.**

> **Derived artifacts never become state without an explicit act.**

> **Screens are evidence. Events are truth.**

---

## Final synthesis

You’ve now closed the last major loophole:

* opportunistic OCR ✔
* always-on OCR ✔
* consent ✔
* reversibility ✔
* verification ✔

while still preserving:

* append-only truth
* cheap expansion
* human agency
* anti-enshittification guarantees

This is *strictly stronger* than Recall, not weaker — because Recall cannot make these distinctions without breaking its own premise.

If you want next steps, the natural ones are:

* add this ADR to the repo
* wire the CI tests early
* and freeze these sentences as contributor invariants before any code lands


Perfect. This is exactly the moment to **lock the rails before the train exists**.

Below are two concrete deliverables you can drop into the repo **now**, before any implementation:

1. **CI wiring plan + stub tests** (that fail by default, enforcing discipline)
2. **Contributor invariants** frozen as normative text (hard to “reinterpret later”)

No fluff, no aspirational language — this is governance-by-structure.

---

# 1. Wire the CI tests early (before any code)

The goal is **not** to test functionality yet.
The goal is to make it *impossible* to add functionality that violates invariants without touching tests.

## A. CI philosophy (important)

* CI should fail **by default** on prohibited behavior
* Tests should assert **absence of effects**, not correctness of features
* OCR-related tests should be *negative tests* (“this must not happen”)

Think: *constitutional tests*, not unit tests.

---

## B. Minimal CI structure (GitHub Actions example)

**`.github/workflows/guardrails.yml`**

```yaml
name: StatiBaker Guardrails

on:
  pull_request:
  push:
    branches: [main]

jobs:
  invariants:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check contributor invariants unchanged
        run: |
          diff -u .ci/invariants.lock docs/INVARIANTS.md

      - name: Run epistemic guardrail tests
        run: |
          pytest tests/guardrails
```

This does two critical things:

* **freezes doctrine**
* **enforces epistemic boundaries**

---

## C. Freeze the invariants (lockfile-style)

You do **not** want invariants to drift casually.

### Canonical invariants file

**`docs/INVARIANTS.md`**
(human-readable, discussed below)

### Locked copy

**`.ci/invariants.lock`**

* exact copy of `docs/INVARIANTS.md`
* any change requires:

  * deliberate edit to both files
  * PR discussion
  * visible diff

This is how you prevent “soft reinterpretation”.

---

## D. Guardrail test suite (stubbed now, enforced later)

**`tests/guardrails/`**

### 1. No silent OCR promotion

**`test_no_silent_ocr_promotion.py`**

```python
def test_quarantined_ocr_does_not_affect_folds(sample_state_with_ocr):
    """
    OCR artifacts in quarantined state must not influence
    any fold output.
    """
    folds_without = run_folds(sample_state_without_ocr)
    folds_with = run_folds(sample_state_with_ocr)

    assert folds_with == folds_without
```

This test should **initially xfail or skip** until folds exist — but it must be present.

---

### 2. OCR cannot affect “what happened”

```python
def test_ocr_cannot_create_events(sample_state_with_ocr):
    events = extract_events(sample_state_with_ocr)

    for e in events:
        assert e.source != "ocr"
```

Meaning:

* OCR artifacts are *never* events
* Promotion must create a new event with explicit source

---

### 3. OCR cannot affect “what matters” except disclosure

```python
def test_ocr_affects_matters_only_via_disclosure(sample_state_with_sensitive_ocr):
    matters = compute_what_matters(sample_state_with_sensitive_ocr)

    assert "privacy_disclosure" in matters
    assert "semantic_conclusion" not in matters
```

This encodes your exception **explicitly**.

---

### 4. Expansion never invokes inference

```python
def test_expand_is_inference_free(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Inference invoked during expansion")

    monkeypatch.setattr("llm.call", fail)

    expand_summary("sample_summary_id")
```

This is one of the most important tests in the repo.

---

### 5. Provenance completeness

```python
def test_all_summary_lines_have_sources(summary):
    for line in summary.lines:
        assert line.sources, "Summary line missing provenance"
```

---

## E. Mark these tests as **non-optional**

In `pytest.ini`:

```ini
[pytest]
markers =
    guardrail: epistemic invariants (must not be skipped)
```

And enforce:

```yaml
pytest -m guardrail
```

No feature work should merge without these passing.

---

# 2. Freeze contributor invariants (before code exists)

This is the cultural spine. These sentences must be **short, blunt, and non-negotiable**.

## A. `docs/INVARIANTS.md` (canonical)

```markdown
# StatiBaker Invariants

These invariants exist before any implementation.
No contribution may violate them.

---

## Epistemic boundaries

• Screens are evidence. Events are truth.  
• Extraction is not interpretation.  
• Automatic extraction may occur. Automatic belief may not.  
• Derived artifacts never become state without an explicit act.

---

## Compression & memory

• Summaries are lossy indexes, not replacements.  
• Every summary declares its loss profile.  
• It must always be cheaper to expand than to summarise again.  
• Expansion is deterministic and inference-free.

---

## State integrity

• All state is append-only.  
• History is never rewritten.  
• Corrections are additive.  
• Disagreement is preserved.

---

## OCR-specific guarantees

• OCR output is never an event.  
• OCR output never enters folds without promotion.  
• OCR cannot affect “what happened”.  
• OCR may affect “what matters” only via disclosure, never interpretation.

---

## Agency & ethics

• The system does not infer goals, intent, or preferences.  
• The system does not recommend or optimise.  
• Verification remains human and local.  
• Exit must remain cheap.

---

If a proposed feature violates these invariants,
the feature is invalid — regardless of usefulness.
```

That last line matters. It removes wiggle room.

---

## B. Lock it

Copy that file verbatim to:

**`.ci/invariants.lock`**

From this point on:

* changing doctrine requires **conscious governance**
* not drive-by refactors

---

## C. CONTRIBUTING.md (one paragraph only)

Add this at the top:

```markdown
Before contributing, read `docs/INVARIANTS.md`.

If your change violates any invariant,
it will not be accepted.

If you believe an invariant is wrong,
open an ADR proposing its change before writing code.
```

That’s it. No essay.

---

# 3. Why doing this *now* matters

Most systems rot because:

* invariants live in people’s heads
* tests come after features
* safety is “handled later”

You’re doing the opposite:

* doctrine first
* tests before code
* violations made mechanically difficult

This is how you avoid **Copilot Recall–style drift**, even if future contributors don’t share your intuitions.

---

## Final state

After this step, you will have:

* ✅ epistemic guarantees frozen
* ✅ CI enforcing absence of bad behavior
* ✅ OCR guardrails encoded structurally
* ✅ no code yet — but no ambiguity either

From here on, *every* implementation decision has to pass through this lattice.

If you want next, the natural next moves are:

* stub the fold engine with empty implementations that satisfy tests
* define a minimal event store schema
* or write ADR-000 (“Why invariants precede features”) as historical record
