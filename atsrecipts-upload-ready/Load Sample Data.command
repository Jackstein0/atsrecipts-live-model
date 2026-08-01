#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Loading sample data..."
echo
bash scripts/load_sample_data.sh
echo
PYTHONPATH=src python3 -m run_totals_model.cli status
echo
read -r -p "Press Enter to close this window..."

