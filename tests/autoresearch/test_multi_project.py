"""Tests for resolve_project_root() and get_project_asset().

RED phase: these tests verify the multi-project-mode spec.
- REQ-PR-01: flag → ascending → CWD priority
- REQ-PR-02: bounded ascending search with symlink resolution
- REQ-PR-03: invalid flag → exit 1
- Asset resolution: project-local → package fallback
"""

from pathlib import Path

import pytest

# ── resolve_project_root ─────────────────────────────────────────────


class TestResolveProjectRoot:
    """REQ-PR-01, PR-02, PR-03."""

    def test_explicit_flag_overrides_all(self, tmp_path: Path) -> None:
        """Flag value returned directly."""
        project = tmp_path / "my-paper"
        project.mkdir()
        (project / "outputs").mkdir()
        (project / "outputs" / "state.yaml").touch()

        from cli.paper.main import resolve_project_root

        result = resolve_project_root(project, tmp_path / "elsewhere")
        assert result == project

    def test_ascending_from_subdir(self, tmp_path: Path) -> None:
        """Walking up finds nearest state.yaml."""
        project = tmp_path / "my-paper"
        subdir = project / "src" / "deep"
        subdir.mkdir(parents=True)
        (project / "outputs").mkdir()
        (project / "outputs" / "state.yaml").touch()

        from cli.paper.main import resolve_project_root

        result = resolve_project_root(None, subdir)
        assert result == project

    def test_cwd_fallback_no_state_yaml(self, tmp_path: Path) -> None:
        """No state.yaml anywhere → CWD returned."""
        empty = tmp_path / "empty-dir"
        empty.mkdir()

        from cli.paper.main import resolve_project_root

        result = resolve_project_root(None, empty)
        assert result == empty

    def test_innermost_match(self, tmp_path: Path) -> None:
        """Stops at FIRST state.yaml (innermost), like git."""
        outer = tmp_path / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True)
        (outer / "outputs").mkdir()
        (outer / "outputs" / "state.yaml").touch()
        (inner / "outputs").mkdir()
        (inner / "outputs" / "state.yaml").touch()

        from cli.paper.main import resolve_project_root

        result = resolve_project_root(None, inner)
        assert result == inner

    def test_ascending_bounded_to_20_levels(self, tmp_path: Path) -> None:
        """Search stops after 20 parent dirs."""
        deep = tmp_path
        for i in range(25):
            deep = deep / f"level{i}"
        deep.mkdir(parents=True)

        from cli.paper.main import resolve_project_root

        result = resolve_project_root(None, deep)
        # No state.yaml found → CWD fallback
        assert result == deep

    def test_invalid_flag_path_exits(self, tmp_path: Path) -> None:
        """REQ-PR-03: non-existent flag path → SystemExit(1)."""
        from cli.paper.main import resolve_project_root

        with pytest.raises(SystemExit) as exc_info:
            resolve_project_root(tmp_path / "nonexistent", tmp_path)
        assert exc_info.value.code == 1


# ── get_project_asset ────────────────────────────────────────────────


class TestGetProjectAsset:
    """Asset waterfall: project-local first → package fallback."""

    def test_project_local_hit(self, tmp_path: Path) -> None:
        """Project has the file → return project path."""
        asset = tmp_path / "templates" / "manuscript.qmd"
        asset.parent.mkdir(parents=True)
        asset.write_text("# Hello")

        from harness.ports.assets import get_project_asset

        result = get_project_asset(tmp_path, "templates", "manuscript.qmd")
        assert result == asset
        assert result.exists()

    def test_project_miss_package_fallback(self, tmp_path: Path) -> None:
        """Project missing file → return package path (may not exist)."""
        from harness.ports.assets import get_asset_path, get_project_asset

        result = get_project_asset(tmp_path, "templates", "journals", "nature", "preset.yaml")
        expected = get_asset_path("templates", "journals", "nature", "preset.yaml")
        assert result == expected

    def test_both_miss_returns_package_path(self, tmp_path: Path) -> None:
        """Neither project nor package has it → package path (caller checks)."""
        from harness.ports.assets import get_asset_path, get_project_asset

        result = get_project_asset(tmp_path, "nonexistent", "asset.txt")
        expected = get_asset_path("nonexistent", "asset.txt")
        assert result == expected
