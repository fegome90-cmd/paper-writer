#!/bin/bash
# ab-test-runner.sh — Execute full A/B test suite for Trifecta extension
# Usage: ./scripts/ab-test-runner.sh [T2|T3|T4|T5|T6|all]
set -euo pipefail

PROVIDER="${AB_PROVIDER:-zai}"
MODEL="${AB_MODEL:-glm-5-turbo}"
TIMEOUT="${AB_TIMEOUT:-300}"
PROJECT="/Users/felipe_gonzalez/Developer/agent_h/trifecta_dope"
RUN_ID="$(date +%Y%m%d-%H%M%S)"

TESTS="${1:-T2 T3 T4 T5 T6}"
RESULTS_DIR="/tmp/ab-test-results"
mkdir -p "$RESULTS_DIR"

echo "=================================================="
echo "  Trifecta A/B Test Suite — Run $RUN_ID"
echo "  Model: $MODEL  Tests: $TESTS"
echo "=================================================="

run_pair() {
    local TID="$1"
    local PROMPT_DIR="/tmp"
    local OUT_A="$RESULTS_DIR/${TID}-agent-a.md"
    local OUT_B="$RESULTS_DIR/${TID}-agent-b.md"

    echo ""
    echo "=== $TID: Launching A/B pair ==="

    # Clean
    rm -f "$OUT_A" "$OUT_B"

    # Agent A (control) — TRIFECTA_DISABLE=1
    TRIFECTA_DISABLE=1 timeout "$TIMEOUT" \
    env PI_LENS_STARTUP_MODE=quick \
    pi --provider "$PROVIDER" --model "$MODEL" \
    --mode json -nc -p @"${PROMPT_DIR}/ab-${TID,,}-prompt-control.txt" \
    > "$RESULTS_DIR/${TID}-output-a.jsonl" 2>/dev/null &
    PID_A=$!

    # Agent B (treatment) — extension active
    (cd "$PROJECT" && timeout "$TIMEOUT" \
    env PI_LENS_STARTUP_MODE=quick \
    pi --provider "$PROVIDER" --model "$MODEL" \
    --mode json -nc -p @"${PROMPT_DIR}/ab-${TID,,}-prompt-treatment.txt" \
    > "$RESULTS_DIR/${TID}-output-b.jsonl" 2>/dev/null) &
    PID_B=$!

    echo "  Agent A PID=$PID_A (TRIFECTA_DISABLE=1)"
    echo "  Agent B PID=$PID_B (extension active)"

    # Wait for both
    SECONDS=0
    while (kill -0 "$PID_A" 2>/dev/null || kill -0 "$PID_B" 2>/dev/null) && [ $SECONDS -lt "$TIMEOUT" ]; do
        sleep 10
        SECONDS=$((SECONDS + 10))
    done

    wait "$PID_A" 2>/dev/null || true; EXIT_A=$?
    wait "$PID_B" 2>/dev/null || true; EXIT_B=$?

    # Copy from agent's write path to results dir (agents write to /tmp/ab-T?-agent-?.md)
    cp "/tmp/ab-${TID,,}-agent-a.md" "$OUT_A" 2>/dev/null || echo "  Agent A: no output"
    cp "/tmp/ab-${TID,,}-agent-b.md" "$OUT_B" 2>/dev/null || echo "  Agent B: no output"

    # Score
    OK_A=0; OK_B=0
    [[ -f "$OUT_A" ]] && [[ $(wc -c < "$OUT_A") -gt 200 ]] && grep -q '## Status:' "$OUT_A" && OK_A=1
    [[ -f "$OUT_B" ]] && [[ $(wc -c < "$OUT_B") -gt 200 ]] && grep -q '## Status:' "$OUT_B" && OK_B=1

    SIZE_A=$(wc -c < "$OUT_A" 2>/dev/null || echo 0)
    SIZE_B=$(wc -c < "$OUT_B" 2>/dev/null || echo 0)
    WORDS_A=$(wc -w < "$OUT_A" 2>/dev/null || echo 0)
    WORDS_B=$(wc -w < "$OUT_B" 2>/dev/null || echo 0)

    echo "  $TID DONE: A=${SIZE_A}B/${WORDS_A}w ok=$OK_A, B=${SIZE_B}B/${WORDS_B}w ok=$OK_B"

    # Write result line
    echo "$TID,$OK_A,$OK_B,$SIZE_A,$SIZE_B,$WORDS_A,$WORDS_B,$SECONDS" >> "$RESULTS_DIR/summary.csv"
}

# Header
echo "test,ok_a,ok_b,size_a,size_b,words_a,words_b,wall_s" > "$RESULTS_DIR/summary.csv"

# Run tests
for T in $TESTS; do
    run_pair "$T"
done

echo ""
echo "=================================================="
echo "  All tests complete. Results in $RESULTS_DIR/"
echo "  Summary:"
cat "$RESULTS_DIR/summary.csv"
echo "=================================================="
