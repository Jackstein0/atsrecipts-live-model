#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Importing historical odds from data/raw/historical_totals_template.csv..."
echo
bash scripts/import_historical_odds.sh
echo
read -r -p "Press Enter to close this window..."

