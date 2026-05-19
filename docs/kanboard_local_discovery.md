# Local Kanboard Discovery (Safe Surface)

Date: 2026-05-19

## Scope and guardrails

- Read-only local discovery only.
- No Kanboard mutations.
- No secret values emitted from config or env.

## Local findings

- Installation shape: Arch package install (`local/kanboard 1.2.47-1`).
- Service shape:
  - `kanboard.service` exists and is a oneshot cron runner (`cli cronjob`).
  - `kanboard.timer` exists and is configured as `OnCalendar=daily`.
  - No evidence that this service unit itself exposes HTTP.
- Container shape: no running Kanboard container detected.
- Filesystem shape:
  - Webapp root: `/usr/share/webapps/kanboard`
  - Config root: `/etc/webapps/kanboard`
  - JSON-RPC entrypoint file: `/usr/share/webapps/kanboard/jsonrpc.php`
- Reachability probe (localhost):
  - No listener observed on `127.0.0.1` ports `80`, `8080`, or `8000` at discovery time.

## URL and endpoint assumptions

Because no local listener was reachable during discovery, endpoint assumptions remain configuration-derived:

- If deployed at server root: `http://<host>/jsonrpc.php`
- If deployed under subdirectory (`/kanboard`): `http://<host>/kanboard/jsonrpc.php`

These match packaged examples in:

- `/etc/webapps/kanboard/kanboard-nginx.conf`
- `/etc/webapps/kanboard/kanboard-nginx-subdir.conf`
- `/etc/webapps/kanboard/kanboard-apache.conf`

## Credential source policy

Use local environment or Kanboard config paths, not hardcoded secrets in repo files:

- Adapter-side template:
  - `StatiBaker/configs/kanboard_adapter.env.template`
- Kanboard config path:
  - `/etc/webapps/kanboard/config.php`
- Relevant config/env key families (names only):
  - `DB_USERNAME`, `DB_PASSWORD`
  - `API_AUTHENTICATION_HEADER`
  - `API_AUTHENTICATION_TOKEN` (read by Kanboard middleware from env)

## Repeatable safe probe

Run:

```bash
python3 StatiBaker/scripts/discover_local_kanboard.py
```

This emits a non-secret JSON summary with:

- service/package/container shape
- reachable local base URLs
- endpoint assumptions
- credential key locations (names only)
