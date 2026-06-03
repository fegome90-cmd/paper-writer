"""Tests for Trifecta subprocess wrapper (clients/trifecta.py).

These tests verify graceful degradation: paper-writer must not fail if Trifecta
is unavailable, slow, or returns errors. The wrapper provides a safe interface
for using Trifecta as a subprocess client.

Strict TDD: these tests were written FIRST, before the implementation.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from clients.trifecta import (
    TrifectaClient,
    get_trifecta_client,
)


class TestTrifectaClientInit:
    """Client initialization and configuration."""

    def test_client_creates_with_repo_path(self, tmp_path: Path) -> None:
        """Client accepts a repo path."""
        client = TrifectaClient(repo_path=tmp_path)
        assert client.repo_path == tmp_path

    def test_client_uses_cwd_by_default(self) -> None:
        """Client defaults to current working directory."""
        client = TrifectaClient()
        assert client.repo_path == Path.cwd()

    def test_client_has_configurable_timeout(self, tmp_path: Path) -> None:
        """Client accepts a timeout parameter (default 5s)."""
        client = TrifectaClient(repo_path=tmp_path, timeout=10.0)
        assert client.timeout == 10.0

    def test_client_default_timeout_is_5_seconds(self, tmp_path: Path) -> None:
        """Default timeout is 5 seconds (graceful degradation)."""
        client = TrifectaClient(repo_path=tmp_path)
        assert client.timeout == 5.0

    def test_mode_off_returns_none(self, tmp_path: Path) -> None:
        """When MCP_TRIFECTA_MODE=off, factory returns None."""
        with patch.dict("os.environ", {"MCP_TRIFECTA_MODE": "off"}):
            client = get_trifecta_client(repo_path=tmp_path)
        assert client is None

    def test_mode_real_returns_client(self, tmp_path: Path) -> None:
        """When MCP_TRIFECTA_MODE=real, factory returns a TrifectaClient."""
        with patch.dict("os.environ", {"MCP_TRIFECTA_MODE": "real"}):
            client = get_trifecta_client(repo_path=tmp_path)
        assert client is not None
        assert isinstance(client, TrifectaClient)


class TestTrifectaGracefulDegradation:
    """Client must not crash paper-writer when Trifecta is unavailable."""

    def test_unavailable_returns_empty_result(self, tmp_path: Path) -> None:
        """When Trifecta CLI is not installed, find_orphans returns empty list."""
        client = TrifectaClient(repo_path=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError("trifecta not found")):
            result = client.find_orphans()
        assert result.success is False
        assert result.data == []
        assert "not found" in result.error.lower()

    def test_timeout_returns_empty_result(self, tmp_path: Path) -> None:
        """When Trifecta CLI times out, find_orphans returns empty list."""
        client = TrifectaClient(repo_path=tmp_path, timeout=0.1)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("trifecta", 0.1)):
            result = client.find_orphans()
        assert result.success is False
        assert result.data == []
        assert "timeout" in result.error.lower()

    def test_called_process_error_returns_empty_result(self, tmp_path: Path) -> None:
        """When Trifecta CLI returns non-zero, find_orphans returns empty list."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 1
        mock.stderr = "graph not indexed"
        with patch("subprocess.run", return_value=mock):
            result = client.find_orphans()
        assert result.success is False
        assert result.data == []

    def test_json_decode_error_returns_empty_result(self, tmp_path: Path) -> None:
        """When Trifecta returns invalid JSON, find_orphans returns empty list."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = "not valid json {"
        with patch("subprocess.run", return_value=mock):
            result = client.find_orphans()
        assert result.success is False
        assert result.data == []


class TestTrifectaSuccessPath:
    """Client must return parsed data on success."""

    def test_find_orphans_parses_json(self, tmp_path: Path) -> None:
        """When Trifecta returns valid JSON, find_orphans parses it."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps(
            {
                "status": "ok",
                "orphans": [
                    {
                        "id": "x",
                        "symbol_name": "foo",
                        "qualified_name": "foo",
                        "kind": "function",
                        "file_rel": "a.py",
                    }
                ],
            }
        )
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_orphans()
        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["symbol_name"] == "foo"

    def test_find_callers_parses_json(self, tmp_path: Path) -> None:
        """find_callers parses Trifecta's callers JSON output."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps(
            {
                "status": "ok",
                "callers": [{"symbol": "main", "file_rel": "cli.py"}],
            }
        )
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_callers("Foo.bar")
        assert result.success is True
        assert len(result.data) == 1

    def test_health_returns_status(self, tmp_path: Path) -> None:
        """health() returns Trifecta's status info."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps(
            {
                "status": "ok",
                "node_count": 1000,
                "edge_count": 1500,
            }
        )
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.health()
        assert result.success is True
        assert result.data["node_count"] == 1000

    def test_find_callers_parses_nodes_key(self, tmp_path: Path) -> None:
        """find_callers handles Trifecta's 'nodes' key (newer CLI versions)."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps(
            {
                "status": "ok",
                "nodes": [{"symbol_name": "main", "file_rel": "cli.py"}],
            }
        )
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_callers("Foo.bar")
        assert result.success is True
        assert len(result.data) == 1

    def test_find_callees_parses_nodes_key(self, tmp_path: Path) -> None:
        """find_callees handles Trifecta's 'nodes' key."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps(
            {
                "status": "ok",
                "nodes": [{"symbol_name": "validate", "file_rel": "validators.py"}],
            }
        )
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_callees("Foo")
        assert result.success is True
        assert len(result.data) == 1


class TestTrifectaCommand:
    """Verify the subprocess command is correct."""

    def test_find_orphans_uses_json_flag(self, tmp_path: Path) -> None:
        """find_orphans calls trifecta with --json flag."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps({"orphans": []})
        with patch("subprocess.run", return_value=mock) as run:
            client.find_orphans()
        call_args = run.call_args[0][0]
        assert "trifecta" in call_args[0]
        assert "graph" in call_args
        assert "orphans" in call_args
        assert "--json" in call_args

    def test_find_callers_passes_symbol(self, tmp_path: Path) -> None:
        """find_callers passes the symbol as --symbol argument."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps({"callers": []})
        with patch("subprocess.run", return_value=mock) as run:
            client.find_callers("MyClass.my_method")
        call_args = run.call_args[0][0]
        assert "--symbol" in call_args
        assert "MyClass.my_method" in call_args


class TestTrifectaGraphActions:
    """Test the new graph action methods added in Phase 1b."""

    def test_find_overview_returns_dict(self, tmp_path: Path) -> None:
        """find_overview returns the graph overview dict."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps(
            {
                "status": "ok",
                "node_count": 1000,
                "edge_count": 1500,
                "orphan_count": 50,
                "top_hubs": [{"symbol": "main", "in_degree": 30}],
            }
        )
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_overview()
        assert result.success is True
        assert result.data["node_count"] == 1000
        assert result.data["orphan_count"] == 50
        assert len(result.data["top_hubs"]) == 1

    def test_find_overview_handles_failure(self, tmp_path: Path) -> None:
        """find_overview returns empty dict on failure."""
        client = TrifectaClient(repo_path=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = client.find_overview()
        assert result.success is False
        assert result.data == {}

    def test_find_hubs_returns_list(self, tmp_path: Path) -> None:
        """find_hubs returns a list of hub dicts."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps(
            {
                "hubs": [
                    {"symbol_name": "main", "in_degree": 30},
                    {"symbol_name": "validate", "in_degree": 15},
                ],
            }
        )
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_hubs(top_n=5)
        assert result.success is True
        assert len(result.data) == 2
        assert result.data[0]["symbol_name"] == "main"

    def test_find_hubs_passes_top_n(self, tmp_path: Path) -> None:
        """find_hubs passes --top to Trifecta CLI."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps({"hubs": []})
        with patch("subprocess.run", return_value=mock) as run:
            client.find_hubs(top_n=20)
        call_args = run.call_args[0][0]
        assert "--top" in call_args
        assert "20" in call_args

    def test_find_callers_passes_depth(self, tmp_path: Path) -> None:
        """find_callers passes --depth when specified."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps({"callers": []})
        with patch("subprocess.run", return_value=mock) as run:
            client.find_callers("MyClass.method", depth=3)
        call_args = run.call_args[0][0]
        assert "--depth" in call_args
        assert "3" in call_args


class TestTrifectaResponseNormalization:
    """Test response normalization edge cases."""

    def test_find_orphans_extracts_orphans_key(self, tmp_path: Path) -> None:
        """find_orphans extracts data from 'orphans' key in dict response."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps({"orphans": ["orphan1", "orphan2"]})
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_orphans()
        assert result.success is True
        assert result.data == ["orphan1", "orphan2"]

    def test_find_orphans_non_dict_non_list_normalizes(self, tmp_path: Path) -> None:
        """find_orphans normalizes unexpected types to empty list."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = "42"
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_orphans()
        assert result.success is True
        assert result.data == []

    def test_find_callers_nodes_key_fallback(self, tmp_path: Path) -> None:
        """find_callers falls back to 'nodes' key when 'callers' missing."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps({"nodes": [{"name": "caller1"}]})
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_callers("some_func")
        assert result.success is True
        assert result.data[0]["name"] == "caller1"

    def test_find_callers_failure_returns_empty(self, tmp_path: Path) -> None:
        """find_callers returns empty list on failure."""
        client = TrifectaClient(repo_path=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = client.find_callers("func")
        assert result.success is False
        assert result.data == []

    def test_find_callees_callees_key(self, tmp_path: Path) -> None:
        """find_callees extracts from 'callees' key."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps({"callees": [{"name": "callee1"}]})
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_callees("some_func")
        assert result.success is True
        assert result.data[0]["name"] == "callee1"

    def test_find_callees_nodes_key_fallback(self, tmp_path: Path) -> None:
        """find_callees falls back to 'nodes' key."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps({"nodes": [{"name": "callee1"}]})
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_callees("some_func")
        assert result.success is True
        assert result.data[0]["name"] == "callee1"

    def test_find_callees_failure_returns_empty(self, tmp_path: Path) -> None:
        """find_callees returns empty list on failure."""
        client = TrifectaClient(repo_path=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = client.find_callees("func")
        assert result.success is False
        assert result.data == []

    def test_find_path_success(self, tmp_path: Path) -> None:
        """find_path returns path info."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps({"path": ["A", "B", "C"], "length": 2})
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_path("A", "C")
        assert result.success is True
        assert result.data["length"] == 2

    def test_find_path_failure_returns_empty(self, tmp_path: Path) -> None:
        """find_path returns empty dict on failure."""
        client = TrifectaClient(repo_path=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = client.find_path("A", "C")
        assert result.success is False
        assert result.data == {}

    def test_find_hubs_non_dict_normalizes(self, tmp_path: Path) -> None:
        """find_hubs normalizes non-dict/non-list responses to empty list."""
        client = TrifectaClient(repo_path=tmp_path)
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = "42"
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            result = client.find_hubs()
        assert result.success is True
        assert result.data == []

    def test_health_failure_returns_empty(self, tmp_path: Path) -> None:
        """health returns empty dict on failure."""
        client = TrifectaClient(repo_path=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = client.health()
        assert result.success is False
        assert result.data == {}

    def test_run_oserror(self, tmp_path: Path) -> None:
        """_run catches OSError and returns failed result."""
        client = TrifectaClient(repo_path=tmp_path)
        with patch("subprocess.run", side_effect=OSError("no such file")):
            result = client.find_orphans()
        assert result.success is False
