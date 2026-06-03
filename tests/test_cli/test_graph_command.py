"""Tests for cli/paper/commands/graph.py — trace and graph-overview handlers."""
from __future__ import annotations

import argparse
import json
from unittest.mock import MagicMock, patch

import pytest

from cli.paper.commands.graph import _cmd_graph_overview, _cmd_trace


def _make_trace_args(
    action: str = "callers",
    symbol: str = "MyClass.method",
    output: str = "json",
    depth: int = 1,
    to_symbol: str | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        action=action,
        symbol=symbol,
        output=output,
        depth=depth,
        to_symbol=to_symbol,
    )


class TestCmdTraceCallers:
    def test_trifecta_not_enabled_exits_1(self) -> None:
        """Trifecta disabled → error."""
        with patch("clients.trifecta.get_trifecta_client", return_value=None):
            with pytest.raises(SystemExit) as exc:
                _cmd_trace(_make_trace_args())
            assert exc.value.code == 1

    def test_callers_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """callers action produces JSON."""
        mock_client = MagicMock()
        mock_result = MagicMock(success=True, error=None, data=[{"symbol_name": "caller1", "file_rel": "a.py"}])
        mock_client.find_callers.return_value = mock_result
        with patch("clients.trifecta.get_trifecta_client", return_value=mock_client):
            _cmd_trace(_make_trace_args(action="callers", output="json"))
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["symbol_name"] == "caller1"

    def test_callers_failure_exits_1(self) -> None:
        """callers failure → exit 1."""
        mock_client = MagicMock()
        mock_result = MagicMock(success=False, error="not found")
        mock_client.find_callers.return_value = mock_result
        with patch("clients.trifecta.get_trifecta_client", return_value=mock_client):
            with pytest.raises(SystemExit) as exc:
                _cmd_trace(_make_trace_args(action="callers"))
            assert exc.value.code == 1


class TestCmdTraceCallees:
    def test_callees_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """callees action produces JSON."""
        mock_client = MagicMock()
        mock_result = MagicMock(success=True, error=None, data=[{"symbol_name": "callee1", "file_rel": "b.py"}])
        mock_client.find_callees.return_value = mock_result
        with patch("clients.trifecta.get_trifecta_client", return_value=mock_client):
            _cmd_trace(_make_trace_args(action="callees", output="json"))
        data = json.loads(capsys.readouterr().out)
        assert data[0]["symbol_name"] == "callee1"


class TestCmdTracePath:
    def test_path_missing_to_symbol_exits_1(self) -> None:
        """path action without --to → exit 1."""
        mock_client = MagicMock()
        with patch("clients.trifecta.get_trifecta_client", return_value=mock_client):
            with pytest.raises(SystemExit) as exc:
                _cmd_trace(_make_trace_args(action="path", to_symbol=None))
            assert exc.value.code == 1

    def test_path_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """path action produces JSON."""
        mock_client = MagicMock()
        mock_result = MagicMock(success=True, error=None, data={"path": ["A", "B", "C"], "path_exists": True})
        mock_client.find_path.return_value = mock_result
        with patch("clients.trifecta.get_trifecta_client", return_value=mock_client):
            _cmd_trace(_make_trace_args(action="path", output="json", to_symbol="C"))
        data = json.loads(capsys.readouterr().out)
        assert data["path_exists"] is True

    def test_path_no_path_found_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        """path action with no path found produces text message."""
        mock_client = MagicMock()
        mock_result = MagicMock(success=True, error=None, data={"path_exists": False, "path": []})
        mock_client.find_path.return_value = mock_result
        with patch("clients.trifecta.get_trifecta_client", return_value=mock_client):
            _cmd_trace(_make_trace_args(action="path", output="text", to_symbol="C"))
        output = capsys.readouterr().out
        assert "No path found" in output


class TestCmdGraphOverview:
    def test_trifecta_not_enabled_exits_1(self) -> None:
        args = argparse.Namespace(output="json")
        with patch("clients.trifecta.get_trifecta_client", return_value=None):
            with pytest.raises(SystemExit) as exc:
                _cmd_graph_overview(args)
            assert exc.value.code == 1

    def test_overview_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(output="json")
        mock_client = MagicMock()
        mock_result = MagicMock(
            success=True,
            error=None,
            data={
                "node_count": 100,
                "edge_count": 200,
                "orphan_count": 5,
                "calls_cycles": 0,
                "imports_cycles": 0,
                "inherits_cycles": 0,
                "top_hubs": [{"symbol_name": "main", "in_degree": 30}],
            },
        )
        mock_client.find_overview.return_value = mock_result
        with patch("clients.trifecta.get_trifecta_client", return_value=mock_client):
            _cmd_graph_overview(args)
        data = json.loads(capsys.readouterr().out)
        assert data["node_count"] == 100
        assert data["orphan_count"] == 5

    def test_overview_failure_exits_1(self) -> None:
        args = argparse.Namespace(output="json")
        mock_client = MagicMock()
        mock_result = MagicMock(success=False, error="unavailable")
        mock_client.find_overview.return_value = mock_result
        with patch("clients.trifecta.get_trifecta_client", return_value=mock_client):
            with pytest.raises(SystemExit) as exc:
                _cmd_graph_overview(args)
            assert exc.value.code == 1
