#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PUBLIC_REPORT="${PUBLIC_REPORT:-/Users/jacksteinkoenig/Documents/Codex/2026-07-30/you/outputs/model_b_picks.html}"
LOCAL_REPORT="${LOCAL_REPORT:-data/processed/model_report.html}"
GENERATED_LABEL="$(date '+%Y-%m-%d %H:%M')"

echo "Updating original model board..."
bash scripts/run_today.sh

echo
echo "Training Model B..."
PYTHONPATH=src python3 -m run_totals_model.cli train-market-adjusted \
  --input data/processed/historical_games.csv \
  --model-out data/processed/totals_model_b.json

echo
echo "Pricing Model B..."
PYTHONPATH=src python3 -m run_totals_model.cli price-market-adjusted \
  --model data/processed/totals_model_b.json \
  --input data/processed/today_results.csv \
  --out data/processed/today_results_model_b.csv

echo
echo "Tracking and grading Model B..."
PYTHONPATH=src python3 -m run_totals_model.cli track-picks \
  --results data/processed/today_results_model_b.csv \
  --tracker data/processed/pick_tracker_model_b.csv \
  --min-label lean

PYTHONPATH=src python3 -m run_totals_model.cli grade-picks \
  --tracker data/processed/pick_tracker_model_b.csv \
  --report-out data/processed/pick_tracker_report_model_b.txt

echo
echo "Writing combined HTML reports..."
PYTHONPATH=src python3 -m run_totals_model.combined_report \
  --original data/processed/today_results.csv \
  --model-b data/processed/today_results_model_b.csv \
  --out "$LOCAL_REPORT" \
  --generated-label "$GENERATED_LABEL"

PYTHONPATH=src python3 -m run_totals_model.combined_report \
  --original data/processed/today_results.csv \
  --model-b data/processed/today_results_model_b.csv \
  --out "$PUBLIC_REPORT" \
  --generated-label "$GENERATED_LABEL"

echo
echo "Done."
echo "Combined report: $LOCAL_REPORT"
echo "Clickable report: $PUBLIC_REPORT"
