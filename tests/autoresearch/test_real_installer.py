"""Real installer test: build wheel, install in isolated venv, run full pipeline."""
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
passed = 0
total = 0
results: list[tuple[str, bool, str]] = []


def run_step(name: str, cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> bool:
    """Run a step and record result."""
    global passed, total
    total += 1
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        ok = r.returncode == 0
        if ok:
            passed += 1
            results.append((name, True, ""))
            print(f"  PASS: {name}")
        else:
            results.append((name, False, r.stderr[:200]))
            print(f"  FAIL: {name} — {r.stderr[:150]}")
        return ok
    except Exception as e:
        results.append((name, False, str(e)[:200]))
        print(f"  FAIL: {name} — {e}")
        return False


with tempfile.TemporaryDirectory(prefix="pw-install-test-") as tmpdir:
    tmpdir = Path(tmpdir)

    # 1. Build wheel
    print("\n=== BUILD ===")
    dist_dir = tmpdir / "dist"
    dist_dir.mkdir()
    run_step(
        "build wheel",
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
        cwd=REPO,
        timeout=60,
    )

    # Find the wheel
    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        print("FATAL: No wheel built. Cannot continue.")
        print(f"METRIC installer_pipeline_steps_passed={passed}")
        sys.exit(1)
    wheel = wheels[0]
    print(f"  wheel: {wheel.name}")

    # 2. Create isolated venv
    print("\n=== INSTALL ===")
    venv_dir = tmpdir / "test-venv"
    run_step(
        "create venv",
        ["uv", "venv", str(venv_dir), "--python", "3.12"],
        timeout=30,
    )

    pip = str(venv_dir / "bin" / "pip")
    python = str(venv_dir / "bin" / "python")

    run_step(
        "install wheel",
        [pip, "install", str(wheel)],
        timeout=120,
    )

    # 3. Verify import works
    print("\n=== IMPORT CHECK ===")
    run_step(
        "import cli.paper.main",
        [python, "-c", "from cli.paper.main import main; print('OK')"],
    )
    run_step(
        "import harness.services.orchestrator_builder",
        [python, "-c", "from harness.services.orchestrator_builder import build_orchestrator_dependencies; print('OK')"],
    )
    run_step(
        "import validators.method_gate",
        [python, "-c", "from validators.method_gate import MethodGateValidator; print('OK')"],
    )

    # 4. Create paper project and run pipeline
    print("\n=== PIPELINE (paper command) ===")
    paper_dir = tmpdir / "my-paper"
    paper_dir.mkdir()

    paper_bin = str(venv_dir / "bin" / "paper")

    run_step(
        "paper --help",
        [paper_bin, "--help"],
    )

    run_step(
        "paper init",
        [paper_bin, "-C", str(paper_dir), "init"],
        timeout=15,
    )

    # Check scaffold
    has_state = (paper_dir / "outputs" / "state.yaml").exists()
    has_templates = (paper_dir / "templates").exists()
    no_source = not (paper_dir / "cli").exists()
    print(f"  scaffold: state={has_state}, templates={has_templates}, no_source_stubs={no_source}")
    if not has_state:
        results.append(("scaffold: state.yaml", False, "missing"))
        total += 1
    else:
        results.append(("scaffold: state.yaml", True, ""))
        total += 1
        passed += 1

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
        "paper validate",
        [paper_bin, "-C", str(paper_dir), "validate"],
        timeout=15,
    )

    # 5. Verify state progression
    print("\n=== STATE CHECK ===")
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

    # 6. Asset resolution check
    print("\n=== ASSET RESOLUTION ===")
    run_step(
        "get_project_asset (templates)",
        [python, "-c", "from harness.ports.assets import get_project_asset; p = get_project_asset('templates/manuscript.qmd'); print(f'OK: {p}')"],
    )

    run_step(
        "get_project_asset (csl)",
        [python, "-c", "from harness.ports.assets import get_project_asset; p = get_project_asset('styles/csl/apa.csl'); print(f'OK: {p}')"],
    )

print(f"\n{'='*50}")
print(f"RESULTS: {passed}/{total} steps passed")
print(f"METRIC installer_pipeline_steps_passed={passed}")
for name, ok, err in results:
    if not ok:
        print(f"  FAILED: {name} — {err}")
sys.exit(0 if passed == total else 1)
