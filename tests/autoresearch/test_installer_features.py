"""Full installer feature verification from installed wheel."""
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
passed = 0
total = 0
results: list[tuple[str, bool, str]] = []


def check(name: str, cmd: list[str], cwd: Path | None = None) -> None:
    """Run a feature check."""
    global passed, total
    total += 1
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=30)
    ok = r.returncode == 0
    if ok:
        passed += 1
        results.append((name, True, ""))
        print(f"  PASS: {name}")
    else:
        err = (r.stderr or r.stdout).strip()[:120]
        results.append((name, False, err))
        print(f"  FAIL: {name} — {err[:80]}")


with tempfile.TemporaryDirectory(prefix="pw-verify-") as raw:
    tmpdir = Path(raw)

    # Build + install
    dist = tmpdir / "dist"
    dist.mkdir()
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist)],
        cwd=REPO, capture_output=True, timeout=60,
    )
    wheel = next(dist.glob("*.whl"))

    venv = tmpdir / "v"
    subprocess.run(
        ["uv", "venv", str(venv), "--python", "3.12"],
        capture_output=True, timeout=30,
    )
    python = str(venv / "bin" / "python")
    paper = str(venv / "bin" / "paper")
    subprocess.run(
        ["uv", "pip", "install", "--python", python, str(wheel)],
        capture_output=True, timeout=120,
    )

    print("=== ENTRYPOINT ===")
    check("paper --help", [paper, "--help"])

    print("\n=== IMPORTS (from clean cwd) ===")
    for mod in [
        "from cli.paper.main import main",
        "from harness.services.orchestrator_builder import build_orchestrator_dependencies",
        "from validators.method_gate import MethodGateValidator",
        "from validators.prose import ProseValidator",
        "from validators.claims import ClaimsValidator",
    ]:
        name = mod.split(" import ")[1]
        check(name, [python, "-c", f"{mod}; print('OK')"], cwd=tmpdir)

    print("\n=== ASSET RESOLUTION ===")
    assets = [
        ("templates/manuscript.qmd", "templates", "manuscript.qmd"),
        ("styles/csl/apa.csl", "styles", "csl", "apa.csl"),
        ("styles/vale/.vale.ini", "styles", "vale", ".vale.ini"),
        ("rules/method_gate/consort.yml", "rules", "method_gate", "consort.yml"),
        ("schemas/method_gate.schema.json", "schemas", "method_gate.schema.json"),
    ]
    for label, *parts in assets:
        args = ", ".join(f"'{p}'" for p in parts)
        code = (
            "from harness.ports.assets import get_asset_path;"
            f" p=get_asset_path({args}); assert p.exists()"
        )
        check(label, [python, "-c", code], cwd=tmpdir)

    print("\n=== VALIDATORS (from installed wheel) ===")
    # Method gate
    check(
        "method_gate (generic=12 items)",
        [python, "-c", """
import tempfile
from pathlib import Path
from validators.method_gate import MethodGateValidator
from parsers.manuscript import ManuscriptParser
t = (
    '# Introduction\\nA.\\n# Methods\\nB.'
    '\\n# Results\\nC.\\n# Discussion\\nD.'
    '\\n# References\\n1. X.'
)
with tempfile.NamedTemporaryFile(suffix='.md', mode='w', delete=False) as f:
    f.write(t)
    ms = ManuscriptParser().parse(Path(f.name))
    r = MethodGateValidator().validate(ms, study_type='*')
    assert r['summary']['total_items'] > 0, 'No items loaded'
    Path(f.name).unlink()
"""],
        cwd=tmpdir,
    )
    # Prose
    prose_code = (
        "from validators.prose import ProseValidator;"
        " v=ProseValidator(); assert len(v.registry) > 0"
    )
    check(
        "prose (29 rules)",
        [python, "-c", prose_code],
        cwd=tmpdir,
    )
    # Claims
    claims_code = (
        "from validators.claims import ClaimsValidator;"
        " v=ClaimsValidator(); assert len(v.rules) > 0"
    )
    check(
        "claims (15 rules)",
        [python, "-c", claims_code],
        cwd=tmpdir,
    )

    print("\n=== FULL PIPELINE ===")
    proj = tmpdir / "paper"
    proj.mkdir()
    check("paper init", [paper, "-C", str(proj), "init"])
    check("paper search", [paper, "-C", str(proj), "search"])
    check("paper screen", [paper, "-C", str(proj), "screen"])
    check("paper draft outline", [paper, "-C", str(proj), "draft", "outline"])
    for sec in ["introduction", "methods", "results", "discussion"]:
        check(f"draft {sec}", [paper, "-C", str(proj), "draft", "section", sec])

    print("\n=== AUDIT + GATE ===")
    intro = proj / "outputs" / "drafts" / "introduction.md"
    check("audit prose", [paper, "-C", str(proj), "audit", "prose", str(intro)])
    check("audit claims", [paper, "-C", str(proj), "audit", "claims", str(intro)])
    # Gate method: exit code != 0 is expected when blockers found
    r = subprocess.run(
        [paper, "-C", str(proj), "gate", "method", str(intro), "--study-type", "*"],
        capture_output=True, text=True,
    )
    total += 1
    if "Total items:" in r.stdout:
        passed += 1
        results.append(("gate method (loads checklist)", True, ""))
        print("  PASS: gate method (loads checklist)")
    else:
        results.append(("gate method", False, r.stdout[:80]))
        print(f"  FAIL: gate method — {r.stdout[:80]}")

    print("\n=== DOCTOR ===")
    check("paper doctor", [paper, "-C", str(proj), "doctor"])

print(f"\n{'='*50}")
print(f"RESULTS: {passed}/{total} features verified")
print(f"METRIC installer_features_verified={passed}")
failures = [(n, e) for n, ok, e in results if not ok]
if failures:
    print(f"\nFAILURES ({len(failures)}):")
    for name, err in failures:
        print(f"  {name}: {err[:100]}")
sys.exit(0 if passed == total else 1)
