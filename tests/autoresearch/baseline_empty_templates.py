"""Baseline: count empty template files created by paper init (no preset)."""

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

with tempfile.TemporaryDirectory() as raw_td:
    td = Path(raw_td) / "paper"
    td.mkdir()
    subprocess.run(
        ["uv", "run", "python", "-m", "cli.paper.main", "-C", str(td), "init"],
        capture_output=True,
        cwd=REPO,
    )

    empty = 0
    for f in td.rglob("*"):
        if f.is_file() and f.stat().st_size == 0:
            empty += 1
            print(f"  EMPTY: {f.relative_to(td)} ({f.stat().st_size} bytes)")

    # Also check: source template has content?
    src_qmd = REPO / "templates" / "manuscript.qmd"
    src_bib = REPO / "templates" / "references.bib"
    print(f"\n  source manuscript.qmd: {src_qmd.stat().st_size} bytes")
    print(f"  source references.bib: {src_bib.stat().st_size} bytes")

    print(f"METRIC empty_template_files={empty}")
sys.exit(0)
