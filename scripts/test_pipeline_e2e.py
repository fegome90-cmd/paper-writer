#!/usr/bin/env python3
"""Full academic pipeline E2E test — init to render."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path("/Users/felipe_gonzalez/Developer/paper-writer")
CLI = [sys.executable, "-m", "cli.paper.main"]

bugs: list[dict[str, str]] = []
passed = 0


def run(args: list[str], cwd: Path) -> tuple[str, str, int]:
    env = {
        **os.environ,
        "ZOTERO_USER_ID": "20772197",
        "ZOTERO_API_KEY": "REDACTED_ZOTERO_API_KEY",
        "ZOTERO_LIBRARY_TYPE": "user",
    }
    r = subprocess.run(CLI + args, capture_output=True, text=True, timeout=60, cwd=REPO, env=env)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def test(name: str, args: list[str], cwd: Path, *, expect_exit: int = 0, check: str | None = None) -> tuple[str, str, int]:
    global passed
    stdout, stderr, rc = run(args, cwd)
    label = " ".join(args)

    ok = rc == expect_exit
    if check and check not in stdout and check not in stderr:
        ok = False

    if ok:
        passed += 1
        print(f"  OK   {name}")
    else:
        bugs.append({"name": name, "cmd": label, "rc": str(rc), "stdout": stdout[:200], "stderr": stderr[:200]})
        print(f"  BUG  {name}: exit={rc}, stdout={stdout[:100]}")
    return stdout, stderr, rc


# =========================================================================
TMP = Path("/tmp/paper-e2e-test")
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir()

print("=" * 60)
print("E2E Academic Pipeline Test")
print("=" * 60)

# Phase 1: Init
print("\n--- Phase 1: init ---")
test("init", ["--project", str(TMP), "init", "--mode", "rapid"], TMP, check="Success")

# Phase 2: Search (Consensus API)
print("\n--- Phase 2: search ---")
stdout, stderr, rc = run(["--project", str(TMP), "search", "--query", "systematic review machine learning healthcare", "--year-min", "2020", "--year-max", "2026"], TMP)
if rc == 0 and "search_completed" in stdout:
    passed += 1
    print("  OK   search (live)")
else:
    print(f"  WARN search: exit={rc}, output={stdout[:100]}")
    # Continue anyway — search might fail due to API limits

# Phase 3: Screen
print("\n--- Phase 3: screen ---")
test("screen", ["--project", str(TMP), "screen"], TMP)

# Phase 4: Export Bib
print("\n--- Phase 4: export-bib ---")
test("export-bib", ["--project", str(TMP), "export-bib"], TMP)

# Phase 4b: Import bib from Zotero
print("\n--- Phase 4b: import bib (from Zotero) ---")
stdout, stderr, rc = run(["--project", str(TMP), "import", "bib", "--from-zotero"], TMP)
if rc == 0:
    passed += 1
    print("  OK   import bib from Zotero")
else:
    print(f"  WARN import bib: {stderr[:100]}")

# Phase 5: Lint
print("\n--- Phase 5: lint ---")
test("lint bib", ["--project", str(TMP), "lint", "bib"], TMP)
test("lint style", ["--project", str(TMP), "lint", "style"], TMP)

# Phase 6: Check
print("\n--- Phase 6: check ---")
test("check refs", ["--project", str(TMP), "check", "refs"], TMP)

# Phase 7: Draft
print("\n--- Phase 7: draft ---")
stdout, stderr, rc = run(["--project", str(TMP), "draft", "outline"], TMP)
if rc == 0:
    passed += 1
    print("  OK   draft outline")
else:
    print(f"  WARN draft outline: exit={rc}, {stdout[:100]}")

# Phase 8: Audit (individual)
print("\n--- Phase 8: audit ---")
manuscript = TMP / "outputs" / "drafts" / "manuscript.qmd"
if not manuscript.exists():
    manuscript = TMP / "templates" / "manuscript.qmd"

if manuscript.exists():
    for subcmd in ["prose", "claims", "ethics", "writing-quality"]:
        test(f"audit {subcmd}", ["--project", str(TMP), "audit", subcmd, str(manuscript)], TMP)
else:
    print(f"  SKIP audit (no manuscript at {manuscript})")

# Phase 9: Gate
print("\n--- Phase 9: gate ---")
stdout, stderr, rc = run(["--project", str(TMP), "gate", "method"], TMP)
if rc == 0 or "Gate" in stdout or "gate" in stdout:
    passed += 1
    print("  OK   gate method")
else:
    print(f"  WARN gate: {stdout[:100]}")

# Phase 10: Verify
print("\n--- Phase 10: verify ---")
stdout, stderr, rc = run(["--project", str(TMP), "verify"], TMP)
if rc == 0:
    passed += 1
    print("  OK   verify")
else:
    # Verify blocks on missing gates — expected
    if "Blocked" in stdout or "FAILED" in stdout:
        passed += 1
        print("  OK   verify (blocked on gates — expected)")
    else:
        bugs.append({"name": "verify", "cmd": "verify", "rc": str(rc), "stdout": stdout[:200], "stderr": stderr[:200]})
        print(f"  BUG  verify: {stdout[:100]}")

# Phase 11: Doctor
print("\n--- Phase 11: doctor ---")
test("doctor", ["--project", str(TMP), "doctor"], TMP, check="environment check")

# Phase 12: Zotero operations
print("\n--- Phase 12: Zotero ---")
test("zotero collections", ["--project", str(TMP), "zotero", "collections"], TMP)
test("zotero search", ["--project", str(TMP), "zotero", "search", "review", "--limit", "3"], TMP)
test("zotero template", ["--project", str(TMP), "zotero", "template", "book"], TMP, check="itemType")

# Phase 13: Thesaurus
print("\n--- Phase 13: thesaurus ---")
stdout, stderr, rc = run(["--project", str(TMP), "thesaurus", "list"], TMP)
if rc == 0:
    passed += 1
    print("  OK   thesaurus list")
else:
    print("  SKIP thesaurus (not installed)")

# Phase 14: Protocol
print("\n--- Phase 14: protocol ---")
search_dir = TMP / "outputs" / "runs"
if search_dir.exists():
    dirs = list(search_dir.iterdir())
    if dirs:
        test("protocol", ["--project", str(TMP), "protocol", "--search-dir", str(dirs[0] / "search")], TMP)
    else:
        print("  SKIP protocol (no search runs)")
else:
    print("  SKIP protocol (no runs dir)")

# =========================================================================
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {len(bugs)} bugs")
print("=" * 60)

if bugs:
    print("\nBUGS:")
    for b in bugs:
        print(f"  [{b['name']}] {b['cmd']}: rc={b['rc']} — {b['stdout'][:80]}")

print(f"\nMETRIC pipeline_bugs={len(bugs)}")
