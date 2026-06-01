"""Baseline: count stale documentation claims."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
stale = 0

# 1. TESTING_STRATEGY.md — hardcoded test count
ts = (REPO / "docs" / "TESTING_STRATEGY.md").read_text()
if "~520" in ts:
    stale += 1
    print("  STALE: TESTING_STRATEGY.md says ~520 tests (actually 537)")

# 2. MULTI_PROJECT_SPEC.md — blockers listed as TODO but already implemented
mp = (REPO / "docs" / "MULTI_PROJECT_SPEC.md").read_text()
if "STATUS: OPEN" in mp or "STATUS: TODO" in mp:
    stale += 1
    print("  STALE: MULTI_PROJECT_SPEC.md has OPEN/TODO blockers")

# Check for "currently the CLI uses Path.cwd()" — should say "previously"
if "Currently the CLI uses" in mp and "Path.cwd()" in mp:
    stale += 1
    print("  STALE: MULTI_PROJECT_SPEC.md says CLI 'currently' uses Path.cwd()")

# Check for unresolved blocker references
blocker_lines = [ln for ln in mp.split("\n") if ln.strip().startswith("| B") and "OPEN" in ln]
if blocker_lines:
    stale += 1
    print(f"  STALE: {len(blocker_lines)} blocker lines still marked OPEN")

# Check for old gate references
if '"cli", "harness", "validators"' in mp and "was:" not in mp.split('"cli"')[0][-50:]:
    stale += 1
    print("  STALE: MULTI_PROJECT_SPEC.md references old 5-dir gate as current")

# Get actual test count
r = subprocess.run(
    ["uv", "run", "pytest", "tests/", "-q", "--tb=no"],
    capture_output=True,
    text=True,
    cwd=REPO,
)
test_line = [ln for ln in r.stdout.strip().split("\n") if "passed" in ln]
print(f"  actual tests: {test_line[-1] if test_line else '?'}")

print(f"METRIC stale_doc_claims={stale}")
sys.exit(0)
