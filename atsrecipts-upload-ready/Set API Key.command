#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Paste your The Odds API key below."
echo "It will be saved locally in this folder's .env file."
echo
read -r -p "API key: " API_KEY

if [ -z "$API_KEY" ]; then
  echo
  echo "No key entered. Nothing was changed."
  read -r -p "Press Enter to close this window..."
  exit 1
fi

cat > .env <<EOF
THE_ODDS_API_KEY=$API_KEY
EOF

echo
echo "Saved API key to .env"
echo
PYTHONPATH=src python3 -m run_totals_model.cli status
echo
read -r -p "Press Enter to close this window..."

