"""Baseline: count validators that hardcode execution_time_ms=0."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

total = 0
unmeasured = 0

for py_file in (REPO / "validators").glob("*.py"):
    if py_file.name.startswith("_"):
        continue
    source = py_file.read_text()
    if "execution_time_ms" not in source:
        continue
    total += 1
    # Check if execution_time_ms is hardcoded to 0 (not measured)
    if '"execution_time_ms": 0' in source or "'execution_time_ms': 0" in source:
        unmeasured += 1
        print(f"  UNMEASURED: {py_file.name}")
    else:
        print(f"  measured: {py_file.name}")

print(f"METRIC unmeasured_validators={unmeasured}")
print(f"total_validators_with_timing={total}")
sys.exit(0)
