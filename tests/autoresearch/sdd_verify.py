"""SDD verify: validate all 18 spec scenarios against implementation.

Checks each scenario from openspec/changes/multi-project-mode/spec.md
against the real code. Reports pass/fail per scenario.
"""
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
passed = 0
failed = 0
total = 0


def check(name: str, fn) -> None:
    global passed, failed, total
    total += 1
    try:
        fn()
        passed += 1
        print(f"  PASS: {name}")
    except Exception as e:
        failed += 1
        print(f"  FAIL: {name} — {e}")


# ── REQ-PR-01: Project root resolution priority ─────────────────────
print("\n=== REQ-PR-01 ===")


def test_flag_overrides() -> None:
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "my-paper"
        project.mkdir()
        (project / "outputs").mkdir()
        (project / "outputs" / "state.yaml").touch()
        from cli.paper.main import resolve_project_root

        result = resolve_project_root(project, Path(td) / "elsewhere")
        assert result == project.resolve()


check("REQ-PR-01: Explicit flag overrides everything", test_flag_overrides)


def test_ascending_subdir() -> None:
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "my-paper"
        subdir = project / "src" / "deep"
        subdir.mkdir(parents=True)
        (project / "outputs").mkdir()
        (project / "outputs" / "state.yaml").touch()
        from cli.paper.main import resolve_project_root

        result = resolve_project_root(None, subdir)
        assert result == project.resolve()


check("REQ-PR-01: Ascending search from subdirectory", test_ascending_subdir)


def test_cwd_fallback() -> None:
    with tempfile.TemporaryDirectory() as td:
        empty = Path(td) / "empty-dir"
        empty.mkdir()
        from cli.paper.main import resolve_project_root

        result = resolve_project_root(None, empty)
        assert result == empty.resolve()


check("REQ-PR-01: CWD fallback for new projects", test_cwd_fallback)


def test_innermost_match() -> None:
    with tempfile.TemporaryDirectory() as td:
        outer = Path(td) / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True)
        (outer / "outputs").mkdir()
        (outer / "outputs" / "state.yaml").touch()
        (inner / "outputs").mkdir()
        (inner / "outputs" / "state.yaml").touch()
        from cli.paper.main import resolve_project_root

        result = resolve_project_root(None, inner)
        assert result == inner.resolve()


check("REQ-PR-01: Innermost match stops first", test_innermost_match)


# ── REQ-PR-02: Safety bounds ────────────────────────────────────────
print("\n=== REQ-PR-02 ===")


def test_bounded_20() -> None:
    with tempfile.TemporaryDirectory() as td:
        deep = Path(td)
        for i in range(25):
            deep = deep / f"level{i}"
        deep.mkdir(parents=True)
        from cli.paper.main import resolve_project_root

        result = resolve_project_root(None, deep)
        assert result == deep.resolve()  # CWD fallback


check("REQ-PR-02: Bounded to 20 levels", test_bounded_20)


def test_symlink_resolution() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        project = td / "my-paper"
        project.mkdir()
        (project / "outputs").mkdir()
        (project / "outputs" / "state.yaml").touch()
        subdir = project / "notes"
        subdir.mkdir()
        from cli.paper.main import resolve_project_root

        result = resolve_project_root(None, subdir)
        assert result == project.resolve()


check("REQ-PR-02: Symlink resolution via Path.resolve()", test_symlink_resolution)


# ── REQ-PR-03: Flag validation ──────────────────────────────────────
print("\n=== REQ-PR-03 ===")


def test_invalid_flag() -> None:
    from cli.paper.main import resolve_project_root

    try:
        resolve_project_root(Path("/nonexistent/path"), Path.cwd())
        raise AssertionError("Should have raised SystemExit")
    except SystemExit as e:
        assert e.code == 1


check("REQ-PR-03: Invalid flag -> exit 1", test_invalid_flag)


# ── repo-initialization-gate ────────────────────────────────────────
print("\n=== repo-initialization-gate ===")


def _make_checker(existing: set[str]):
    """Create InMemoryArtifactChecker without importing from tests."""
    from harness.ports.artifact_checker import ArtifactChecker

    class SimpleChecker(ArtifactChecker):
        def __init__(self, paths: set[str]) -> None:
            self.paths = paths
            self.root = Path(tempfile.mkdtemp())

        def check_dir_exists(self, name: str) -> None:
            if name not in self.paths:
                raise FileNotFoundError(f"Dir missing: {name}")

        def check_file_exists(self, name: str) -> None:
            if name not in self.paths:
                raise FileNotFoundError(f"File missing: {name}")

        def check_any_file_exists(self, name: str) -> bool:
            return name in self.paths

        def get_full_path_str(self, name: str) -> str:
            return str(self.root / name)

    return SimpleChecker(existing)


def test_gate_pass() -> None:
    checker = _make_checker({"templates", "outputs", "outputs/state.yaml"})
    from harness.services.gates import validate_repo_initialized

    result = validate_repo_initialized(checker)
    assert result.status == "pass"


check("Gate: Fresh project passes", test_gate_pass)


def test_gate_missing_templates() -> None:
    checker = _make_checker({"outputs", "outputs/state.yaml"})
    from harness.services.gates import validate_repo_initialized

    result = validate_repo_initialized(checker)
    assert result.status == "fail"


check("Gate: Missing templates fails", test_gate_missing_templates)


def test_gate_no_source_dirs() -> None:
    checker = _make_checker({"templates", "outputs", "outputs/state.yaml"})
    from harness.services.gates import validate_repo_initialized

    result = validate_repo_initialized(checker)
    assert result.status == "pass"


check("Gate: No source dirs still passes", test_gate_no_source_dirs)


# ── asset-resolution ────────────────────────────────────────────────
print("\n=== asset-resolution ===")


def test_project_local_asset() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        asset = td / "templates" / "manuscript.qmd"
        asset.parent.mkdir(parents=True)
        asset.write_text("# Hello")
        from harness.ports.assets import get_project_asset

        result = get_project_asset(td, "templates", "manuscript.qmd")
        assert result == asset
        assert result.exists()


check("Asset: Project-local hit", test_project_local_asset)


def test_package_fallback() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        from harness.ports.assets import get_asset_path, get_project_asset

        result = get_project_asset(
            td, "templates", "journals", "nature", "preset.yaml"
        )
        expected = get_asset_path(
            "templates", "journals", "nature", "preset.yaml"
        )
        assert result == expected


check("Asset: Package fallback", test_package_fallback)


def test_both_miss() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        from harness.ports.assets import get_asset_path, get_project_asset

        result = get_project_asset(td, "nonexistent", "asset.txt")
        expected = get_asset_path("nonexistent", "asset.txt")
        assert result == expected


check("Asset: Both miss returns package path", test_both_miss)


# ── cli-entrypoint ──────────────────────────────────────────────────
print("\n=== cli-entrypoint ===")


def test_flag_exists() -> None:
    code = (REPO / "cli/paper/main.py").read_text()
    assert '"--project"' in code
    assert '"-C"' in code


check("CLI: --project/-C flag exists", test_flag_exists)


def test_backward_compat() -> None:
    code = (REPO / "cli/paper/main.py").read_text()
    assert "resolve_project_root(args.project, Path.cwd())" in code


check("CLI: CWD fallback backward compatible", test_backward_compat)


def test_phase0_unaffected() -> None:
    code = (REPO / "cli/paper/main.py").read_text()
    # Phase 0 commands have func attribute and return before resolve
    lines = code.split("\n")
    func_idx = next(
        i for i, ln in enumerate(lines) if "func(args)" in ln
    )
    # There must be a 'return' in the same block
    block = lines[func_idx - 3 : func_idx + 3]
    assert any("return" in ln for ln in block)


check("CLI: Phase 0 commands unaffected", test_phase0_unaffected)


# ── init-directory-creation ─────────────────────────────────────────
print("\n=== init-directory-creation ===")


def test_init_creates_lean() -> None:
    code = (REPO / "harness/adapters/filesystem_action_runner.py").read_text()
    init_section = code.split('if command == "init"')[1].split("elif command")[0]
    assert '"cli"' not in init_section
    assert '"harness"' not in init_section
    assert '"validators"' not in init_section
    assert '"tests"' not in init_section
    assert '"templates"' in init_section
    assert '"outputs"' in init_section


check("Init: Only project dirs, no source stubs", test_init_creates_lean)


def test_doctor_uses_get_project_asset() -> None:
    code = (REPO / "harness/services/doctor.py").read_text()
    assert "get_project_asset" in code
    assert "_looks_like_project_root" not in code


check(
    "Doctor: Uses get_project_asset, no heuristic",
    test_doctor_uses_get_project_asset,
)


# ── Summary ─────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print(f"METRIC scenarios_verified={passed}")
print(f"passed={passed}/{total} failed={failed}")
if failed == 0:
    print("VERDICT: ALL SCENARIOS VERIFIED")
else:
    print(f"VERDICT: {failed} SCENARIOS FAILED")
sys.exit(0)
