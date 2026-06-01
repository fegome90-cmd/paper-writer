"""Production readiness: comprehensive quality gate measurement."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
passed = 0
total = 5

# 1. ruff check
r = subprocess.run(
    ["uv", "run", "ruff", "check", "--quiet", "."],
    capture_output=True,
    text=True,
    cwd=REPO,
)
ruff_clean = r.returncode == 0
if ruff_clean:
    passed += 1
print(f"  {'PASS' if ruff_clean else 'FAIL'}: ruff check (exit={r.returncode})")

# 2. ruff format
r = subprocess.run(
    ["uv", "run", "ruff", "format", "--check", "--quiet", "."],
    capture_output=True,
    text=True,
    cwd=REPO,
)
fmt_clean = r.returncode == 0
if fmt_clean:
    passed += 1
print(f"  {'PASS' if fmt_clean else 'FAIL'}: ruff format (exit={r.returncode})")

# 3. mypy
r = subprocess.run(
    ["uv", "run", "mypy", "harness", "cli", "validators", "integrations", "verification"],
    capture_output=True,
    text=True,
    cwd=REPO,
)
mypy_clean = r.returncode == 0
if mypy_clean:
    passed += 1
print(f"  {'PASS' if mypy_clean else 'FAIL'}: mypy (exit={r.returncode})")

# 4. pytest
r = subprocess.run(
    ["uv", "run", "pytest", "tests/", "-q", "--tb=no"],
    capture_output=True,
    text=True,
    cwd=REPO,
)
tests_pass = r.returncode == 0
test_line = [ln for ln in r.stdout.strip().split("\n") if "passed" in ln]
test_info = test_line[-1] if test_line else "?"
if tests_pass:
    passed += 1
print(f"  {'PASS' if tests_pass else 'FAIL'}: pytest ({test_info})")

# 5. full pipeline with -C
r = subprocess.run(
    [
        "uv",
        "run",
        "python",
        "-c",
        """
import tempfile, subprocess
from pathlib import Path
with tempfile.TemporaryDirectory() as td:
    td = Path(td) / 'p'
    td.mkdir()
    r = subprocess.run(
        ['uv', 'run', 'python', '-m', 'cli.paper.main', '-C', str(td), 'init'],
        capture_output=True, text=True
    )
    assert r.returncode == 0, f'init failed: {r.stderr}'
    assert (td / 'outputs' / 'state.yaml').exists()
    assert not (td / 'cli').exists()
    print('full pipeline OK')
""",
    ],
    capture_output=True,
    text=True,
    cwd=REPO,
)
pipeline_ok = r.returncode == 0
if pipeline_ok:
    passed += 1
print(f"  {'PASS' if pipeline_ok else 'FAIL'}: full pipeline -C init ({r.stdout.strip()})")

print(f"\nMETRIC quality_gates_passed={passed}")
print(f"production_ready={'YES' if passed == total else 'NO'}")
sys.exit(0)
