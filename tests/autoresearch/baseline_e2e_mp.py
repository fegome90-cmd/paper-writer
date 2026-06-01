"""Baseline: count E2E tests covering multi-project features."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# Count E2E tests that use -C or --project
e2e_file = REPO / "tests/e2e/test_smoke_e2e.py"
content = e2e_file.read_text()

checks = {
    "uses_project_flag": '"-C"' in content or '"--project"' in content,
    "tests_ascending_search": "ascending" in content.lower() or "subdir" in content.lower(),
    "tests_lean_init": "cli" not in content.split("test_init_creates_scaffold")[1].split("def ")[0]
    if "test_init_creates_scaffold" in content
    else False,
    "tests_cross_project_isolation": "isolation" in content.lower()
    or "two.*project" in content.lower(),
    "tests_cwd_fallback_e2e": "cwd" in content.lower() and "fallback" in content.lower(),
}

covered = sum(1 for v in checks.values() if v)
total = len(checks)

for name, passed in checks.items():
    print(f"  {'PASS' if passed else 'FAIL'}: {name}")

print(f"METRIC e2e_multi_project_covered={covered}")

# Also count total E2E tests
result = subprocess.run(
    ["uv", "run", "pytest", "tests/e2e/", "--co", "-q"],
    capture_output=True,
    text=True,
    cwd=REPO,
)
e2e_count = result.stdout.strip().split("\n")[-1] if result.stdout else "?"
print(f"total_e2e_tests={e2e_count}")

sys.exit(0)
