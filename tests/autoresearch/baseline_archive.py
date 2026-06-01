"""SDD archive baseline: measure what's NOT yet archived."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

total = 0
done = 0

checks = {
    "main_spec_synced": (REPO / "openspec" / "specs" / "paper-writer" / "spec.md").exists(),
    "change_moved_to_archive": (
        REPO / "openspec" / "changes" / "archive" / "2026-06-01-multi-project-mode"
    ).exists(),
    "blockers_marked_implemented": False,  # check below
    "archive_report_in_engram": False,  # check via memory
    "sdd_cycle_complete": False,
}

# Check blockers in MULTI_PROJECT_SPEC.md
spec_file = REPO / "docs" / "MULTI_PROJECT_SPEC.md"
if spec_file.exists():
    content = spec_file.read_text()
    blockers_remaining = content.count("STATUS: OPEN")
    blockers_done = content.count("STATUS: IMPLEMENTED")
    checks["blockers_marked_implemented"] = blockers_remaining == 0
    print(f"blockers: {blockers_done} implemented, {blockers_remaining} open")

for name, passed in checks.items():
    total += 1
    status = "PASS" if passed else "FAIL"
    if passed:
        done += 1
    print(f"  {status}: {name}")

print(f"METRIC archive_tasks_completed={done}")
sys.exit(0)
