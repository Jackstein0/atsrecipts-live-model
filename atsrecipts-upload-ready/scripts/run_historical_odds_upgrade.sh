#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

if [ -z "${THE_ODDS_API_KEY:-}" ] && [ -f "PASTE_API_KEY_HERE.txt" ]; then
  API_KEY_FROM_FILE="$(grep '^THE_ODDS_API_KEY=' PASTE_API_KEY_HERE.txt | tail -n 1 | cut -d= -f2-)"
  if [ -n "$API_KEY_FROM_FILE" ]; then
    export THE_ODDS_API_KEY="$API_KEY_FROM_FILE"
  fi
fi

echo "Testing historical odds access..."
PYTHONPATH=src python3 -m run_totals_model.cli historical-odds-access

echo
echo "Fetching recent historical totals..."
PYTHONPATH=src python3 -m run_totals_model.cli fetch-historical-odds \
  --max-days "${MAX_DAYS:-7}" \
  --out data/raw/historical_totals.csv

echo
echo "Merging historical odds into training file..."
PYTHONPATH=src python3 -m run_totals_model.cli merge-historical-odds \
  --historical-games data/processed/historical_games.csv \
  --odds data/raw/historical_totals.csv \
  --out data/processed/historical_games_with_real_odds.csv

echo
echo "Running backtest on merged file..."
PYTHONPATH=src python3 -m run_totals_model.cli backtest \
  --input data/processed/historical_games_with_real_odds.csv \
  --bets-out data/processed/backtest_bets_real_odds.csv \
  --summary-out data/processed/backtest_summary_real_odds.csv \
  --report-out data/processed/backtest_report_real_odds.txt

echo
echo "Historical odds upgrade complete."
echo "Report: data/processed/backtest_report_real_odds.txt"

