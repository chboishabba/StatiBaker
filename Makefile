.PHONY: test sessionize dashboard

DATE ?= $(shell date +%F)

test:
	python -m unittest discover -s tests

sessionize:
	python -m sb.activity.sessionize tests/fixtures/snapshots.json --output /tmp/activity_ledger.json --config SESSIONIZER_CONFIG.json

dashboard:
	python scripts/build_dashboard.py --date $(DATE)
