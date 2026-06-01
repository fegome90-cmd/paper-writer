"""Baseline: check if paper CLI has --version."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

r = subprocess.run(
    ["uv", "run", "python", "-m", "cli.paper.main", "--version"],
    capture_output=True,
    text=True,
    cwd=REPO,
)
has_version = r.returncode == 0 and r.stdout.strip()

r2 = subprocess.run(
    ["uv", "run", "python", "-m", "cli.paper.main", "-V"],
    capture_output=True,
    text=True,
    cwd=REPO,
)
has_short_version = r2.returncode == 0 and r2.stdout.strip()

missing = 0
if not has_version:
    missing += 1
    print("  MISSING: --version flag")
else:
    print(f"  OK: --version = {r.stdout.strip()}")

if not has_short_version:
    missing += 1
    print("  MISSING: -V short flag")
else:
    print(f"  OK: -V = {r2.stdout.strip()}")

print(f"METRIC missing_cli_features={missing}")
sys.exit(0)
