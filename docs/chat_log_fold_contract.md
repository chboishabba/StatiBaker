# Chat Log Fold Contract

## Purpose

This note defines how StatiBaker should treat chat logs that contain pasted or
summarized material from other local records.

A chat log is often a conversation record, but it can also be a fold over
terminal logs, Codex tool traces, user notes, transcripts, OCR snippets, and
other observer records. StatiBaker must preserve that distinction so downstream
renderers can recover formatting and provenance without creating a second
canonical store for the same content.

## Core Rule

Chat messages are canonical conversation events. They are not automatically the
canonical source for every artifact-like span inside them.

If a chat message contains pasted terminal output, a copied note, a transcript
fragment, or an OCR-derived excerpt, the correct model is:

- store the chat message once in the chat archive
- store the source event once in its own producer-owned lane
- add a join/backref that says a span of the chat message corresponds to that
  source event
- let renderers use the joined source shape for display when evidence is strong
- never silently replace or mutate the canonical chat text

## Source Families

Expected source families include:

- `chat_archive_message`: canonical conversation message rows
- `codex_history`: local Codex user/session history
- `codex_tui_log`: local Codex TUI/tool-call logs
- `cli_event`: terminal or shell metadata events
- `user_note`: explicit note or planning artifacts
- `transcript`: voice, meeting, or media transcript records
- `ocr_activity`: OCR or screen-capture observer records
- `document_source`: local file/document excerpts

Producer ownership remains with the source family. StatiBaker may observe,
summarize, hash, and reference these records, but it must not promote copied
chat spans into new canonical source records.

## Join Shape

Reference rows or export manifests should use a shape equivalent to:

```json
{
  "contract_version": "chat_source_join_v1",
  "chat_ref": {
    "canonical_thread_id": "thread-id",
    "message_id": "message-id",
    "source_id": "archive-source-id"
  },
  "chat_span": {
    "start_char": 1200,
    "end_char": 2480,
    "start_line": 38,
    "end_line": 53
  },
  "source_ref": {
    "kind": "codex_tui_log",
    "uri": "/home/c/.codex/log/codex-tui.log",
    "event_id": "optional-stable-event-id"
  },
  "join_type": "exact_digest",
  "confidence": "high",
  "render_hint": "terminal_block",
  "evidence": {
    "digest": "sha256:...",
    "timestamp_window": ["2026-05-18T03:00:00Z", "2026-05-18T03:05:00Z"]
  }
}
```

The `uri` should be a local ref or content-addressed ref, not copied source
content. If a source lane is metadata-only, use hashes, IDs, timestamps, and
bounded previews only.

## Join Types

Use the narrowest honest join type:

- `exact_digest`: normalized span digest matches a source event digest
- `near_text`: high-overlap text match, with lossy whitespace or export damage
- `time_window_tool_call`: chat span aligns with a local tool call by time,
  thread/session, role, and command family
- `user_declared`: user explicitly says the span came from a source
- `heuristic_shape`: source-like formatting detected without a matched source

Only `exact_digest`, strong `near_text`, or strong `time_window_tool_call`
should allow renderers to treat a damaged chat span as recovered terminal or
tool output. `heuristic_shape` may justify conservative display repair, but not
source-backed claims.

## Rendering Policy

Renderers may use joins to improve HTML/PDF output:

- terminal-like spans may render as monospaced terminal blocks
- fragmented command/output rows may be reflowed when source evidence supports
  the original layout
- long opaque file links may display as compact labels while preserving targets
- transcript/note excerpts may retain paragraph structure from the source when
  the join is strong

Renderers must keep audit surfaces honest:

- canonical JSON exports preserve the chat archive text
- canonical Markdown exports preserve the chat archive text unless explicitly
  marked as display-only
- HTML/PDF display repairs emit diagnostics and backrefs
- repaired output is presentation, not a replacement source

## StatiBaker Boundary

StatiBaker should store or expose joins as reference-heavy observer data:

- source kind
- source URI or source ID
- message/thread IDs
- span offsets or line ranges
- digest/evidence fields
- confidence and join type
- render hints

StatiBaker should not store:

- full terminal output copied from chat
- full OCR bodies copied from source systems
- screenshots or media bytes
- a second canonical copy of a note/transcript/document excerpt
- inferred source relationships without confidence/evidence labels

## Practical Use

For the Perplexity/GPT/Codex exporter work, this contract means:

- malformed pasted shell output in a chat can be repaired for PDF display when
  joined to local Codex/TUI/CLI records
- if no source record can be joined, use conservative whitespace repair only
- every repair should point back to the canonical message span and, when
  available, to the source log or trace event
- generated bundles remain sidecars over canonical archive rows

This gives the suite a stable rule: store once, join by reference, render with
evidence, and keep source authority visible.
