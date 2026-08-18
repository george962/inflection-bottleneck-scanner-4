#!/usr/bin/env bash
set -euo pipefail
inflection-scanner research --deep "${DEEP_CANDIDATES:-180}" --research-count "${RESEARCH_CANDIDATES:-24}" --top 30
python scripts/validate_publish.py --published published --min-reports 5
