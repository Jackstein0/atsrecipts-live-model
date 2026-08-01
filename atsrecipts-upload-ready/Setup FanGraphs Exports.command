#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Creating FanGraphs export drop-zone files..."
echo
PYTHONPATH=src python3 -m run_totals_model.cli fangraphs-templates
echo
echo "Put your FanGraphs CSV exports here:"
echo "data/fangraphs/team_batting.csv"
echo "data/fangraphs/starters.csv"
echo "data/fangraphs/bullpen.csv"
echo
echo "Then double-click Run Today.command."
echo
read -r -p "Press Enter to close this window..."

