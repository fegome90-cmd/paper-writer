#!/usr/bin/env python3
"""Phase 6 — Real Material Validation Runner.

Reads a validation manifest, sets up an isolated workspace, executes the
paper CLI pipeline, and produces a local report.  Never commits real
material to the repository.

Usage:
    python verification/run_real_validation.py <manifest_path>
    python verification/run_real_validation.py verification/local-data/case.local.yaml
    python verification/run_real_validation.py --dry-run <manifest_path>

Exit codes:
    0  pass or pass_with_degraded_mode (automated checks satisfied)
    1  fail (pipeline error or acceptance criteria not met)
    2  configuration error (missing file, bad manifest)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ── Constants ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
VERIFICATION_DIR = REPO_ROOT / "verification"
REPORTS_DIR = VERIFICATION_DIR / "reports"

VERDICT_PASS = "pass"
VERDICT_DEGRADED = "pass_with_degraded_mode"
VERDICT_MANUAL = "manual_review_required"
VERDICT_FAIL = "fail"

VALID_VERDICTS = {VERDICT_PASS, VERDICT_DEGRADED, VERDICT_MANUAL, VERDICT_FAIL}


# ── Data structures ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StageResult:
    """Outcome of a single pipeline stage."""

    name: str
    command: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    degraded: bool = False
    degraded_reason: str = ""
    skipped: bool = False


@dataclass
class ValidationResult:
    """Full result of a validation run."""

    case_id: str
    title: str
    manifest_path: str
    workspace: str
    stages: list[StageResult] = field(default_factory=list)
    acceptance: dict[str, bool] = field(default_factory=dict)
    verdict: str = VERDICT_FAIL
    degraded_warnings: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    notes: list[str] = field(default_factory=list)


# ── Manifest loading ───────────────────────────────────────────────────────

REQUIRED_FIELDS = {"case_id", "title", "source_material", "stages"}
REQUIRED_SOURCE_FIELDS = {"pdf_path"}


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a YAML manifest. Returns parsed dict."""
    if not path.exists():
        print(f"ERROR: manifest not found: {path}", file=sys.stderr)
        sys.exit(2)
    with open(path) as f:
        data = yaml.safe_load(f)

    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        print(f"ERROR: manifest missing required fields: {missing}", file=sys.stderr)
        sys.exit(2)

    src = data["source_material"]
    src_missing = REQUIRED_SOURCE_FIELDS - set(src.keys())
    if src_missing:
        print(
            f"ERROR: source_material missing required fields: {src_missing}",
            file=sys.stderr,
        )
        sys.exit(2)
    return dict(data)


def resolve_bib_path(manifest: dict[str, Any]) -> str | None:
    """Resolve bibliography path from manifest, or None if skip."""
    bib = manifest.get("bibliography", {})
    mode = bib.get("mode", "skip")
    if mode == "skip":
        return None
    path = bib.get("bib_path", "")
    if not path and mode == "required":
        print("ERROR: bibliography mode is 'required' but bib_path is empty", file=sys.stderr)
        sys.exit(2)
    return path if path else None


# ── Workspace isolation ────────────────────────────────────────────────────


def prepare_workspace(manifest: dict[str, Any], tmp_root: Path | None = None) -> Path:
    """Create an isolated workspace as a copy of the repo structure.

    The workspace is a temp directory containing:
    - A symlink to .venv (avoids re-install)
    - Copies of templates/, styles/, skills/ (read-only pipeline inputs)
    - A fresh outputs/ directory
    - A fresh outputs/state.yaml

    Returns the workspace root path.
    """
    ws = Path(tempfile.mkdtemp(prefix=f"paper-validate-{manifest['case_id']}-", dir=tmp_root))

    # Symlink venv to avoid reinstall
    venv = REPO_ROOT / ".venv"
    if venv.exists():
        (ws / ".venv").symlink_to(venv)

    # Copy read-only pipeline inputs
    for d in ("templates", "styles", "skills"):
        src = REPO_ROOT / d
        if src.exists():
            shutil.copytree(src, ws / d, symlinks=True)

    # Copy pyproject.toml and cli/ for the CLI to work
    for f in ("pyproject.toml",):
        src_f = REPO_ROOT / f
        if src_f.exists():
            shutil.copy2(src_f, ws / f)

    # Copy source packages needed for CLI
    for pkg in ("cli", "harness", "validators", "integrations"):
        src_pkg = REPO_ROOT / pkg
        if src_pkg.exists():
            shutil.copytree(src_pkg, ws / pkg, symlinks=True)

    # Fresh outputs directory
    (ws / "outputs").mkdir()
    (ws / "outputs" / "drafts").mkdir()
    (ws / "outputs" / "search").mkdir()
    (ws / "outputs" / "render").mkdir()
    (ws / "outputs" / "logs").mkdir()

    # Fresh state.yaml with all required gates initialized to false
    all_gates = [
        "repo_initialized", "search_completed", "screened_evidence",
        "outline_drafted", "sections_completed", "bib_normalized",
        "citations_resolved", "refs_validated", "style_passed",
        "reporting_passed", "render_passed", "ready_for_delivery",
    ]
    gates_yaml = "\n".join(f"  {g}: false" for g in all_gates)
    state_yaml = ws / "outputs" / "state.yaml"
    state_yaml.write_text(
        f"repo_initialized: false\ngates:\n{gates_yaml}\nstage: bootstrap\n"
    )

    return ws


# ── Pipeline execution ─────────────────────────────────────────────────────


def _build_paper_cmd(workspace: Path) -> list[str]:
    """Build the base command for invoking the paper CLI in the workspace."""
    venv_python = workspace / ".venv" / "bin" / "python"
    if venv_python.exists():
        return [str(venv_python), "-m", "cli.paper.main"]
    # Fallback: system python with repo on sys.path
    return [sys.executable, "-m", "cli.paper.main"]


def run_stage(
    workspace: Path,
    stage: dict[str, Any],
    bib_path: str | None,
    timeout: int = 120,
) -> StageResult:
    """Execute a single pipeline stage and return the result."""
    cmd_str = stage["command"]
    args = list(stage.get("args", []))

    # Interpolate {bib_path} placeholder
    if bib_path:
        args = [a.replace("{bib_path}", bib_path) for a in args]

    cmd = [*_build_paper_cmd(workspace), cmd_str, *args]
    allow_degraded = stage.get("allow_degraded", False)

    # Check skip_if conditions
    skip_if = stage.get("skip_if", "")
    if skip_if == "bibliography.mode == skip" and bib_path is None:
        return StageResult(
            name=stage["name"],
            command=cmd_str,
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            duration_s=0.0,
            skipped=True,
        )

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workspace),
        )
        duration = time.monotonic() - t0
        success = proc.returncode == 0
        degraded = False
        degraded_reason = ""

        # Check if failure was due to a degraded-mode tool
        if not success and allow_degraded:
            stderr_lower = proc.stderr.lower()
            degraded_markers = ["unavailable", "not found", "not installed", "degraded"]
            if any(m in stderr_lower for m in degraded_markers):
                degraded = True
                degraded_reason = stage.get("degraded_reason", "Tool unavailable")
                success = True  # Treat as success for pipeline continuation

        return StageResult(
            name=stage["name"],
            command=cmd_str,
            success=success,
            exit_code=proc.returncode,
            stdout=proc.stdout[-2000:] if proc.stdout else "",  # Truncate
            stderr=proc.stderr[-2000:] if proc.stderr else "",
            duration_s=round(duration, 2),
            degraded=degraded,
            degraded_reason=degraded_reason,
        )
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return StageResult(
            name=stage["name"],
            command=cmd_str,
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Stage timed out after {timeout}s",
            duration_s=round(duration, 2),
        )
    except Exception as e:
        duration = time.monotonic() - t0
        return StageResult(
            name=stage["name"],
            command=cmd_str,
            success=False,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            duration_s=round(duration, 2),
        )


# ── Acceptance checks ─────────────────────────────────────────────────────


def check_acceptance(
    result: ValidationResult,
    manifest: dict[str, Any],
    workspace: Path,
) -> dict[str, bool]:
    """Run automated acceptance checks against pipeline output."""
    checks: dict[str, bool] = {}
    criteria = manifest.get("acceptance", {})

    # 1. Pipeline completed all stages
    if criteria.get("pipeline_completed", True):
        checks["pipeline_completed"] = all(s.success for s in result.stages)

    # 2. No fabricated references
    if criteria.get("no_fabricated_refs", True):
        # Check that no @al keys appear in any draft output
        fabricated = False
        drafts_dir = workspace / "outputs" / "drafts"
        if drafts_dir.exists():
            for f in drafts_dir.iterdir():
                if f.suffix == ".md" and f.is_file():
                    content = f.read_text()
                    if "@al" in content:
                        fabricated = True
                        result.notes.append(f"Fabricated ref pattern '@al' found in {f.name}")
        checks["no_fabricated_refs"] = not fabricated

    # 3. Render output exists
    if criteria.get("render_output_exists", True):
        render_dir = workspace / "outputs" / "render"
        docx_files = list(render_dir.glob("*.docx")) if render_dir.exists() else []
        checks["render_output_exists"] = len(docx_files) > 0
        if docx_files:
            size = docx_files[0].stat().st_size
            checks["render_output_exists"] = size > 1000  # Non-trivial
            result.notes.append(f"Render output: {docx_files[0].name} ({size} bytes)")

    # 4. DOCX integrity (ZIP with word/document.xml)
    if criteria.get("docx_integrity", True):
        render_dir = workspace / "outputs" / "render"
        docx_files = list(render_dir.glob("*.docx")) if render_dir.exists() else []
        if docx_files:
            import zipfile

            try:
                with zipfile.ZipFile(docx_files[0]) as zf:
                    checks["docx_integrity"] = "word/document.xml" in zf.namelist()
            except Exception:
                checks["docx_integrity"] = False
        else:
            checks["docx_integrity"] = False

    return checks


def compute_verdict(
    result: ValidationResult,
    manifest: dict[str, Any],
) -> str:
    """Compute the final verdict based on stages and acceptance."""
    # All stages must succeed
    failed_stages = [s for s in result.stages if not s.success and not s.skipped]
    if failed_stages:
        result.notes.append(
            f"Failed stages: {', '.join(s.name for s in failed_stages)}"
        )
        return VERDICT_FAIL

    # All acceptance criteria must pass
    failed_checks = [k for k, v in result.acceptance.items() if not v]
    if failed_checks:
        result.notes.append(
            f"Failed acceptance: {', '.join(failed_checks)}"
        )
        return VERDICT_FAIL

    # Degraded mode?
    degraded_stages = [s for s in result.stages if s.degraded]
    if degraded_stages:
        for s in degraded_stages:
            result.degraded_warnings.append(f"{s.name}: {s.degraded_reason}")

    # Manual review required?
    if manifest.get("manual_review", {}).get("required", False):
        if degraded_stages:
            return VERDICT_DEGRADED
        return VERDICT_MANUAL

    return VERDICT_PASS


# ── Report generation ──────────────────────────────────────────────────────


def generate_report(result: ValidationResult) -> str:
    """Generate a Markdown report from the validation result."""
    lines: list[str] = []

    lines.append(f"# Phase 6 Validation Report — {result.case_id}")
    lines.append("")
    lines.append(f"**Title:** {result.title}")
    lines.append(f"**Manifest:** `{result.manifest_path}`")
    lines.append(f"**Workspace:** `{result.workspace}`")
    lines.append(f"**Started:** {result.started_at}")
    lines.append(f"**Finished:** {result.finished_at}")
    lines.append(f"**Duration:** {result.duration_s:.1f}s")
    lines.append("")

    # Verdict banner
    verdict_emoji = {
        VERDICT_PASS: "✅",
        VERDICT_DEGRADED: "⚠️",
        VERDICT_MANUAL: "📋",
        VERDICT_FAIL: "❌",
    }
    lines.append(f"## Verdict: {verdict_emoji.get(result.verdict, '?')} {result.verdict}")
    lines.append("")

    # Stage results
    lines.append("## Pipeline Stages")
    lines.append("")
    lines.append("| Stage | Command | Status | Duration | Notes |")
    lines.append("|-------|---------|--------|----------|-------|")
    for s in result.stages:
        if s.skipped:
            status = "⏭️ skipped"
        elif s.degraded:
            status = "⚠️ degraded"
        elif s.success:
            status = "✅ pass"
        else:
            status = f"❌ fail (exit {s.exit_code})"
        notes = s.degraded_reason if s.degraded else ""
        lines.append(f"| {s.name} | `{s.command}` | {status} | {s.duration_s}s | {notes} |")
    lines.append("")

    # Acceptance
    if result.acceptance:
        lines.append("## Acceptance Criteria")
        lines.append("")
        for k, v in result.acceptance.items():
            mark = "✅" if v else "❌"
            lines.append(f"- {mark} `{k}`")
        lines.append("")

    # Degraded warnings
    if result.degraded_warnings:
        lines.append("## Degraded-Mode Warnings")
        lines.append("")
        for w in result.degraded_warnings:
            lines.append(f"- ⚠️ {w}")
        lines.append("")

    # Manual review checklist
    lines.append("## Manual Review Checklist")
    lines.append("")
    checklist = load_manifest_checklist(result.manifest_path)
    if checklist:
        for item in checklist:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("- [ ] DOCX opens successfully")
        lines.append("- [ ] Citations formatted correctly")
        lines.append("- [ ] No fabricated references")
    lines.append("")

    # Notes
    if result.notes:
        lines.append("## Notes")
        lines.append("")
        for n in result.notes:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines)


def load_manifest_checklist(manifest_path: str) -> list[str]:
    """Extract manual review checklist items from manifest."""
    try:
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
        items = data.get("manual_review", {}).get("checklist", [])
        if isinstance(items, list):
            return [
                i if isinstance(i, str) else i.get("item", str(i))
                for i in items
            ]
    except Exception:
        pass
    return []


# ── Main runner ────────────────────────────────────────────────────────────


def run_validation(
    manifest_path: Path,
    dry_run: bool = False,
    keep_workspace: bool = False,
    tmp_root: Path | None = None,
) -> ValidationResult:
    """Execute the full validation pipeline for a given manifest."""
    manifest = load_manifest(manifest_path)
    bib_path = resolve_bib_path(manifest)

    started = datetime.now(timezone.utc)
    result = ValidationResult(
        case_id=manifest["case_id"],
        title=manifest["title"],
        manifest_path=str(manifest_path),
        workspace="",
        started_at=started.isoformat(),
    )

    if dry_run:
        result.notes.append("DRY RUN — no stages executed")
        result.workspace = "(dry run)"
        result.verdict = VERDICT_MANUAL
        finished = datetime.now(timezone.utc)
        result.finished_at = finished.isoformat()
        result.duration_s = (finished - started).total_seconds()
        return result

    # Validate source exists (after dry_run so manifest structure is checked first)
    pdf_path = Path(manifest["source_material"]["pdf_path"])
    if not pdf_path.exists():
        print(
            f"ERROR: source PDF not found: {pdf_path}",
            file=sys.stderr,
        )
        print(
            "The validation runner requires the source file to exist at the "
            "declared path. Place the file or update the manifest.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Validate bib exists if required
    if bib_path and not Path(bib_path).exists():
        print(f"ERROR: bibliography not found: {bib_path}", file=sys.stderr)
        sys.exit(2)

    # Prepare isolated workspace
    workspace = prepare_workspace(manifest, tmp_root=tmp_root)
    result.workspace = str(workspace)

    if not keep_workspace:
        # Register cleanup (but allow inspection on failure)
        import atexit

        def _cleanup() -> None:
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)

        atexit.register(_cleanup)

    # Execute stages
    stages = manifest.get("stages", [])
    for stage_def in stages:
        sr = run_stage(workspace, stage_def, bib_path)
        result.stages.append(sr)
        print(
            f"  [{sr.name}] {'✅' if sr.success else '❌'} "
            f"({sr.duration_s}s)"
            f"{' [degraded]' if sr.degraded else ''}"
            f"{' [skipped]' if sr.skipped else ''}"
        )
        if not sr.success and not sr.degraded:
            print(f"    stderr: {sr.stderr[:200]}", file=sys.stderr)
            # Stop pipeline on hard failure
            break

    # Acceptance checks
    result.acceptance = check_acceptance(result, manifest, workspace)

    # Compute verdict
    result.verdict = compute_verdict(result, manifest)

    finished = datetime.now(timezone.utc)
    result.finished_at = finished.isoformat()
    result.duration_s = (finished - started).total_seconds()

    # Write report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{manifest['case_id']}.md"
    report_md = generate_report(result)
    report_path.write_text(report_md)

    # Also write structured JSON
    json_path = REPORTS_DIR / f"{manifest['case_id']}.json"
    json_data = {
        "case_id": result.case_id,
        "title": result.title,
        "verdict": result.verdict,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "duration_s": result.duration_s,
        "workspace": result.workspace,
        "stages": [
            {
                "name": s.name,
                "command": s.command,
                "success": s.success,
                "exit_code": s.exit_code,
                "duration_s": s.duration_s,
                "degraded": s.degraded,
                "degraded_reason": s.degraded_reason,
                "skipped": s.skipped,
            }
            for s in result.stages
        ],
        "acceptance": result.acceptance,
        "degraded_warnings": result.degraded_warnings,
        "notes": result.notes,
    }
    json_path.write_text(json.dumps(json_data, indent=2))

    print(f"\nReport: {report_path}")
    print(f"JSON:   {json_path}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 6 — Real Material Validation Runner",
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to validation manifest (.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manifest without executing pipeline",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Do not delete the temporary workspace after run",
    )
    args = parser.parse_args()

    print("Phase 6 — Real Material Validation")
    print(f"Manifest: {args.manifest}")
    print(f"Mode: {'dry-run' if args.dry_run else 'live'}")
    print("")

    result = run_validation(
        manifest_path=args.manifest,
        dry_run=args.dry_run,
        keep_workspace=args.keep_workspace,
    )

    print(f"\nVerdict: {result.verdict}")
    sys.exit(0 if result.verdict in (VERDICT_PASS, VERDICT_DEGRADED) else 1)


if __name__ == "__main__":
    main()
