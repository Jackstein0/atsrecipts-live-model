#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHONPATH=src python3 -m run_totals_model.cli backtest \
  --input data/processed/historical_games.csv \
  --bets-out data/processed/backtest_bets.csv \
  --summary-out data/processed/backtest_summary.csv \
  --report-out data/processed/backtest_report.txt

echo
echo "Backtest report:"
cat data/processed/backtest_report.txt

