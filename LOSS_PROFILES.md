# Loss Profiles (Explicit Compression)

## Purpose
Define what is compressed, what is retained, and how expansion works.

## Active loss profiles

### 1) collapse_low_signal_events
- Scope: consecutive events with `low_signal=true` and identical signature.
- Signature fields: `source`, `type`, `text`, `thread_id`.
- Output: one collapsed event with:
  - `collapsed_count`
  - `collapsed_ids`
- Expansion: emits placeholder events using the collapsed signature and IDs.
- Declared loss: original timestamps inside the collapsed run are not preserved.

## Expansion contract
- Expanded output must preserve event count and signature order.
- Any loss must be declared in the loss profile.

## Non-goals
- No semantic summarization.
- No importance scoring.
