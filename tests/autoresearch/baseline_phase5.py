"""Phase 5 baseline: precise ruff error count via JSON output."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# ruff check (JSON for precision)
result = subprocess.run(
    ["uv", "run", "ruff", "check", "--output-format=json", "."],
    capture_output=True,
    text=True,
    cwd=REPO,
)
if result.stdout.strip():
    findings = json.loads(result.stdout)
    ruff_check = len(findings)
    by_code: dict[str, int] = {}
    for f in findings:
        code = f.get("code", "?")
        by_code[code] = by_code.get(code, 0) + 1
        print(f"  {f['filename']}:{f['location']['row']}: {code} {f.get('message','')[:60]}")
else:
    ruff_check = 0
    by_code = {}
print(f"ruff_check_errors={ruff_check} {by_code}")

# ruff format check
fmt = subprocess.run(
    ["uv", "run", "ruff", "format", "--check", "--quiet", "."],
    capture_output=True,
    text=True,
    cwd=REPO,
)
ruff_fmt = len([ln for ln in fmt.stdout.strip().splitlines() if ln.strip()])
print(f"ruff_format_errors={ruff_fmt}")

total = ruff_check + ruff_fmt
print(f"METRIC ruff_errors={total}")
sys.exit(0)
