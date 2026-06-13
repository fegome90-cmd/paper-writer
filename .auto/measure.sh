#!/bin/bash
set -euo pipefail
# Measure PR2 progress: exit-code taxonomy migration + output contract.
# Primary metric: count of bare SystemExit(1) calls in cli/paper/ (lower = better).

cd "$(dirname "$0")/.."

# --- Primary metric: SystemExit(1) calls in cli/paper/ (target: migrate to typed exceptions) ---
SYS_EXIT_1=$(grep -rn "raise SystemExit(1)\|sys.exit(1)" cli/paper/ --include='*.py' 2>/dev/null | grep -v __pycache__ | wc -l | tr -d ' ')
echo "METRIC system_exit_1_count=$SYS_EXIT_1"

# --- Secondary: print() calls in cli/paper/ (PR2 migrates to emit_*) ---
PRINT_COUNT=$(grep -rn "print(" cli/paper/ --include='*.py' 2>/dev/null | grep -v __pycache__ | grep -v '"""' | wc -l | tr -d ' ')
echo "METRIC print_calls=$PRINT_COUNT"

# --- Secondary: cli_module_count ---
MODULES=$(ls cli/paper/*.py cli/paper/commands/*.py 2>/dev/null | wc -l | tr -d ' ')
echo "METRIC cli_module_count=$MODULES"

# --- Secondary: fast correctness — cli + project tests ---
# Exclude e2e tests (need Pandoc/real I/O) per AGENTS.md gotcha #4 and
# the -m "not e2e" convention used by CI (commit 80c8083 marked them).
RAW=$(uv run pytest tests/cli/ tests/test_cli/ tests/autoresearch/test_multi_project.py -q --no-header -m "not e2e" --tb=line 2>/dev/null || true)
FAILED=$(echo "$RAW" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' | head -1 || echo 0)
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
