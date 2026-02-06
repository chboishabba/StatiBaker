# Android Status Contract (Design-Only)

## Purpose
Define coarse mobile status signals without app/content leakage.

## Inputs
- ADB / Termux / Wazuh agent snapshots.

## Outputs
- JSONL records in `logs/mobile/YYYY-MM-DD.jsonl`.

## Allowed fields
- `ts`
- `signal` = `mobile_status`
- `source` = `adb` | `termux` | `wazuh`
- `device` (stable device ID)
- `battery` (level, charging)
- `screen` (on/off)
- `interactive` (true/false)
- `network` (wifi/cell/offline)

## Prohibited fields
- App names, notifications, message content.
- GPS coordinates unless explicitly policy-gated.

## Example
```json
{"ts":"2026-02-05T15:20:00Z","signal":"mobile_status","source":"adb","device":"R58M123ABC","battery":{"level":42,"charging":true},"screen":"off","interactive":false,"network":"wifi"}
```
