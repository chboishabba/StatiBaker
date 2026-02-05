import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone


def _run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip() or "command failed"
        raise RuntimeError(msg)
    return result.stdout


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_battery(output):
    level = None
    charging = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("level:"):
            try:
                level = int(line.split(":", 1)[1].strip())
            except ValueError:
                level = None
        if line.startswith("status:"):
            status = line.split(":", 1)[1].strip()
            charging = status in {"2", "4", "5", "charging", "full"}
        if line.startswith("AC powered:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in {"true", "false"}:
                charging = value == "true"
        if line.startswith("USB powered:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in {"true", "false"}:
                charging = value == "true"
    return level, charging


def _parse_screen(output):
    screen = "unknown"
    interactive = None
    for line in output.splitlines():
        if "Display Power" in line and "state=" in line:
            match = re.search(r"state=([A-Z_]+)", line)
            if match:
                screen = "on" if match.group(1) in {"ON", "DOZE"} else "off"
        if "mInteractive=" in line:
            match = re.search(r"mInteractive=(true|false)", line)
            if match:
                interactive = match.group(1) == "true"
    return screen, interactive


def _parse_network(output):
    output = output.lower()
    if "wifi" in output and "connected" in output:
        return "wifi"
    if "mobile" in output and "connected" in output:
        return "mobile"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Poll minimal Android status via adb.")
    parser.add_argument("--device", help="ADB device serial")
    parser.add_argument("--output", help="Write JSONL to file (default stdout)")
    args = parser.parse_args()

    base = ["adb"]
    if args.device:
        base += ["-s", args.device]

    try:
        serial = _run(base + ["get-serialno"]).strip()
        battery_out = _run(base + ["shell", "dumpsys", "battery"])
        power_out = _run(base + ["shell", "dumpsys", "power"])
        conn_out = _run(base + ["shell", "dumpsys", "connectivity"])

        level, charging = _parse_battery(battery_out)
        screen, interactive = _parse_screen(power_out)
        network = _parse_network(conn_out)

        record = {
            "ts": _now_iso(),
            "signal": "mobile_status",
            "source": "adb",
            "device": serial,
            "battery": {"level": level, "charging": charging},
            "screen": screen,
            "interactive": interactive,
            "network": network,
        }

        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        else:
            sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")
    except (RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
