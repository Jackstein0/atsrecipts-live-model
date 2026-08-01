#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Creating historical odds template..."
echo
bash scripts/make_historical_odds_template.sh
echo
read -r -p "Press Enter to close this window..."

