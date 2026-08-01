#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Running historical odds upgrade..."
echo
bash scripts/run_historical_odds_upgrade.sh
echo
read -r -p "Press Enter to close this window..."

