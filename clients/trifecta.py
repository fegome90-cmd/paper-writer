"""Trifecta subprocess wrapper for paper-writer.

Provides a safe interface to use Trifecta's CLI as a subprocess client.
All methods gracefully degrade when Trifecta is unavailable — paper-writer
must NEVER fail because Trifecta is down.

Usage:
    from clients.trifecta import get_trifecta_client

    client = get_trifecta_client()
    if client is not None:
        result = client.find_orphans()
        if result.success:
            for orphan in result.data:
                print(orphan["symbol_name"])

Configuration via environment:
    MCP_TRIFECTA_MODE=off   - Disabled (default, paper-writer doesn't use Trifecta)
    MCP_TRIFECTA_MODE=real  - Use real Trifecta subprocess
    MCP_TRIFECTA_MODE=mock  - Use mock for tests

Why subprocess and not direct import:
    - TrifectaF1Server is designed as a JSON-RPC socket server, not a library
    - Subprocess is the public API and most stable contract
    - Subprocess failures don't crash the caller
    - No coupling to Trifecta's internal module structure
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class TrifectaUnavailableError(Exception):
    """Raised when Trifecta is required but unavailable.

    Most callers should NOT raise this — use TrifectaResult.success=False
    for graceful degradation. This is for cases where Trifecta is mandatory.
    """


@dataclass
class TrifectaResult:
    """Result of a Trifecta CLI call.

    On success: success=True, data=parsed JSON, error=""
    On failure: success=False, data=[], error=description (for logging)
    """

    success: bool
    data: Any = None
    error: str = ""
    command: list[str] = field(default_factory=list)


class TrifectaClient:
    """Subprocess wrapper for the Trifecta CLI.

    All methods are safe to call when Trifecta is unavailable — they return
    TrifectaResult(success=False) instead of raising exceptions.
    """

    DEFAULT_TIMEOUT = 5.0  # seconds

    def __init__(
        self,
        repo_path: Path | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize Trifecta client.

        Args:
            repo_path: Path to the repo to query. Defaults to current working directory.
            timeout: Subprocess timeout in seconds. Default 5s for graceful degradation.
        """
        self.repo_path = Path(repo_path) if repo_path is not None else Path.cwd()
        self.timeout = timeout

    def _run(self, cmd: list[str]) -> TrifectaResult:
        """Run a Trifecta CLI command and parse the JSON output.

        Never raises — all errors are returned as TrifectaResult(success=False).
        """
        full_cmd = ["trifecta"] + cmd + ["--json"]
        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.repo_path,
            )
        except FileNotFoundError as exc:
            return TrifectaResult(
                success=False,
                data=[],
                error=f"Trifecta CLI not found: {exc}",
                command=full_cmd,
            )
        except subprocess.TimeoutExpired as exc:
            return TrifectaResult(
                success=False,
                data=[],
                error=f"Trifecta CLI timeout after {self.timeout}s: {exc}",
                command=full_cmd,
            )
        except OSError as exc:
            return TrifectaResult(
                success=False,
                data=[],
                error=f"Trifecta CLI OS error: {exc}",
                command=full_cmd,
            )

        if result.returncode != 0:
            return TrifectaResult(
                success=False,
                data=[],
                error=f"Trifecta CLI exit {result.returncode}: {result.stderr.strip()}",
                command=full_cmd,
            )

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return TrifectaResult(
                success=False,
                data=[],
                error=f"Trifecta CLI returned invalid JSON: {exc}",
                command=full_cmd,
            )

        return TrifectaResult(success=True, data=data, command=full_cmd)

    def find_orphans(self) -> TrifectaResult:
        """Find symbols with no incoming edges (potential dead code).

        Returns:
            TrifectaResult with data=list of orphan dicts, each containing:
                - id, symbol_name, qualified_name, kind, file_rel, orphan_type
        """
        result = self._run(["graph", "orphans"])
        if not result.success:
            # Ensure data is always a list for find_orphans
            result.data = []
            return result
        # Extract orphans from the response
        if isinstance(result.data, dict) and "orphans" in result.data:
            result.data = result.data["orphans"]
        elif not isinstance(result.data, list):
            result.data = []
        return result

    def find_callers(self, symbol: str, depth: int = 1) -> TrifectaResult:
        """Find callers of a symbol.

        Args:
            symbol: Qualified name like "ClassName.method_name" or "function_name"
            depth: Traversal depth (1=direct, 3=transitive). Default 1.

        Returns:
            TrifectaResult with data=list of caller dicts.
        """
        result = self._run(["graph", "callers", "--symbol", symbol, "--depth", str(depth)])
        if not result.success:
            result.data = []
            return result
        # Trifecta returns callers in either "callers" or "nodes" key
        if isinstance(result.data, dict):
            if "callers" in result.data:
                result.data = result.data["callers"]
            elif "nodes" in result.data:
                result.data = result.data["nodes"]
            else:
                result.data = []
        elif not isinstance(result.data, list):
            result.data = []
        return result

    def find_callees(self, symbol: str) -> TrifectaResult:
        """Find what a symbol calls.

        Args:
            symbol: Qualified name like "ClassName.method_name" or "function_name"

        Returns:
            TrifectaResult with data=list of callee dicts.
        """
        result = self._run(["graph", "callees", "--symbol", symbol])
        if not result.success:
            result.data = []
            return result
        # Trifecta returns in either "callees" or "nodes" key
        if isinstance(result.data, dict):
            if "callees" in result.data:
                result.data = result.data["callees"]
            elif "nodes" in result.data:
                result.data = result.data["nodes"]
            else:
                result.data = []
        elif not isinstance(result.data, list):
            result.data = []
        return result

    def find_path(self, from_symbol: str, to_symbol: str) -> TrifectaResult:
        """Find shortest call path between two symbols.

        Args:
            from_symbol: Source symbol
            to_symbol: Target symbol

        Returns:
            TrifectaResult with data=dict containing path information.
        """
        result = self._run(["graph", "path", "--from", from_symbol, "--to", to_symbol])
        if not result.success:
            result.data = {}
            return result
        if not isinstance(result.data, dict):
            result.data = {}
        return result

    def find_overview(self) -> TrifectaResult:
        """Get architectural health overview: cycles, orphans, hubs, path stats.

        Returns:
            TrifectaResult with data=dict containing node_count, edge_count,
            cycles, orphan_count, top_hubs list.
        """
        result = self._run(["graph", "overview"])
        if not result.success:
            result.data = {}
            return result
        if not isinstance(result.data, dict):
            result.data = {}
        return result

    def find_hubs(self, top_n: int = 10) -> TrifectaResult:
        """Find most-depended-upon symbols (architectural keystones).

        Args:
            top_n: Number of top hubs to return (default 10).

        Returns:
            TrifectaResult with data=list of hub dicts.
        """
        result = self._run(["graph", "hubs", "--top", str(top_n)])
        if not result.success:
            result.data = []
            return result
        if isinstance(result.data, dict) and "hubs" in result.data:
            result.data = result.data["hubs"]
        elif not isinstance(result.data, list):
            result.data = []
        return result

    def health(self) -> TrifectaResult:
        """Get Trifecta graph health status.

        Returns:
            TrifectaResult with data=dict containing node_count, edge_count, etc.
        """
        result = self._run(["graph", "status"])
        if not result.success:
            result.data = {}
            return result
        if not isinstance(result.data, dict):
            result.data = {}
        return result


def get_trifecta_client(
    repo_path: Path | None = None,
    timeout: float = TrifectaClient.DEFAULT_TIMEOUT,
) -> TrifectaClient | None:
    """Factory that returns a TrifectaClient based on MCP_TRIFECTA_MODE.

    Returns:
        - None if MCP_TRIFECTA_MODE=off (default for safety)
        - TrifectaClient instance if MCP_TRIFECTA_MODE=real or =mock

    Use this factory in validators, not TrifectaClient() directly.
    This way, paper-writer can be configured to use or not use Trifecta
    via environment variable, with no code changes.
    """
    mode = os.environ.get("MCP_TRIFECTA_MODE", "off").lower()
    if mode == "off":
        return None
    if mode in ("real", "mock"):
        return TrifectaClient(repo_path=repo_path, timeout=timeout)
    # Unknown mode — be safe and disable
    return None
