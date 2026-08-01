#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Setting up the MLB run totals tool..."
echo

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo "Created .env"
else
  echo ".env already exists"
fi

PYTHONPATH=src python3 -m run_totals_model.cli init-source-csvs \
  --team-metrics data/source/team_metrics.csv \
  --starter-metrics data/source/starter_metrics.csv \
  --bullpen-metrics data/source/bullpen_metrics.csv \
  --park-metrics data/source/park_metrics.csv \
  --weather-metrics data/source/weather_metrics.csv

mkdir -p data/processed data/raw

echo
echo "Setup is done."
echo
PYTHONPATH=src python3 -m run_totals_model.cli status
echo
echo "Next:"
echo "1. Put your Odds API key in .env"
echo "2. Fill the CSV files in data/source"
echo "3. Add historical training data at data/processed/historical_games.csv"
echo "4. Double-click Run Today.command"
echo
read -r -p "Press Enter to close this window..."
