#!/usr/bin/env python
import argparse
import json

from sb import query


def main():
    parser = argparse.ArgumentParser(description="Read-only SB query surface (CLI).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    parser.add_argument("--base", help="Optional base directory for safe reads")

    activity = sub.add_parser("activity-events", help="List activity events")
    activity.add_argument("--ledger", required=True)

    carryover = sub.add_parser("carryover", help="Carryover summary")
    carryover.add_argument("--state", required=True)

    prov = sub.add_parser("provenance", help="Provenance summary")
    prov.add_argument("--state", required=True)
    prov.add_argument("--ledger")
    prov.add_argument("--drift")

    commitments = sub.add_parser("commitments", help="Commitment feed from dashboard payload")
    commitments.add_argument("--dashboard", required=True)

    candidates = sub.add_parser("completion-candidates", help="Completion candidates from dashboard payload")
    candidates.add_argument("--dashboard", required=True)

    args = parser.parse_args()

    if args.cmd == "activity-events":
        payload = query.list_activity_events(args.ledger, base_dir=args.base)
    elif args.cmd == "carryover":
        payload = query.carryover_summary(args.state, base_dir=args.base)
    elif args.cmd == "commitments":
        payload = query.commitment_feed(args.dashboard, base_dir=args.base)
    elif args.cmd == "completion-candidates":
        payload = query.completion_candidates(args.dashboard, base_dir=args.base)
    else:
        payload = query.provenance(
            args.state,
            ledger_path=args.ledger,
            drift_path=args.drift,
            base_dir=args.base,
        )

    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
