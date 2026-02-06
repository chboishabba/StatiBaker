# Observed Signals (Append-Only)

SB treats capture as **observed signals**, not memory. Signals explain activity
and support segmentation; they never define meaning.

## Principles
- Append-only JSONL; no rewrites.
- Structural signals only; no content capture.
- Deterministic sessionization remains SB authority.
- ITIR may annotate but must not re-segment time.

## Signal streams

### 1) Screen / app state (evidence)
Source: OpenRecall-style snapshots.
Schema: see `STATE_SCHEMA.json` `snapshots[]`.
Notes:
- Screenshots and window/app metadata only.
- No OCR unless explicitly policy-gated.

### 2) Input activity (structure, not content)
Path: `logs/input/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T11:32:14Z","signal":"input","focus_app":"org.gnome.Terminal","keys":{"text":0,"nav":12,"control":4},"modifiers":{"ctrl":3,"alt":1,"super":0},"mouse":{"moves":140,"clicks":3,"scroll":1}}
```

Notes:
- No characters, passwords, or clipboard contents.
- Counts only (bursts, cadence, transitions).

### 3) System / journal events (structured)
Path: `logs/system/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T12:04:01Z","signal":"system","event":"network_down","iface":"wlan0"}
```

Notes:
- Structured events only (service start/stop, suspend/resume, device attach/detach).
- No raw journal text spam.

### 3b) Wazuh lifecycle events (structured)
Path: `logs/system/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T12:04:01Z","signal":"system","event":"wazuh_lifecycle","kind":"network_down","source":"wazuh","agent":"host-01"}
```

Notes:
- Lifecycle only (boot, suspend/resume, network up/down, service restarts).
- Wazuh alert semantics are ignored; only structured lifecycle events are kept.

### 4) Power and lifecycle signals
Path: `logs/power/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T09:14:02Z","signal":"power_state","state":"suspend"}
```

Notes:
- Suspend/resume, lid close/open, AC/battery transitions, thermal throttling.
- These explain gaps without attributing intent.

### 5) Filesystem metadata (no content)
Path: `logs/fs/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T10:22:01Z","signal":"fs_meta","dir_hash":"sha256:...","changes":42,"scanned_files":2000}
```

Notes:
- Never store paths verbatim outside SB; hash + classify.
- Metadata only (mtime/ctime changes, coarse open/close counts).

### 6) Network shape (no endpoints)
Path: `logs/net/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T11:03:30Z","signal":"net_shape","bytes_in":1200000,"bytes_out":220000,"connections":18,"protocols":{"tcp":16,"udp":2}}
```

Notes:
- No hostnames, IPs, or URLs; only shape/volume.

### 7) Error surfaces (counts only)
Path: `logs/errors/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T12:15:44Z","signal":"error_surface","kind":"exit_nonzero","count":3}
```

Notes:
- Counts only (exit codes, restarts, kernel warnings, GPU resets).

### 8) Agent / automation heartbeats
Path: `logs/agents/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T12:30:00Z","signal":"agent_heartbeat","agent":"sb-indexer","state":"busy","task_id":"task-17"}
```

Notes:
- Distinguish human vs automation activity.

### 9) Time-anchor beacons
Path: `logs/anchors/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T13:00:00Z","signal":"anchor","kind":"calendar_reminder"}
```

Notes:
- No notification text; type only.

### 10) Environment context (optional)
Path: `logs/env/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T06:00:00Z","signal":"env","kind":"timezone","value":"UTC-05"}
```

Notes:
- Coarse, low-frequency signals only (timezone, day/night).

### 11) Consent and redaction events
Path: `logs/consent/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T14:10:00Z","signal":"consent","state":"capture_disabled","scope":"screen"}
```

Notes:
- Absence of consent is a first-class event.

### 12) CLI activity (optional)
Path: `logs/cli/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T12:11:09Z","signal":"cli","cmd":"git","cwd_hash":"sha256:...","exit":1,"duration_ms":430}
```

Notes:
- Binary name only; no arguments or env vars unless explicitly whitelisted.

### 13) Mobile status (ADB/Termux/KDE Connect)
Path: `logs/mobile/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T15:20:00Z","signal":"mobile_status","source":"adb","device":"R58M123ABC","battery":{"level":42,"charging":true},"screen":"off","interactive":false,"network":"wifi"}
```

Notes:
- Coarse status only; no app names or content.

### 14) System facts (osquery)
Path: `logs/system_facts/YYYY-MM-DD.jsonl`

Example:
```json
{"ts":"2026-02-05T16:00:00Z","signal":"system_fact","source":"osquery","name":"uptime","row":{"total_seconds":"123456"}}
```

Notes:
- Curated queries only; avoid raw logs and free text.
- Treat as facts snapshots, not event streams.

#### osquery priorities (default order)
1. Uptime
2. System info (OS version/build)
3. Memory info (total/free)
4. CPU info (model/cores)
5. Mounts/disk capacity (no paths unless hashed)
6. Interface state (no raw IPs unless hashed)

#### Avoid by default
- `process_events` / `processes` full listings (noisy, identity-rich)
- `file_events` / audit-style tables unless aggressively filtered
- Any table that includes raw command lines, file paths, or user names without hashing

### 15) Metrics summaries (observability)
Path: `logs/metrics/YYYY-MM-DD.jsonl`

Example:
```json
{"t_start":"2026-02-05T10:00:00Z","t_end":"2026-02-05T11:00:00Z","signal":"metric_summary","metric":"node_cpu_seconds_total","summary":{"mean":0.82,"p95":0.97}}
```

Notes:
- Numeric summaries only; no semantic labels or content.
- Intended as supporting signals for segmentation confidence.
- Source: Prometheus (including Graphite exporter metrics). Grafana remains a
  visualization layer only.
- InfluxDB (Home Assistant) may be added once credentials and live data are confirmed.

## Non-captured data (hard no)
- Keystroke content or passwords
- Clipboard contents (unless explicit opt-in)
- Raw command arguments and env vars
- OCR text without policy gate and provenance
- Any semantic labels like "coding" or "thinking"

## Invariant
Signals explain activity; they never define meaning.

## Sessionization vs confidence
- Session boundaries may use hard signals: suspend/resume, lid close/open, focus change, display change.
- Confidence scoring may use supporting signals: input intensity, error surfaces, network shape, power throttling.
- No signal may infer intent or semantic labels.
