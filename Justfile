set shell := ["bash", "-lc"]

test:
    python -m unittest discover -s tests

sessionize:
    python -m sb.activity.sessionize tests/fixtures/snapshots.json --output /tmp/activity_ledger.json --config SESSIONIZER_CONFIG.json

dashboard date='$(date +%F)':
    python scripts/build_dashboard.py --date {{date}}
