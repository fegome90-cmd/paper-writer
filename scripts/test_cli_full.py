#!/usr/bin/env python3
"""Comprehensive CLI feature test — tests every command and subcommand."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = [sys.executable, "-m", "cli.paper.main"]

bugs: list[dict[str, str]] = []
passed = 0
skipped = 0


def run(args: list[str], *, expect_exit: int = 0, cwd: Path | None = None) -> tuple[str, str, int]:
    """Run CLI command, return (stdout, stderr, returncode)."""
    result = subprocess.run(
        CLI + args,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd or REPO,
        env={
            **__import__("os").environ,
            "ZOTERO_USER_ID": "20772197",
            "ZOTERO_API_KEY": "REDACTED_ZOTERO_API_KEY",
            "ZOTERO_LIBRARY_TYPE": "user",
        },
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def test(name: str, args: list[str], *, expect_exit: int = 0, expect_in: str | None = None,
         expect_not_in: str | None = None, expect_err_in: str | None = None) -> None:
    """Test a CLI command."""
    global passed, skipped
    stdout, stderr, rc = run(args, expect_exit=expect_exit)
    label = f"{' '.join(args)}"
    details = []

    if rc != expect_exit:
        details.append(f"exit={rc} (expected {expect_exit})")
    if expect_in and expect_in not in stdout and expect_in not in stderr:
        details.append(f"expected '{expect_in}' not found in output")
    if expect_not_in and expect_not_in in stdout:
        details.append(f"unexpected '{expect_not_in}' found in output")
    if expect_err_in and expect_err_in not in stderr:
        details.append(f"expected '{expect_err_in}' not found in stderr")

    if details:
        bugs.append({"name": name, "cmd": label, "details": "; ".join(details), "stdout": stdout[:200], "stderr": stderr[:200]})
        print(f"  BUG {name}: {'; '.join(details)}")
    else:
        passed += 1
        print(f"  OK   {name}")


def test_env(tmp: Path) -> None:
    """Set up a temp project directory."""
    state = tmp / "outputs" / "state.yaml"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("schema_version: '1.2'\nstage: init\ngates:\n  init_done: true\n")


# =========================================================================
print("=" * 60)
print("Phase 1: Basic commands (help, version, doctor)")
print("=" * 60)

test("version", ["--version"], expect_exit=0, expect_in="0.1.0")
test("help", ["--help"], expect_exit=0, expect_in="paper CLI")
test("doctor", ["doctor"], expect_exit=0, expect_in="environment check")

# =========================================================================
print("\n" + "=" * 60)
print("Phase 2: init command")
print("=" * 60)

test("init default", ["init"], expect_exit=0, expect_in="init")
test("init --preset nature", ["init", "--preset", "nature"], expect_exit=0)
test("init --mode academic", ["init", "--mode", "academic"], expect_exit=0)

# =========================================================================
print("\n" + "=" * 60)
print("Phase 3: Zotero subcommands (8 operations)")
print("=" * 60)

test("zotero help", ["zotero", "--help"], expect_in="collections")
test("zotero collections", ["zotero", "collections"], expect_exit=0)
test("zotero template book", ["zotero", "template", "book"], expect_in="itemType")
test("zotero template journalArticle", ["zotero", "template", "journalArticle"], expect_in="itemType")
test("zotero search", ["zotero", "search", "machine learning", "--limit", "1"], expect_exit=0)
test("zotero search --json", ["zotero", "search", "test", "--limit", "1", "--json"], expect_exit=0)

# Test key validation
test("zotero get bad key", ["zotero", "get", "badkey!"], expect_exit=1, expect_in="Invalid")
test("zotero get short key", ["zotero", "get", "ABC"], expect_exit=1, expect_in="Invalid")

# Test file validation
test("zotero create missing file", ["zotero", "create", "/nonexistent.json"], expect_exit=1)
test("zotero upload missing file", ["zotero", "upload", "ABCD2345", "/nonexistent.pdf"], expect_exit=1)
test("zotero delete no version batch", ["zotero", "delete", "ABCD2345", "EFGH6789"], expect_exit=1, expect_in="version")

# Create, get, update, delete cycle
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    json.dump([{"itemType": "book", "title": "CLI Full Test", "date": "2026"}], f)
    create_file = f.name

stdout, _, _ = run(["zotero", "create", create_file])
key = ""
if "Created: 1" in stdout:
    # Extract key
    for line in stdout.split("\n"):
        stripped = line.strip()
        if stripped and stripped[0] in "23456789ABCDEFGH":
            candidate = stripped.split(":")[0].strip()
            if len(candidate) == 8:
                key = candidate
                break
    
    if key and len(key) == 8:
        test("zotero get live", ["zotero", "get", key], expect_in="CLI Full Test")
        test("zotero get --json", ["zotero", "get", key, "--json"], expect_in="key")
        
        # Partial update
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            json.dump({"title": "CLI Full Test Updated"}, f2)
            update_file = f2.name
        test("zotero update partial", ["zotero", "update", key, update_file, "--partial"], expect_in="Updated")
        
        # Full update
        test("zotero update full", ["zotero", "update", key, update_file], expect_in="Updated")
        
        # Delete
        test("zotero delete auto-version", ["zotero", "delete", key], expect_in="Deleted")
    else:
        print(f"  SKIP create cycle (key={key!r})")
        skipped += 1
else:
    print(f"  SKIP create cycle (create failed: {stdout[:100]})")
    skipped += 1

# =========================================================================
print("\n" + "=" * 60)
print("Phase 4: thesaurus subcommands")
print("=" * 60)

test("thesaurus help", ["thesaurus", "--help"], expect_in="import")
test("thesaurus list", ["thesaurus", "list"], expect_exit=0)
test("thesaurus audit", ["thesaurus", "audit"], expect_exit=0)
test("thesaurus search", ["thesaurus", "search", "diabetes"], expect_exit=0)

# =========================================================================
print("\n" + "=" * 60)
print("Phase 5: mesh subcommands")
print("=" * 60)

test("mesh help", ["mesh", "--help"], expect_exit=0)
test("mesh resolve", ["mesh", "resolve", "diabetes"], expect_exit=0)
test("mesh expand", ["mesh", "expand", "Diabetes Mellitus"], expect_exit=0)

# =========================================================================
print("\n" + "=" * 60)
print("Phase 6: lint / check / audit")
print("=" * 60)

test("lint bib (no file)", ["lint", "bib"], expect_exit=0)
test("lint style", ["lint", "style"], expect_exit=0)
test("check refs", ["check", "refs"], expect_exit=0)

# Audit subcommands
for subcmd in ["prose", "claims", "ethics", "writing-quality"]:
    test(f"audit {subcmd}", ["audit", subcmd], expect_exit=0)

# =========================================================================
print("\n" + "=" * 60)
print("Phase 7: verify / gate / protocol / render")
print("=" * 60)

test("verify", ["verify"], expect_exit=0)
test("gate method", ["gate", "method"], expect_exit=0)

# protocol needs --search-dir
test("protocol no dir", ["protocol"], expect_exit=2)
test("render", ["render"], expect_exit=0)

# =========================================================================
print("\n" + "=" * 60)
print("Phase 8: search / chain / screen / export-bib (dry-run)")
print("=" * 60)

# These need state — test that they handle missing state gracefully
test("search no query", ["search"], expect_exit=0)
test("chain", ["chain"], expect_exit=0)
test("screen", ["screen"], expect_exit=0)
test("export-bib", ["export-bib"], expect_exit=0)

# =========================================================================
print("\n" + "=" * 60)
print("Phase 9: import")
print("=" * 60)

test("import help", ["import", "--help"], expect_in="bib")
test("import bib no source", ["import", "bib"], expect_exit=0)

# =========================================================================
print("\n" + "=" * 60)
print("Phase 10: draft subcommands")
print("=" * 60)

test("draft outline", ["draft", "outline"], expect_exit=0)
test("draft section no args", ["draft", "section"], expect_exit=0)
test("draft all", ["draft", "all"], expect_exit=0)

# =========================================================================
print("\n" + "=" * 60)
print("Phase 11: trace / graph-overview")
print("=" * 60)

test("trace help", ["trace", "--help"], expect_in="symbol")
test("graph-overview", ["graph-overview"], expect_exit=0)

# =========================================================================
# SUMMARY
# =========================================================================
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {len(bugs)} bugs, {skipped} skipped")
print("=" * 60)

if bugs:
    print("\nBUGS FOUND:")
    for b in bugs:
        print(f"  [{b['name']}] {b['cmd']}: {b['details']}")
        if b["stderr"]:
            print(f"    stderr: {b['stderr'][:100]}")

# Write structured output for autoresearch
print(f"\nMETRIC cli_bugs={len(bugs)}")
