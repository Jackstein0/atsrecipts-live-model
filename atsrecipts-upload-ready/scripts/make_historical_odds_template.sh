#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHONPATH=src python3 -m run_totals_model.cli historical-odds-template \
  --historical-games data/processed/historical_games.csv \
  --out data/raw/historical_totals_template.csv

echo
echo "Template created at: data/raw/historical_totals_template.csv"
echo "Fill market_total, over_odds, and under_odds, then run:"
echo
echo "PYTHONPATH=src python3 -m run_totals_model.cli merge-historical-odds --odds data/raw/historical_totals_template.csv"

