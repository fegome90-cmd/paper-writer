#!/bin/bash
set -euo pipefail
# Measure paper CLI structural refactoring progress (PR1).
# Primary metric is deterministic (line count) — zero run-to-run variance.

cd "$(dirname "$0")/.."

# --- Primary metric: main.py line count (lower = better) ---
MAIN_LINES=$(wc -l < cli/paper/main.py | tr -d ' ')
echo "METRIC main_py_lines=$MAIN_LINES"

# --- Secondary: module decomposition ---
MODULES=$(ls cli/paper/*.py cli/paper/commands/*.py 2>/dev/null | wc -l | tr -d ' ')
echo "METRIC cli_module_count=$MODULES"

# --- Secondary: fast correctness — cli + project tests ---
RAW=$(uv run pytest tests/cli/ tests/test_cli/ tests/autoresearch/test_multi_project.py -q --no-header --tb=line 2>/dev/null || true)
FAILED=$(echo "$RAW" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' | head -1 || echo 0)
# If no summary line, count F chars in the dot-progress line
if [ "$FAILED" = "0" ]; then
  SUMMARY=$(echo "$RAW" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' | head -1 || echo 0)
  if [ "$SUMMARY" = "0" ]; then
    DOTLINE=$(echo "$RAW" | tr -cd '.F' | head -c 5000)
    FAILED=$(echo "$DOTLINE" | tr -cd 'F' | wc -c | tr -d ' ')
    PASSED=$(echo "$DOTLINE" | tr -cd '.' | wc -c | tr -d ' ')
  else
    PASSED="$SUMMARY"
  fi
else
  PASSED=$(echo "$RAW" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' | head -1 || echo 0)
fi
echo "METRIC test_failures=$FAILED"
echo "METRIC test_passed=$PASSED"

# --- Secondary: import time (ms), budget < 50ms ---
IMPORT_MS=$(python3 -c "
import time
s = time.perf_counter()
import cli.paper.main
elapsed = (time.perf_counter() - s) * 1000
print(f'{elapsed:.0f}')
" 2>/dev/null || echo 999)
echo "METRIC import_time_ms=$IMPORT_MS"

# --- Secondary: lint errors on cli/paper/ (new files must stay clean) ---
LINT=$(uv run ruff check cli/paper/ 2>/dev/null | grep -c '^[A-Za-z_/].*\.py:' || echo 0)
echo "METRIC lint_errors_cli=$LINT"
