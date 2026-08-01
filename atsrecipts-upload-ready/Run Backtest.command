#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Running backtest..."
echo
bash scripts/run_backtest.sh
echo
read -r -p "Press Enter to close this window..."

