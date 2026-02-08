# Chat Flow Lane Mode (Alternate View Spec)

This document defines a true lane-style chat flow view as an alternate mode to
the existing timeline strip.

## Why

The current strip is a linear sequence with time-scaled block widths. It is
useful for dense days, but it is not a classical waterfall/lane chart.

Lane mode adds:
- explicit per-thread lanes,
- cross-lane connectors for context switches,
- clearer “one thread hammered” vs “many thread jumps” reading.

## Mode model

UI mode selector:
- `Auto` (default)
- `Timeline Strip`
- `Thread Lanes`

Auto policy:
- prefer `Thread Lanes` when complexity is moderate,
- fall back to `Timeline Strip` for dense days.

Initial fallback thresholds (tunable):
- lane mode allowed when `message_count <= 600` and `thread_count <= 40`
- otherwise auto-select strip mode.

## Lane chart semantics

- X-axis: absolute message time (continuous time scale).
- Y-axis: thread lanes.
- Node: one chat message.
- Connector: message-to-message transition in chronological order.

Connector types:
- same-thread transition:
  - stays in-lane,
  - neutral connector styling.
- thread switch transition:
  - cross-lane connector,
  - emphasized stroke/style.

Node semantics:
- color algorithm stays user-selectable (`thread`, `time of day`, `role`,
  `switch`).
- role marker can be shape or outline style, not color-only.
- hover details should include timestamp, role, thread title, and switch state.

## Lane ordering

Default lane ordering:
1. dominant thread first (highest message count),
2. remaining lanes by message count descending,
3. stable tie-break by thread id.

Optional future ordering:
- first-seen time,
- recent-activity first.

## Dense day handling

When lane mode is unavailable/too dense:
- show explicit reason (for example: `thread_count=73 exceeds lane threshold 40`),
- keep strip mode active,
- keep all chat-flow metrics unchanged.

## Data contract changes (planned)

Extend `chat_flow` payload with lane-specific precomputed arrays:
- `lanes`: ordered lane metadata (`thread_id`, `title`, `lane_index`, counts).
- `lane_points`: per-message plotting rows:
  - `ts`, `x_epoch`, `lane_index`, `thread_id`, `role`, `switch`, `color_index`.
- `lane_edges`: transition rows:
  - `from_idx`, `to_idx`, `from_lane`, `to_lane`, `switch`, `gap_seconds`.
- `lane_mode_available`: boolean.
- `lane_mode_blockers`: list of reasons when unavailable.

Keep existing `waterfall` array for strip mode compatibility.

## Accessibility and interaction

- keyboard-focusable nodes/connectors where feasible,
- non-color cues for switch and role,
- tooltip text mirrors current strip detail text.

Minimum interactions:
- hover highlight for lane/thread,
- click thread in legend to isolate/focus,
- reset filter action.

## Test/acceptance criteria

- lane mode renders deterministic layout for fixed input.
- auto mode chooses lane/strip correctly at thresholds.
- switch connectors match computed `switch_count`.
- same totals/metrics regardless of selected visual mode.
- fallback message appears when lane mode is blocked by density.

## Rollout

1. Payload support (`chat_flow.lanes/lane_points/lane_edges`).
2. HTML renderer adds mode switch and lane canvas/SVG.
3. Auto-mode thresholds + fallback messaging.
4. Tests (payload + render + mode selection).
