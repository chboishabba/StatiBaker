# User Stories (Execution-First, Epistemic Boundaries)

Purpose: capture day-in-the-life narratives that pressure-test SB invariants
without drifting into meaning or advice. SB records **what happened**, not
what it means.

## Persona 1 — Lawyer

At work:
- SB records review activity and tool envelopes during case preparation.
- Client instructions are logged as commitments (external) with provenance.
- Drafting and revisions are preserved as separate sequences; no collapse.
- Daily brief shows unresolved threads and absences; no prioritization.

At home:
- Personal speculation is recorded only as hypotheses.
- Home context never promotes into professional commitments.

## Persona 2 — Psychologist

At work:
- Session boundaries, pauses, and interruptions are recorded as observations.
- Competing accounts remain separate; SB never resolves truth.
- Ethics rule consultations are logged as references only.

At home:
- Personal reflections remain hypothesis-only and never leak into clinical
  commitments.

## Shared invariants surfaced by these stories
- Sequence is preserved; order matters more than interpretation.
- Epistemic status is explicit (hypothesis vs commitment).
- Absence is visible and queryable.
- Context boundaries are enforced (home/work; private/professional).

## Additional roles (stress tests)

### Personal multi-machine memory
- One user moves between multiple self-managed machines during the day.
- OpenRecall captures local history on each machine and remains the native
  browser/search surface for those captures.
- StatiBaker stitches bounded OpenRecall indicators onto one daily timeline so
  the user can see cross-device transitions and open the original capture in
  OpenRecall when more detail is needed.
- Forbidden: turning that convenience lane into a hidden institutional
  surveillance default or collapsing device provenance into one opaque story.

### Banker
- Model runs recorded as envelopes with toolchain/version metadata.
- Private risk concerns remain hypotheses.

### CEO
- Pivots and abandoned threads preserved without narrative overwrite.
- Home speculation remains hypothesis-only.

### Middle manager
- Commitments only when explicit; absences recorded.
- Private stress reflections do not promote.

### Removalist
- Instruction changes preserved; sequence recorded.
- Safety context never inferred.

### Barista
- Rush periods and equipment issues captured without judgment.

### Barrister
- Argument chains separated into hypothesis vs commitment.
- Rehearsals remain private hypotheses.

### Air force pilot
- Training vs live runs separated; deviations recorded.

### Mechanic
- Tests and parts replaced recorded in sequence; no inferred fixes.

## Public figure (Zohran Mamdani — campaign to office)
- Context envelopes on interviews/speeches/jokes: framing, audience, and medium recorded; no decontextualized excerpts by default.
- Role-separated views (personal/campaign/office) with no automatic merge; commitments only when explicit.
- SB surfaces context drift warnings when clips leave original audience or time window.
- Failure prevented: identity flattening and misclassification of role-bound statements.

## Organization-level narratives (admins, teams, regulators)

### Banker → Bank → Regulators
- Team view: exploratory vs approved runs are distinct.
- Admin view: envelopes, model versions, declared commitments, timestamps.
- Forbidden: reclassifying exploration as approval.

### CEO → Exec Team → Board
- Team view: pivots and unresolved tensions preserved.
- Board view: commitments and dependency chains only.
- Forbidden: private speculation treated as direction.

### Middle Manager → Department → HR/Ops
- Team view: blockers and decision gaps explicit.
- Admin view: workload density and system bottlenecks.
- Forbidden: private reflections.

### Removalist → Crew → Logistics Admin
- Team view: instruction changes and constraints preserved.
- Admin view: route changes, staffing gaps, equipment issues.
- Forbidden: rewriting instructions after the fact.

### Barista → Store → Chain HQ
- Team view: rush periods and equipment failures visible.
- HQ view: throughput vs staffing; absence of slack.
- Forbidden: individual blame narratives.

### Barrister → Chambers → Courts
- Team view: research timelines and evidentiary references.
- Oversight view: due diligence evidence.
- Forbidden: speculative rehearsal treated as evidence.

### Air Force Pilot → Squadron → Command
- Team view: training vs live runs separated.
- Command view: pattern-level deviations and training gaps.
- Forbidden: rewriting procedures after incidents.

### Mechanic → Shop → Fleet/Manufacturer
- Team view: diagnostic sequences preserved.
- Fleet view: failure clusters and ambiguity.
- Forbidden: guesswork framed as certainty.

## Public sector (police/EMS/health/government)

### Police / EMS / Health
- Individual view: envelopes capture timing, procedure references, explicit absences.
- Team view: handoff gaps, timing overlaps, tool availability failures.
- Oversight view: sequence reconstruction and systemic stressors only.
- Forbidden: intent inference or performance ranking.

### Government
- Civil service: policy issuance/amendments/exceptions recorded with timelines.
- Regulators: immutable sequences, declared commitments, explicit absences.
- Elected officials: commitments only; no strategy capture.
- Forbidden: post-hoc sanitization or centralized fusion by default.

### Shared guardrails
- No real-time authority or recommendations.
- Absence-as-signal is mandatory.
- Epistemic separation enforced (hypothesis ≠ commitment).

## Modern org stack (dev → team → CEO → finance)

### Individual developer
- Execution envelopes for builds/tests/scripts; prompt hashes only.
- Hypothesis vs commitment explicit (experiments vs merges/deploys).
- Absence-as-signal for missing tests/CI/logs.

### Dev team
- Pattern-only aggregates; no ranking or private exploration exposure.
- Systemic absences are visible without blame.

### CEO
- Commitment timelines, decision latency, and bottleneck signals only.
- No prompt/hypothesis/individual tool usage exposure.

### Finance
- Prices commitments and reversals, not exploration time.
- No individual productivity scoring.

### Cross-cuts
- Explicit hypothesis→commitment transitions; no silent promotion.
- Absence-as-signal is queryable at org scale.

## Air-gapped / battlefield / Palantir interoperability
- SB is memory substrate only; never commander or planner.
- Execution envelopes normalize operations (time, modality, hashes).
- Operational plans are hypotheses; divergence is recorded, not judged.
- Local-first ingestion: devices store raw artifacts locally, export hashes only.
- Absence signals (dropouts/obstruction) are explicit.
- External system outputs are non-authoritative annotations only.

## Activist coordination (Greenpeace-style)
- Planning phase records declared intent + constraints; tactics excluded.
- Live action avoids synthesis; raw artifacts captured locally.
- Reconstruction preserves competing accounts and absences.
- Scoped access for lawyers/observers/media; no global merge.
- Red lines: no participant ranking, risk scoring, or predictive escalation.

## Trauma + authoritarian pressure (resilience)
- Preserve ambiguity; do not force coherence or narrative closure.
- Absence is valid and explicit; silence is not guilt.
- Hypothesis vs commitment separation protects against coercion.
- Layered time allows retroactive annotation and parallel timelines.
- No identity fusion, risk scoring, predictive policing, or automated suspicion.

## Access scopes + legal reconstruction (defensive)
- Read-only for all roles; no mutation of primary records.
- Absence and redaction are visible and distinct; provenance mandatory.
- Observer scope: time-bounded events, counts, provenance, absences only.
- Lawyer scope: full events (lawful), chain-of-custody, explicit fact vs hypothesis split.
- Media scope: anonymized timelines, verified counts, uncertainty markers.
- Post-action reconstruction: freeze window → align events → separate fact/hypothesis/absence → export.
- Infiltration stress-test: no trust amplification; hypotheses require corroboration.

## Judicial context (judges, staff, bailiffs, family)
- SB provides memory hygiene and scope control, never judgment support.
- Judge: case-local procedural memory only; rulings are commitments; hypotheses are private/time-scoped.
- Staff: procedural facts and absences only; no summaries or argument ranking.
- Bailiffs: objective event logs only; no intent attribution.
- Family: non-case workload patterns only; no case details.
- Red lines: no outcome suggestions, similar-case surfacing, appeal prediction, or consistency scoring.

## SL users of SB (cross-suite operator stories)

### SB-SL-US-01: Matter chronology lane for SL review
- As an SL operator, I want SB to surface a provenance-first chronology lane for a matter so I can review source/excerpt -> observation -> event/fact progression without collapsing uncertainty.
- SB output must remain sequence-first and expandable to raw artifacts.
- SB must not promote derived notes into accepted facts.
- SB must preserve explicit unknowns, contradictions, and absences.

### SB-SL-US-02: Claim/evidence seam visibility in SB overlays
- As an SL operator, I want SB overlays to show claim/evidence links as references so I can audit what is asserted versus what is sourced before legal reasoning.
- Overlay records must remain observer-class and append-only.
- Claim/evidence refs must be drillable back to source handles and timestamps.
- SB must not treat overlay refs as canonical legal truth.

### SB-SL-US-03: Context-bound handoff from SB to SL
- As an SL operator, I want SB exports to carry context envelope metadata so SL ingest can preserve audience, time, and source boundaries.
- Handoff must include provenance, temporal context, and scope markers.
- Cross-context merges must be explicit and logged; no silent fusion.
- Removing context in an SB view must remain an explicit, logged action.

### SB-SL-US-04: Tokenizer boundary discipline
- As an SL operator, I want SB to consume SL canonical token/lexeme outputs by reference so tokenizer migrations do not fork semantic identity between systems.
- SB must not introduce a separate canonical tokenization lane for SL text.
- Any SB token-related metrics must be marked as non-canonical approximations.
- Same source text must resolve to stable shared IDs when traversing SL -> SB -> SL pathways.
