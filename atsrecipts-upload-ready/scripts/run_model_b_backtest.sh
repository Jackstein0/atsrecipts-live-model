#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHONPATH=src python3 -m run_totals_model.cli backtest-market-adjusted \
  --input data/processed/historical_games.csv \
  --bets-out data/processed/backtest_bets_model_b.csv \
  --summary-out data/processed/backtest_summary_model_b.csv \
  --report-out data/processed/backtest_report_model_b.txt

echo
echo "Model B backtest report:"
cat data/processed/backtest_report_model_b.txt
