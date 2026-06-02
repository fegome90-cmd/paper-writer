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
