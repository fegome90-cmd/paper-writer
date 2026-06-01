"""Baseline: count runtime assets missing from the wheel."""
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# Build wheel
dist_dir = REPO / "dist_test"
dist_dir.mkdir(exist_ok=True)
subprocess.run(
    ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
    cwd=REPO, capture_output=True, timeout=60,
)
wheels = list(dist_dir.glob("*.whl"))
if not wheels:
    print("FATAL: No wheel built")
    sys.exit(1)
wheel = wheels[0]

# Check what's in the wheel vs what's needed at runtime
with zipfile.ZipFile(wheel) as z:
    wheel_files = set(z.namelist())

# Runtime-essential assets (used via Path(__file__).parent.parent / "X")
required_assets = {
    "rules": list((REPO / "rules").rglob("*")),
    "schemas": list((REPO / "schemas").rglob("*")),
}

missing = 0
missing_details: list[str] = []

for _category, files in required_assets.items():
    for f in files:
        if f.is_dir():
            continue
        # Expected path in wheel (flat under package root)
        rel = f.relative_to(REPO)
        # Check multiple possible locations in wheel
        found = any(str(rel) in wf for wf in wheel_files)
        if not found:
            missing += 1
            if len(missing_details) < 20:
                missing_details.append(str(rel))

print(f"Missing runtime assets in wheel: {missing}")
for d in missing_details:
    print(f"  MISSING: {d}")

# Also check: which source files use Path(__file__).parent.parent?
print("\n=== Runtime path patterns ===")

for py in (REPO / "validators").glob("*.py"):
    content = py.read_text()
    matches = re.findall(
        r'Path\(__file__\).*?["\']([^"\']+)["\']', content,
    )
    for m in matches:
        print(f"  {py.name}: Path(__file__).../{m}")

print(f"\nMETRIC missing_runtime_assets={missing}")

# Cleanup
shutil.rmtree(dist_dir, ignore_errors=True)
sys.exit(0)
