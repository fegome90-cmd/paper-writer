#!/usr/bin/env bash
# ab-test-extension.sh — A/B test: same task, with vs without Trifecta context injection.
#
# Usage:
#   ./scripts/ab-test-extension.sh @task-prompt.txt
#   ./scripts/ab-test-extension.sh "Explain how the Oracle handles stale graphs"
#
# Outputs:
#   /tmp/ab-test-agent-a.md  (WITHOUT extension)
#   /tmp/ab-test-agent-b.md  (WITH extension)
#   /tmp/ab-test-result.json (comparison metrics)
#
# Requirements:
#   - pi installed and authenticated
#   - TRIFECTA_DISABLE gate added to 02-trifecta-context-loader.ts
#   - Same model for both agents (controlled via --model flag)

set -euo pipefail

# --- Config ---
TASK="${1:?Usage: $0 @task-prompt.txt | 'inline task'}"
MODEL="${AB_MODEL:-zai/glm-5-turbo}"
PROVIDER="${AB_PROVIDER:-zai}"
TIMEOUT="${AB_TIMEOUT:-600}"
PROJECT_DIR="${AB_PROJECT:-$(pwd)}"
RUN_ID="$(date +%Y%m%d-%H%M%S)"

echo "[AB-TEST] Run ID: $RUN_ID"
echo "[AB-TEST] Model:  $MODEL"
echo "[AB-TEST] Task:   ${TASK:0:80}..."

# --- Resolve task file ---
if [[ "$TASK" == @* ]]; then
	TASK_FILE="${TASK#@}"
	if [[ ! -f "$TASK_FILE" ]]; then
		echo "[AB-TEST] ERROR: Task file not found: $TASK_FILE"
		exit 1
	fi
else
	TASK_FILE="/tmp/ab-test-task-$RUN_ID.txt"
	echo "$TASK" >"$TASK_FILE"
fi

# --- Build prompts ---
# Agent A (control): explicitly told no context available
cat >"/tmp/ab-test-prompt-a-$RUN_ID.txt" <<'PROMPT_A'
# Your Role: Code Analyst (CONTROL — no Trifecta context)

# Boundary: You are an EXECUTOR. Do NOT launch sub-agents.

# Task

PROMPT_A

cat "$TASK_FILE" >>"/tmp/ab-test-prompt-a-$RUN_ID.txt"

cat >>"/tmp/ab-test-prompt-a-$RUN_ID.txt" <<'PROMPT_A_FOOTER'

## Output

You MUST write your response to /tmp/ab-test-agent-a.md using the write tool.
Include this header:

## Status: success|partial|blocked
## Answer: <your complete answer>
## References: <list of files/symbols you referenced, or "none found">
## Confidence: high|medium|low
## Time to Answer: <estimate in seconds>
PROMPT_A_FOOTER

# Agent B (treatment): gets Trifecta context injected by extension
cat >"/tmp/ab-test-prompt-b-$RUN_ID.txt" <<'PROMPT_B'
# Your Role: Code Analyst (WITH Trifecta context)

# Boundary: You are an EXECUTOR. Do NOT launch sub-agents.

# Task

PROMPT_B

cat "$TASK_FILE" >>"/tmp/ab-test-prompt-b-$RUN_ID.txt"

cat >>"/tmp/ab-test-prompt-b-$RUN_ID.txt" <<'PROMPT_B_FOOTER'

## Output

You MUST write your response to /tmp/ab-test-agent-b.md using the write tool.
Include this header:

## Status: success|partial|blocked
## Answer: <your complete answer>
## References: <list of files/symbols you referenced, or "none found">
## Confidence: high|medium|low
## Time to Answer: <estimate in seconds>
PROMPT_B_FOOTER

# --- Launch both agents in parallel ---
echo "[AB-TEST] Launching Agent A (no extension) and Agent B (with extension)..."

LAUNCH_TIME=$(date +%s)

# Agent A: TRIFECTA_DISABLE=1
TRIFECTA_DISABLE=1 \
	timeout "$TIMEOUT" \
	env PI_LENS_STARTUP_MODE=quick \
	pi --provider "$PROVIDER" --model "$MODEL" \
	--mode json -nc -p @"/tmp/ab-test-prompt-a-$RUN_ID.txt" \
	>"/tmp/ab-test-output-a-$RUN_ID.jsonl" 2>/dev/null &
PID_A=$!
echo "$PID_A" >"/tmp/ab-test-pid-a-$RUN_ID.txt"

# Agent B: normal (extension runs)
timeout "$TIMEOUT" \
	env PI_LENS_STARTUP_MODE=quick \
	pi --provider "$PROVIDER" --model "$MODEL" \
	--mode json -nc -p @"/tmp/ab-test-prompt-b-$RUN_ID.txt" \
	>"/tmp/ab-test-output-b-$RUN_ID.jsonl" 2>/dev/null &
PID_B=$!
echo "$PID_B" >"/tmp/ab-test-pid-b-$RUN_ID.txt"

echo "[AB-TEST] Agent A PID: $PID_A (TRIFECTA_DISABLE=1)"
echo "[AB-TEST] Agent B PID: $PID_B (extension active)"

# --- Wait for both ---
SECONDS=0
POLL=15
while (kill -0 "$PID_A" 2>/dev/null || kill -0 "$PID_B" 2>/dev/null) && [ $SECONDS -lt "$TIMEOUT" ]; do
	STATUS_A="running"
	STATUS_B="running"
	kill -0 "$PID_A" 2>/dev/null || STATUS_A="done"
	kill -0 "$PID_B" 2>/dev/null || STATUS_B="done"
	echo "[AB-TEST] ${SECONDS}s — A: $STATUS_A, B: $STATUS_B"
	sleep "$POLL"
	SECONDS=$((SECONDS + POLL))
done

# Collect exit codes
wait "$PID_A" 2>/dev/null || true
EXIT_A=$?
wait "$PID_B" 2>/dev/null || true
EXIT_B=$?

END_TIME=$(date +%s)
WALL_SECONDS=$((END_TIME - LAUNCH_TIME))

echo "[AB-TEST] Done. Wall time: ${WALL_SECONDS}s. Exit codes: A=$EXIT_A, B=$EXIT_B"

# --- Validate outputs ---
validate_output() {
	local label="$1"
	local file="$2"
	local launch="$3"

	if [[ ! -f "$file" ]]; then
		echo "  $label: ❌ No output file"
		return 1
	fi

	local file_time
	file_time=$(stat -f '%m' "$file" 2>/dev/null || echo 0)
	if [[ "$file_time" -lt "$launch" ]]; then
		echo "  $label: ❌ Stale output (pre-launch)"
		return 1
	fi

	local size
	size=$(wc -c <"$file" 2>/dev/null || echo 0)
	if [[ "$size" -lt 200 ]]; then
		echo "  $label: ❌ Output too small ($size bytes)"
		return 1
	fi

	if ! grep -q '## Status:' "$file" 2>/dev/null; then
		echo "  $label: ❌ Missing envelope header"
		return 1
	fi

	echo "  $label: ✅ ($size bytes)"
	return 0
}

echo ""
echo "=== Results ==="
OK_A=0
OK_B=0
validate_output "Agent A (no ctx)" /tmp/ab-test-agent-a.md "$LAUNCH_TIME" && OK_A=1
validate_output "Agent B (w/ ctx)" /tmp/ab-test-agent-b.md "$LAUNCH_TIME" && OK_B=1

# --- Compare ---
if [[ $OK_A -eq 1 && $OK_B -eq 1 ]]; then
	echo ""
	echo "=== Comparison ==="

	# Extract fields
	for agent in a b; do
		FILE="/tmp/ab-test-agent-${agent}.md"
		echo ""
		echo "--- Agent ${agent^^} ---"
		grep -E '^## (Status|Confidence|Time to Answer|References):' "$FILE" 2>/dev/null || echo "(no header fields)"

		# Count unique file references
		REFS=$(grep -oE '[a-z_]+\.(py|ts|js|md|yaml|yml|json)' "$FILE" 2>/dev/null | sort -u | wc -l | tr -d ' ')
		echo "Unique file refs: $REFS"

		# Word count of answer section
		WORDS=$(sed -n '/^## Answer:/,/^## /p' "$FILE" 2>/dev/null | wc -w | tr -d ' ')
		echo "Answer word count: $WORDS"
	done
fi

# --- Write JSON result ---
cat >"/tmp/ab-test-result.json" <<JSONEOF
{
    "run_id": "$RUN_ID",
    "model": "$MODEL",
    "task_file": "$TASK_FILE",
    "wall_seconds": $WALL_SECONDS,
    "exit_a": $EXIT_A,
    "exit_b": $EXIT_B,
    "output_a_ok": $OK_A,
    "output_b_ok": $OK_B,
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSONEOF

echo ""
echo "[AB-TEST] Result saved to /tmp/ab-test-result.json"
echo "[AB-TEST] Agent A output: /tmp/ab-test-agent-a.md"
echo "[AB-TEST] Agent B output: /tmp/ab-test-agent-b.md"
