import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.adapters.local_tool_resolver import LocalToolResolver
from harness.ports.tool_resolver import ToolResolution


@pytest.fixture
def repo_root(tmp_path):
    return tmp_path


@pytest.fixture
def resolver(repo_root):
    return LocalToolResolver(repo_path=repo_root)


def test_resolve_from_env_var(resolver, repo_root):
    """Test resolution via environment variable override."""
    fake_path = repo_root / "fake_bin"
    fake_path.touch(mode=0o755)

    env_map = {"PANDOC_BIN": str(fake_path)}

    with patch.dict(os.environ, env_map):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="3.1.0\n")

            res = resolver.resolve("pandoc")

            assert res is not None
            assert res.path == fake_path
            assert res.version == "3.1.0"
            assert res.source == "env"


def test_resolve_local_toolchain(resolver, repo_root):
    """Test resolution via local toolchain (tools/node/...)."""
    local_bin_dir = repo_root / "tools" / "node" / "node_modules" / ".bin"
    local_bin_dir.mkdir(parents=True)
    fake_path = local_bin_dir / "bibtex-tidy"
    fake_path.touch(mode=0o755)

    with patch.dict(os.environ, {}, clear=True):
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="1.12.0\n")

                res = resolver.resolve("bibtex-tidy")

                assert res is not None
                assert res.path == fake_path
                assert res.version == "1.12.0"
                assert res.source == "local"


def test_resolve_global_path(resolver, repo_root):
    """Test resolution via global PATH (shutil.which)."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("shutil.which", return_value="/usr/bin/vale"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="3.0.0\n")

                res = resolver.resolve("vale")

                assert res is not None
                assert str(res.path) == "/usr/bin/vale"
                assert res.source == "global"


def test_resolve_version_too_old(resolver, repo_root):
    """Test that resolve returns None if version is below minimum."""
    with patch("shutil.which", return_value="/usr/bin/pandoc"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="2.19.0\n")

            # min_version 3.0.0, found 2.19.0
            res = resolver.resolve("pandoc", min_version="3.0.0")

            assert res is None


def test_resolve_not_found(resolver):
    """Test that resolve returns None if tool not found anywhere."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("shutil.which", return_value=None):
            res = resolver.resolve("unknown-tool")
            assert res is None


def test_build_resolution_nonzero_exit(resolver, repo_root) -> None:
    """_build_resolution returns None when tool returns non-zero."""
    fake_path = repo_root / "fake"
    fake_path.touch(mode=0o755)
    with patch.dict(os.environ, {"MYTOOL_BIN": str(fake_path)}):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            res = resolver.resolve("mytool")
            assert res is None


def test_build_resolution_timeout(resolver, repo_root) -> None:
    """_build_resolution returns None on subprocess timeout."""
    fake_path = repo_root / "fake"
    fake_path.touch(mode=0o755)
    with patch.dict(os.environ, {"MYTOOL_BIN": str(fake_path)}):
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="fake", timeout=5)
        ):
            res = resolver.resolve("mytool")
            assert res is None


def test_build_resolution_oserror(resolver, repo_root) -> None:
    """_build_resolution returns None on OSError."""
    fake_path = repo_root / "fake"
    fake_path.touch(mode=0o755)
    with patch.dict(os.environ, {"MYTOOL_BIN": str(fake_path)}):
        with patch("subprocess.run", side_effect=OSError("permission denied")):
            res = resolver.resolve("mytool")
            assert res is None


def test_build_resolution_unexpected_exception(resolver, repo_root) -> None:
    """_build_resolution returns None on unexpected exception."""
    fake_path = repo_root / "fake"
    fake_path.touch(mode=0o755)
    with patch.dict(os.environ, {"MYTOOL_BIN": str(fake_path)}):
        with patch("subprocess.run", side_effect=RuntimeError("unexpected")):
            res = resolver.resolve("mytool")
            assert res is None


def test_parse_version_two_part() -> None:
    """_parse_version handles two-part versions like '1.11'."""
    result = LocalToolResolver._parse_version("1.11")
    assert result == (1, 11, 0)


def test_parse_version_full_semver() -> None:
    """_parse_version handles full semver."""
    result = LocalToolResolver._parse_version("2.3.14")
    assert result == (2, 3, 14)


def test_parse_version_with_prefix() -> None:
    """_parse_version extracts semver from prefixed string."""
    result = LocalToolResolver._parse_version("pandoc 3.1.0\n")
    assert result == (3, 1, 0)


def test_parse_version_no_match() -> None:
    """_parse_version returns None for non-version strings."""
    result = LocalToolResolver._parse_version("not-a-version")
    assert result is None


def test_verify_min_version_none_res() -> None:
    """_verify_min_version returns False for None resolution."""
    r = LocalToolResolver(Path("/tmp"))
    assert r._verify_min_version(None, "1.0.0") is False


def test_verify_min_version_no_min() -> None:
    """_verify_min_version returns True when no min_version required."""
    r = LocalToolResolver(Path("/tmp"))
    res = ToolResolution(path=Path("/usr/bin/pandoc"), version="3.0.0", source="global")
    assert r._verify_min_version(res, None) is True
