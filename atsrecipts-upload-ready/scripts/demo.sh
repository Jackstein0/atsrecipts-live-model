#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHONPATH=src python3 -m run_totals_model.cli train \
  --input examples/sample_games.csv \
  --model-out data/processed/sample_model.json

PYTHONPATH=src python3 -m run_totals_model.cli features-today \
  --schedule-json examples/mlb_schedule_sample.json \
  --team-metrics examples/source/team_metrics.csv \
  --starter-metrics examples/source/starter_metrics.csv \
  --bullpen-metrics examples/source/bullpen_metrics.csv \
  --park-metrics examples/source/park_metrics.csv \
  --weather-metrics examples/source/weather_metrics.csv \
  --out data/processed/sample_today_features.csv

PYTHONPATH=src python3 -m run_totals_model.cli odds-from-json \
  --input examples/the_odds_api_totals_sample.json \
  --features data/processed/sample_today_features.csv \
  --out data/processed/sample_merged_board.csv

PYTHONPATH=src python3 -m run_totals_model.cli price \
  --model data/processed/sample_model.json \
  --input data/processed/sample_merged_board.csv \
  --out data/processed/sample_results.csv

echo
echo "Demo complete. Results were saved to: data/processed/sample_results.csv"
