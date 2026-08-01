#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Running today's MLB totals board..."
echo
bash scripts/run_today.sh
echo
read -r -p "Press Enter to close this window..."

