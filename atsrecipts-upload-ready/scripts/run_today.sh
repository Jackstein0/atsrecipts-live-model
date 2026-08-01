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

PYTHONPATH=src python3 -m run_totals_model.cli status
echo

if [ -f "data/processed/today_results.csv" ]; then
  echo "Archiving previous report..."
  PYTHONPATH=src python3 -m run_totals_model.cli archive-current
  echo
fi

FEATURES="${FEATURES:-data/processed/today_features.csv}"
MODEL="${MODEL:-data/processed/totals_model.json}"
TRAINING="${TRAINING:-data/processed/historical_games.csv}"
BOARD="${BOARD:-data/processed/today_board.csv}"
RESULTS="${RESULTS:-data/processed/today_results.csv}"
RAW_JSON="${RAW_JSON:-data/raw/today_odds.json}"
RAW_SCHEDULE_JSON="${RAW_SCHEDULE_JSON:-data/raw/today_schedule.json}"
TEAM_METRICS="${TEAM_METRICS:-data/source/team_metrics.csv}"
STARTER_METRICS="${STARTER_METRICS:-data/source/starter_metrics.csv}"
BULLPEN_METRICS="${BULLPEN_METRICS:-data/source/bullpen_metrics.csv}"
PARK_METRICS="${PARK_METRICS:-data/source/park_metrics.csv}"
WEATHER_METRICS="${WEATHER_METRICS:-data/source/weather_metrics.csv}"

echo "Updating real MLB source data..."
PYTHONPATH=src python3 -m run_totals_model.cli update-real-data \
  --team-metrics "$TEAM_METRICS" \
  --starter-metrics "$STARTER_METRICS" \
  --bullpen-metrics "$BULLPEN_METRICS" \
  --park-metrics "$PARK_METRICS" \
  --weather-metrics "$WEATHER_METRICS" \
  --historical-games "$TRAINING" \
  --raw-dir data/raw
echo

if [ -f "data/fangraphs/team_batting.csv" ] || [ -f "data/fangraphs/starters.csv" ] || [ -f "data/fangraphs/bullpen.csv" ]; then
  echo "Importing FanGraphs exports..."
  PYTHONPATH=src python3 -m run_totals_model.cli import-fangraphs
  echo
fi

echo "Updating weather..."
PYTHONPATH=src python3 -m run_totals_model.cli update-weather \
  --out "$WEATHER_METRICS" \
  --raw-schedule-json "$RAW_SCHEDULE_JSON"
echo

PYTHONPATH=src python3 -m run_totals_model.cli train \
  --input "$TRAINING" \
  --model-out "$MODEL"

for source_file in "$TEAM_METRICS" "$STARTER_METRICS" "$BULLPEN_METRICS" "$PARK_METRICS"; do
  if [ ! -f "$source_file" ]; then
    echo "Missing source metrics file: $source_file"
    echo "Run: PYTHONPATH=src python3 -m run_totals_model.cli init-source-csvs"
    echo "Then fill the CSVs from your FanGraphs/export data."
    exit 1
  fi
done

WEATHER_ARGS=()
if [ -f "$WEATHER_METRICS" ]; then
  WEATHER_ARGS=(--weather-metrics "$WEATHER_METRICS")
fi

PYTHONPATH=src python3 -m run_totals_model.cli features-today \
  --out "$FEATURES" \
  --team-metrics "$TEAM_METRICS" \
  --starter-metrics "$STARTER_METRICS" \
  --bullpen-metrics "$BULLPEN_METRICS" \
  --park-metrics "$PARK_METRICS" \
  --raw-schedule-json "$RAW_SCHEDULE_JSON" \
  "${WEATHER_ARGS[@]}"

PYTHONPATH=src python3 -m run_totals_model.cli odds-current \
  --features "$FEATURES" \
  --out "$BOARD" \
  --raw-json "$RAW_JSON"

PYTHONPATH=src python3 -m run_totals_model.cli price \
  --model "$MODEL" \
  --input "$BOARD" \
  --out "$RESULTS" \
  --preserve-existing

PYTHONPATH=src python3 -m run_totals_model.cli track-picks \
  --results "$RESULTS" \
  --tracker data/processed/pick_tracker.csv \
  --min-label lean

PYTHONPATH=src python3 -m run_totals_model.cli grade-picks \
  --tracker data/processed/pick_tracker.csv \
  --report-out data/processed/pick_tracker_report.txt

PYTHONPATH=src python3 -m run_totals_model.cli report-today \
  --results "$RESULTS" \
  --out data/processed/today_report.html

PYTHONPATH=src python3 -m run_totals_model.cli report-data \
  --out data/processed/data_audit.html

echo
echo "Done. Results were saved to: $RESULTS"
echo "Readable report: data/processed/today_report.html"
echo "Data audit: data/processed/data_audit.html"
echo "Pick tracker: data/processed/pick_tracker.csv"
