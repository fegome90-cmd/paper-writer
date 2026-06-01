"""Baseline validation script for multi-project-mode autoresearch gate.

Measures:
  - cwd_hardcodes_remaining: Path.cwd() in TARGET_FILES that are
    direct assignments (not args to resolve_project_root)
  - cwd_hardcodes_eliminated: 4 - remaining
  - features_implemented: --project flag, resolve_project_root, get_project_asset
  - bugs_present: gate checks source dirs, init creates source dirs
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

TARGET_FILES = [
    REPO / "cli/paper/main.py",
    REPO / "harness/services/orchestrator_builder.py",
    REPO / "integrations/tools/bibtex_tidy.py",
]

# ── cwd_hardcodes_remaining ──────────────────────────────────────────
# Count lines with Path.cwd() that are assignments (= Path.cwd()),
# not arguments to resolve_project_root.
cwd_remaining = 0
for f in TARGET_FILES:
    if not f.exists():
        continue
    for line in f.read_text().splitlines():
        stripped = line.strip()
        if "Path.cwd()" not in stripped:
            continue
        # Legitimate: resolve_project_root(..., Path.cwd())
        if "resolve_project_root" in stripped:
            continue
        # Legitimate: repo_path = Path(context.get("repo_path", Path.cwd()))
        # But that's what we're ELIMINATING. Count it.
        # Direct assignment pattern: = Path.cwd()
        if "= Path.cwd()" in stripped or "Path.cwd())" in stripped:
            cwd_remaining += 1

cwd_eliminated = 4 - cwd_remaining
print(f"cwd_hardcodes_remaining={cwd_remaining}")
print(f"METRIC cwd_hardcodes_eliminated={cwd_eliminated}")

# ── bugs_present ─────────────────────────────────────────────────────
SOURCE_DIRS = ["cli", "harness", "validators", "tests"]

gates_code = (REPO / "harness/services/gates.py").read_text()
gate_section = gates_code.split("validate_repo_initialized")[1]
gate_has_source = any(f'"{d}"' in gate_section for d in SOURCE_DIRS)

action_code = (REPO / "harness/adapters/filesystem_action_runner.py").read_text()
init_section = action_code.split('if command == "init"')[1]
init_has_source = any(f'"{d}"' in init_section for d in SOURCE_DIRS)

bugs = int(gate_has_source) + int(init_has_source)
print(f"bugs_present={bugs}/2")

# ── features_implemented ─────────────────────────────────────────────
main_code = (REPO / "cli/paper/main.py").read_text()
assets_code = (REPO / "harness/ports/assets.py").read_text()

features = 0
if '"--project"' in main_code and '"-C"' in main_code:
    features += 1
if "def resolve_project_root" in main_code:
    features += 1
if "def get_project_asset" in assets_code:
    features += 1
print(f"features_implemented={features}/3")

# ── Summary ──────────────────────────────────────────────────────────
if cwd_remaining == 0 and features == 3 and bugs == 0:
    print("BASELINE_CONFIRMED=complete")
else:
    print("BASELINE_CONFIRMED=partial")
sys.exit(0)
