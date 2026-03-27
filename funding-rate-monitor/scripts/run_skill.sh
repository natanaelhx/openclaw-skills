#!/bin/bash
# Entrypoint da skill funding-rate-monitor
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect Python
if command -v py &>/dev/null; then
  PYTHON="py"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
else
  PYTHON="python"
fi

# Install dependencies if missing
$PYTHON -c "import requests, pandas, numpy, tabulate" 2>/dev/null || \
  $PYTHON -m pip install requests pandas numpy tabulate -q

mkdir -p ~/funding_backtest/{data,reports}
$PYTHON "$SCRIPT_DIR/funding_monitor.py" "$@"
