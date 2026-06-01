"""Real installer test: build wheel, install in isolated venv, run full pipeline."""
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
passed = 0
total = 0
results: list[tuple[str, bool, str]] = []


def run_step(
    name: str,
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 30,
) -> bool:
    """Run a step and record result."""
    global passed, total
    total += 1
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout,
        )
        ok = r.returncode == 0
        if ok:
            passed += 1
            results.append((name, True, ""))
            print(f"  PASS: {name}")
        else:
            err = r.stderr.strip()[:200] if r.stderr else r.stdout.strip()[:200]
            results.append((name, False, err))
            print(f"  FAIL: {name} — {err[:120]}")
        return ok
    except Exception as e:
        results.append((name, False, str(e)[:200]))
        total += 1
        print(f"  FAIL: {name} — {e}")
        return False


with tempfile.TemporaryDirectory(prefix="pw-install-") as raw_tmpdir:
    tmpdir = Path(raw_tmpdir)

    # === BUILD ===
    print("\n=== BUILD ===")
    dist_dir = tmpdir / "dist"
    dist_dir.mkdir()
    run_step(
        "build wheel",
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
        cwd=REPO,
        timeout=60,
    )

    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        print("FATAL: No wheel built.")
        print(f"METRIC installer_pipeline_steps_passed={passed}")
        sys.exit(1)
    wheel = wheels[0]
    print(f"  wheel: {wheel.name}")

    # === INSTALL ===
    print("\n=== INSTALL ===")
    venv_dir = tmpdir / "venv"
    run_step(
        "create venv",
        ["uv", "venv", str(venv_dir), "--python", "3.12"],
        timeout=30,
    )

    python = str(venv_dir / "bin" / "python")
    paper_bin = str(venv_dir / "bin" / "paper")

    # Use uv pip install (uv venv doesn't include pip)
    run_step(
        "install wheel via uv pip",
        ["uv", "pip", "install", "--python", python, str(wheel)],
        timeout=120,
    )

    # === ENTRYPOINT ===
    print("\n=== ENTRYPOINT ===")
    run_step(
        "paper --help",
        [paper_bin, "--help"],
    )

    # === IMPORT CHECK (from clean cwd, not source tree) ===
    print("\n=== IMPORT CHECK ===")
    import_check = "from cli.paper.main import main; print('OK')"
    run_step(
        "import cli.paper.main",
        [python, "-c", import_check],
        cwd=tmpdir,
    )
    import_check_ob = (
        "from harness.services.orchestrator_builder "
        "import build_orchestrator_dependencies; print('OK')"
    )
    run_step(
        "import orchestrator_builder",
        [python, "-c", import_check_ob],
        cwd=tmpdir,
    )
    import_check_mg = (
        "from validators.method_gate import MethodGateValidator; print('OK')"
    )
    run_step(
        "import validators.method_gate",
        [python, "-c", import_check_mg],
        cwd=tmpdir,
    )

    # === ASSET RESOLUTION (from clean cwd) ===
    print("\n=== ASSET RESOLUTION ===")
    asset_code = (
        "from pathlib import Path; "
        "from harness.ports.assets import get_asset_path; "
        "p = get_asset_path('templates', 'manuscript.qmd'); "
        "print(f'template={p} exists={p.exists()}')"
    )
    run_step(
        "get_asset_path (templates)",
        [python, "-c", asset_code],
        cwd=tmpdir,
    )

    csl_code = (
        "from harness.ports.assets import get_asset_path; "
        "p = get_asset_path('styles', 'csl', 'apa.csl'); "
        "print(f'csl={p} exists={p.exists()}')"
    )
    run_step(
        "get_asset_path (csl)",
        [python, "-c", csl_code],
        cwd=tmpdir,
    )

    # === FULL PIPELINE ===
    print("\n=== PIPELINE ===")
    paper_dir = tmpdir / "my-paper"
    paper_dir.mkdir()

    run_step(
        "paper init",
        [paper_bin, "-C", str(paper_dir), "init"],
        timeout=15,
    )

    # Scaffold check
    has_state = (paper_dir / "outputs" / "state.yaml").exists()
    has_templates = (paper_dir / "templates").exists()
    no_source = not (paper_dir / "cli").exists() and not (paper_dir / "harness").exists()
    total += 1
    if has_state and has_templates and no_source:
        passed += 1
        results.append(("scaffold: state+templates, no source stubs", True, ""))
        print("  PASS: scaffold check")
    else:
        msg = f"state={has_state} tmpl={has_templates} no_src={no_source}"
        results.append(("scaffold check", False, msg))
        print(f"  FAIL: scaffold — {msg}")

    run_step(
        "paper search",
        [paper_bin, "-C", str(paper_dir), "search"],
        timeout=15,
    )
    run_step(
        "paper screen",
        [paper_bin, "-C", str(paper_dir), "screen"],
        timeout=15,
    )
    run_step(
        "paper draft outline",
        [paper_bin, "-C", str(paper_dir), "draft", "outline"],
        timeout=15,
    )
    for sec in ["introduction", "methods", "results", "discussion"]:
        run_step(
            f"paper draft section {sec}",
            [paper_bin, "-C", str(paper_dir), "draft", "section", sec],
            timeout=15,
        )
    run_step(
        "paper check refs",
        [paper_bin, "-C", str(paper_dir), "check", "refs"],
        timeout=15,
    )

    # === FINAL STATE ===
    print("\n=== STATE ===")
    r = subprocess.run(
        [python, "-c", f"""
import yaml
state = yaml.safe_load(open('{paper_dir}/outputs/state.yaml'))
print(f"stage={{state['stage']}}")
gates = state.get('gates', {{}})
passed_gates = sum(1 for v in gates.values() if v)
print(f"gates={{passed_gates}}/{{len(gates)}}")
"""],
        capture_output=True, text=True,
    )
    print(f"  {r.stdout.strip()}")

print(f"\n{'='*50}")
print(f"RESULTS: {passed}/{total} steps passed")
print(f"METRIC installer_pipeline_steps_passed={passed}")
failures = [(n, e) for n, ok, e in results if not ok]
if failures:
    print(f"\nFAILURES ({len(failures)}):")
    for name, err in failures:
        print(f"  {name}: {err[:100]}")
sys.exit(0 if passed == total else 1)
