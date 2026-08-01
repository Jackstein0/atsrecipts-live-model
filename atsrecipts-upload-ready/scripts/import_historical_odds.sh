#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INPUT="${1:-data/raw/historical_totals_template.csv}"

PYTHONPATH=src python3 -m run_totals_model.cli import-historical-odds \
  --input "$INPUT" \
  --out data/raw/historical_totals_imported.csv

PYTHONPATH=src python3 -m run_totals_model.cli merge-historical-odds \
  --historical-games data/processed/historical_games.csv \
  --odds data/raw/historical_totals_imported.csv \
  --out data/processed/historical_games_with_real_odds.csv

PYTHONPATH=src python3 -m run_totals_model.cli backtest \
  --input data/processed/historical_games_with_real_odds.csv \
  --bets-out data/processed/backtest_bets_real_odds.csv \
  --summary-out data/processed/backtest_summary_real_odds.csv \
  --report-out data/processed/backtest_report_real_odds.txt

echo
echo "Imported historical odds and reran backtest."
echo "Report: data/processed/backtest_report_real_odds.txt"

