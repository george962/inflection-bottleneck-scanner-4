#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f ".venv/bin/activate" ]]; then source .venv/bin/activate; fi
inflection-scanner research --deep 100 --research-count 20 --top 30
