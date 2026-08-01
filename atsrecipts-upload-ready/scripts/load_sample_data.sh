#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p data/source data/processed data/raw

cp examples/source/team_metrics.csv data/source/team_metrics.csv
cp examples/source/starter_metrics.csv data/source/starter_metrics.csv
cp examples/source/bullpen_metrics.csv data/source/bullpen_metrics.csv
cp examples/source/park_metrics.csv data/source/park_metrics.csv
cp examples/source/weather_metrics.csv data/source/weather_metrics.csv
cp examples/sample_games.csv data/processed/historical_games.csv

echo "Loaded sample metric CSVs and sample historical training data."
echo
echo "These files are for testing the workflow only:"
echo "- data/source/team_metrics.csv"
echo "- data/source/starter_metrics.csv"
echo "- data/source/bullpen_metrics.csv"
echo "- data/source/park_metrics.csv"
echo "- data/source/weather_metrics.csv"
echo "- data/processed/historical_games.csv"

