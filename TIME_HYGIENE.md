# Time Hygiene Policy (Documented Only)

## Principles
- Aging is visible, not corrective.
- No silent deletion or forgetting.
- Saturation yields labels, not summaries.

## Aging rules
- Carryover age is tracked in `carryover_age_days`.
- Old carryovers may be flagged but not removed.

## Saturation handling
- When carryover exceeds capacity, mark a `carryover_saturation` label.
- Do not collapse or summarize without explicit loss profile.

## Inactivity handling
- Long gaps are explicit as missing input days.
- SB should emit a daily brief that states missing sources.
