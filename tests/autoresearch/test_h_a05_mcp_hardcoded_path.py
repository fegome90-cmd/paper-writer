"""H-A05: MCP hardcoded absolute path is fragile.

CONFIRMED BUG: _DEFAULT_SERVER_PATH contains a personal absolute path
that breaks on any other machine. These tests verify the fix.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDefaultPathNotPersonal:
    """_DEFAULT_SERVER_PATH must NOT contain a personal absolute path."""

    def test_default_path_not_personal_absolute(self) -> None:
        from integrations.tools.mcp_paper_client import _DEFAULT_SERVER_PATH

        assert "/Users/felipe_gonzalez" not in _DEFAULT_SERVER_PATH, (
            f"_DEFAULT_SERVER_PATH contains personal absolute path: {_DEFAULT_SERVER_PATH!r}"
        )

    def test_default_path_not_hardcoded_home(self) -> None:
        from integrations.tools.mcp_paper_client import _DEFAULT_SERVER_PATH

        assert not _DEFAULT_SERVER_PATH.startswith("/Users/"), (
            f"_DEFAULT_SERVER_PATH starts with /Users/: {_DEFAULT_SERVER_PATH!r}"
        )


class TestMissingPathClearError:
    """When no valid path is configured, error must be clear and actionable."""

    def test_missing_env_and_no_default_gives_clear_error(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            env = os.environ.copy()
            env.pop("PAPER_MCP_SERVER_PATH", None)
            with patch.dict("os.environ", env, clear=True):
                from integrations.tools.mcp_paper_client import McpPaperSearchProvider

                with pytest.raises(RuntimeError, match="PAPER_MCP_SERVER_PATH"):
                    McpPaperSearchProvider()

    def test_does_not_silently_proceed(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            env = os.environ.copy()
            env.pop("PAPER_MCP_SERVER_PATH", None)
            with patch.dict("os.environ", env, clear=True):
                from integrations.tools.mcp_paper_client import McpPaperSearchProvider

                with pytest.raises(RuntimeError):
                    McpPaperSearchProvider()


class TestEnvVarOverridesDefault:
    """PAPER_MCP_SERVER_PATH env var must take precedence."""

    def test_env_var_used_over_default(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False) as tmp:
            tmp.write(b"// test server")
            tmp_path = tmp.name

        try:
            with patch.dict("os.environ", {"PAPER_MCP_SERVER_PATH": tmp_path}):
                from integrations.tools.mcp_paper_client import McpPaperSearchProvider

                provider = McpPaperSearchProvider()
                assert provider._server_path == tmp_path
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_explicit_server_path_overrides_env(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False) as tmp:
            tmp.write(b"// test server")
            tmp_path = tmp.name

        try:
            with patch.dict("os.environ", {"PAPER_MCP_SERVER_PATH": "/env/path/server.js"}):
                from integrations.tools.mcp_paper_client import McpPaperSearchProvider

                provider = McpPaperSearchProvider(server_path=tmp_path)
                assert provider._server_path == tmp_path
        finally:
            Path(tmp_path).unlink(missing_ok=True)
