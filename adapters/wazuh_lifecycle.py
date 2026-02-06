import argparse
import json
import sys


def _norm_text(*parts):
    chunks = []
    for part in parts:
        if not part:
            continue
        if isinstance(part, list):
            chunks.extend([str(item).lower() for item in part])
        else:
            chunks.append(str(part).lower())
    return " ".join(chunks)


def _classify_event(payload):
    rule = payload.get("rule", {}) if isinstance(payload, dict) else {}
    groups = rule.get("groups", [])
    description = rule.get("description", "")
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    message = payload.get("full_log") or payload.get("message") or data.get("message")

    text = _norm_text(groups, description, message)

    if "network" in text and any(word in text for word in ["down", "disconnect", "lost"]):
        return "network_down"
    if "network" in text and any(word in text for word in ["up", "connect", "restored"]):
        return "network_up"
    if any(word in text for word in ["boot", "startup", "reboot"]):
        return "boot"
    if any(word in text for word in ["shutdown", "poweroff", "halt"]):
        return "shutdown"
    if any(word in text for word in ["suspend", "sleep"]):
        return "suspend"
    if any(word in text for word in ["resume", "wakeup", "wake up"]):
        return "resume"
    if "service" in text and "restart" in text:
        return "service_restart"

    return None


def _extract_ts(payload):
    for key in ["timestamp", "time", "ts"]:
        if key in payload:
            return payload.get(key)
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    return data.get("timestamp")


def _extract_agent(payload):
    agent = payload.get("agent") if isinstance(payload, dict) else None
    if isinstance(agent, dict):
        return agent.get("name") or agent.get("id")
    return payload.get("agent_name") or payload.get("agent_id")


def convert_events(lines):
    output = []
    for line in lines:
        if not line.strip():
            continue
        payload = json.loads(line)
        kind = _classify_event(payload)
        if not kind:
            continue
        ts = _extract_ts(payload)
        if not ts:
            continue
        record = {
            "ts": ts,
            "signal": "system",
            "event": "wazuh_lifecycle",
            "kind": kind,
            "source": "wazuh",
        }
        agent = _extract_agent(payload)
        if agent:
            record["agent"] = agent
        output.append(record)
    return output


def main():
    parser = argparse.ArgumentParser(description="Extract Wazuh lifecycle events to SB JSONL.")
    parser.add_argument("--input", required=True, help="Wazuh alert JSONL input")
    parser.add_argument("--output", help="Write JSONL to file (default stdout)")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as handle:
        records = convert_events(handle)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
    else:
        for record in records:
            sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
