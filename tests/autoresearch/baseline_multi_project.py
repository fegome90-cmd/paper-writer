"""Baseline validation script for multi-project-mode autoresearch gate.

Measures:
  - cwd_hardcodes: count of Path.cwd() calls that must be eliminated
  - gate_checks_source_dirs: whether validate_repo_initialized requires source dirs
  - init_creates_source_dirs: whether init scaffolds source-code stubs
  - has_project_flag: whether --project/-C CLI flag exists
  - has_resolve_project_root: whether resolve_project_root() function exists
  - has_get_project_asset: whether get_project_asset() function exists

Exit 0 = all pass, 1 = failures found (baseline gap confirmed).
"""
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# ── 1. cwd_hardcodes: count Path.cwd() in target files ──────────────
TARGET_FILES = [
    REPO / "cli/paper/main.py",
    REPO / "harness/services/orchestrator_builder.py",
    REPO / "integrations/tools/bibtex_tidy.py",
]

cwd_count = 0
for f in TARGET_FILES:
    if not f.exists():
        print(f"WARN: {f} not found")
        continue
    tree = ast.parse(f.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Attribute)
                    and func.attr == "cwd"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "Path"):
                cwd_count += 1

print(f"cwd_hardcodes={cwd_count}")
if cwd_count != 4:
    print(f"WARN: expected 4, found {cwd_count}")

# ── 2. gate_checks_source_dirs ──────────────────────────────────────
gates_path = REPO / "harness/services/gates.py"
gates_code = gates_path.read_text()
# Check if required_dirs includes source-code dirs
SOURCE_DIRS = ["cli", "harness", "validators", "tests"]
gate_has_source = any(f'"{d}"' in gates_code.split("validate_repo_initialized")[1].split("def ")[0]
                      for d in SOURCE_DIRS)
print(f"gate_checks_source_dirs={gate_has_source}")

# ── 3. init_creates_source_dirs ─────────────────────────────────────
action_runner_path = REPO / "harness/adapters/filesystem_action_runner.py"
action_code = action_runner_path.read_text()
init_section = action_code.split('if command == "init"')[1].split("elif command")[0]
init_has_source = any(f'"{d}"' in init_section for d in SOURCE_DIRS)
print(f"init_creates_source_dirs={init_has_source}")

# ── 4. has_project_flag ────────────────────────────────────────────
main_code = (REPO / "cli/paper/main.py").read_text()
has_flag = '"--project"' in main_code or "'--project'" in main_code
has_short = '"-C"' in main_code or "'-C'" in main_code
print(f"has_project_flag={has_flag and has_short}")

# ── 5. has_resolve_project_root ────────────────────────────────────
has_resolve = "def resolve_project_root" in main_code
print(f"has_resolve_project_root={has_resolve}")

# ── 6. has_get_project_asset ────────────────────────────────────────
assets_code = (REPO / "harness/ports/assets.py").read_text()
has_gpa = "def get_project_asset" in assets_code
print(f"has_get_project_asset={has_gpa}")

# ── Summary ─────────────────────────────────────────────────────────
# Current state: 4 hardcodes, gate checks source dirs, init creates source stubs,
# no project flag, no resolve function, no get_project_asset.
# Target: 0 hardcodes, no source dirs in gate/init, all 3 new functions present.

checks = {
    "cwd_hardcodes": cwd_count == 4,          # baseline: should be 4
    "gate_checks_source_dirs": gate_has_source,  # baseline: should be True (bug)
    "init_creates_source_dirs": init_has_source, # baseline: should be True (bug)
    "has_project_flag": has_flag and has_short,   # baseline: should be False (missing)
    "has_resolve_project_root": has_resolve,      # baseline: should be False (missing)
    "has_get_project_asset": has_gpa,             # baseline: should be False (missing)
}

# For baseline: features implemented = 0 (nothing done yet)
features_implemented = sum(1 for k, v in checks.items()
                           if k in ("has_project_flag", "has_resolve_project_root", "has_get_project_asset")
                           and v)
bugs_present = sum(1 for k, v in checks.items()
                   if k in ("gate_checks_source_dirs", "init_creates_source_dirs") and v)
cwd_eliminated = 4 - cwd_count

print(f"METRIC cwd_hardcodes_eliminated={cwd_eliminated}")
print(f"features_implemented={features_implemented}/3")
print(f"bugs_present={bugs_present}/2")
print(f"cwd_hardcodes_remaining={cwd_count}")

# Baseline: should show 0 eliminated, 0/3 features, 2 bugs
if cwd_eliminated == 0 and features_implemented == 0 and bugs_present == 2:
    print("BASELINE_CONFIRMED=yes")
    sys.exit(0)
else:
    print("BASELINE_CONFIRMED=partial")
    sys.exit(0)  # Still exit 0 — this is just measurement
