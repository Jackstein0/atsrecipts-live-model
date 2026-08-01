#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Running demo with sample data..."
echo
bash scripts/demo.sh
echo
read -r -p "Press Enter to close this window..."

