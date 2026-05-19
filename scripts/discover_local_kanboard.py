#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


KANBOARD_CONFIG_DIR = Path("/etc/webapps/kanboard")
KANBOARD_CONFIG_FILE = KANBOARD_CONFIG_DIR / "config.php"
KANBOARD_WEBAPP_DIR = Path("/usr/share/webapps/kanboard")
KANBOARD_SYSTEMD_UNIT = Path("/usr/lib/systemd/system/kanboard.service")
KANBOARD_TIMER_UNIT = Path("/usr/lib/systemd/system/kanboard.timer")


def _run(cmd: list[str]) -> tuple[int | None, str]:
    if not cmd or shutil.which(cmd[0]) is None:
        return None, ""
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return proc.returncode, (proc.stdout or "").strip()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _parse_define_names(config_text: str) -> list[str]:
    names = sorted(set(re.findall(r"define\('([^']+)'", config_text)))
    return names


def _open_http(url: str) -> tuple[bool, int | None]:
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=1.5) as resp:
            return True, int(resp.getcode())
    except URLError:
        return False, None
    except Exception:
        return False, None


def _infer_prefixes() -> list[str]:
    prefixes = {"/"}
    nginx_subdir = _read_text(KANBOARD_CONFIG_DIR / "kanboard-nginx-subdir.conf")
    apache_conf = _read_text(KANBOARD_CONFIG_DIR / "kanboard-apache.conf")
    if "location /kanboard" in nginx_subdir or "Alias /kanboard" in apache_conf:
        prefixes.add("/kanboard")
    return sorted(prefixes)


def _probe_base_urls() -> dict[str, object]:
    prefixes = _infer_prefixes()
    probe_ports = [80, 8080, 8000]
    candidates: list[str] = []
    for port in probe_ports:
        for prefix in prefixes:
            if port == 80:
                candidates.append(f"http://127.0.0.1{prefix}")
            else:
                candidates.append(f"http://127.0.0.1:{port}{prefix}")

    reachable: list[dict[str, object]] = []
    for url in candidates:
        ok, code = _open_http(url)
        if ok:
            reachable.append({"base_url": url, "http_status": code})

    endpoint_assumptions = [
        {"endpoint": f"{url.rstrip('/')}/jsonrpc.php", "derived_from": "reachable_base_url"}
        for url in (row["base_url"] for row in reachable)
    ]
    if not endpoint_assumptions:
        for prefix in prefixes:
            endpoint_assumptions.append(
                {
                    "endpoint": f"http://127.0.0.1{prefix.rstrip('/')}/jsonrpc.php",
                    "derived_from": "packaged_webserver_examples_not_currently_reachable",
                }
            )
    return {
        "prefixes": prefixes,
        "reachable_base_urls": reachable,
        "endpoint_assumptions": endpoint_assumptions,
    }


def _service_shape() -> dict[str, object]:
    unit_text = _read_text(KANBOARD_SYSTEMD_UNIT)
    timer_text = _read_text(KANBOARD_TIMER_UNIT)

    _, docker_ps = _run(["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Ports}}"])
    container_rows = [
        line for line in docker_ps.splitlines() if "kanboard" in line.lower()
    ]
    if container_rows:
        shape = "container"
    elif KANBOARD_WEBAPP_DIR.exists() or KANBOARD_CONFIG_FILE.exists():
        shape = "system-package-webapp"
    else:
        shape = "unknown"

    _, status_text = _run(["systemctl", "status", "kanboard.service", "--no-pager", "--lines=6"])
    is_active = "Active: active" in status_text

    return {
        "shape": shape,
        "webapp_dir": str(KANBOARD_WEBAPP_DIR) if KANBOARD_WEBAPP_DIR.exists() else None,
        "config_file": str(KANBOARD_CONFIG_FILE) if KANBOARD_CONFIG_FILE.exists() else None,
        "has_kanboard_service_unit": KANBOARD_SYSTEMD_UNIT.exists(),
        "has_kanboard_timer_unit": KANBOARD_TIMER_UNIT.exists(),
        "kanboard_service_active": is_active,
        "kanboard_service_summary": (
            "cron-only oneshot" if "ExecStart=/usr/share/webapps/kanboard/cli cronjob" in unit_text else "unknown"
        ),
        "kanboard_timer_summary": (
            "daily cron trigger" if "OnCalendar=daily" in timer_text else "unknown"
        ),
        "container_rows": container_rows,
    }


def _package_shape() -> dict[str, object]:
    package_rows: list[str] = []
    for cmd in (
        ["pacman", "-Q", "kanboard"],
        ["dpkg-query", "-W", "kanboard"],
        ["apk", "info", "kanboard"],
    ):
        code, out = _run(cmd)
        if code == 0 and out:
            package_rows.extend(out.splitlines())
    return {
        "detected_packages": package_rows,
    }


def _credential_surface() -> dict[str, object]:
    config_text = _read_text(KANBOARD_CONFIG_FILE)
    define_names = _parse_define_names(config_text)
    # Expose only config key names and recommended adapter env keys, never values.
    return {
        "config_path": str(KANBOARD_CONFIG_FILE),
        "config_keys_detected_count": len(define_names),
        "selected_config_keys": [
            key
            for key in (
                "DB_DRIVER",
                "DB_USERNAME",
                "DB_PASSWORD",
                "API_AUTHENTICATION_HEADER",
                "MAIL_SMTP_USERNAME",
                "MAIL_SMTP_PASSWORD",
            )
            if key in define_names
        ],
        "adapter_env_recommendations": [
            "KANBOARD_BASE_URL",
            "KANBOARD_JSONRPC_ENDPOINT",
            "KANBOARD_PROJECT_ID",
            "KANBOARD_API_USER",
            "KANBOARD_API_TOKEN",
            "KANBOARD_API_AUTH_HEADER",
        ],
        "upstream_env_observed_in_code": [
            "DB_USERNAME",
            "DB_PASSWORD",
            "API_AUTHENTICATION_HEADER",
            "API_AUTHENTICATION_TOKEN",
        ],
    }


def discover_local_kanboard() -> dict[str, object]:
    return {
        "schema_version": "stati_baker.kanboard_local_discovery.v0_1",
        "discovered_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "authority_boundary": {
            "read_only": True,
            "secrets_emitted": False,
            "kanboard_mutation_attempted": False,
        },
        "service": _service_shape(),
        "package": _package_shape(),
        "network": _probe_base_urls(),
        "credentials": _credential_surface(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover local Kanboard installation shape without exposing secrets."
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of pretty JSON.",
    )
    args = parser.parse_args()
    payload = discover_local_kanboard()
    if args.compact:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
