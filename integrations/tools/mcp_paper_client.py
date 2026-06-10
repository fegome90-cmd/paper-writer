"""MCP SDK client wrapper for paper-mcp server.

Uses the official Python MCP SDK (mcp[cli]) for session management,
capability negotiation, tool invocation, and process lifecycle.

Fail-closed: all errors propagate. No silent degradation.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from harness.ports.paper_search_provider import (
    _DEFAULT_SOURCES,
    PaperSearchProvider,
    SearchProvenance,
    SearchProviderResult,
    _normalize_paper,
    _validate_query_and_limit,
    deduplicate_papers,
)

# ── Defaults ──────────────────────────────────────────────────────────

_DEFAULT_SERVER_PATH = ""
_INIT_TIMEOUT = timedelta(seconds=10)
_TOOL_TIMEOUT = timedelta(seconds=30)


class McpPaperSearchProvider(PaperSearchProvider):
    """Real academic search via paper-mcp server using official MCP SDK.

    Requires:
        - mcp[cli] package installed
        - PAPER_MCP_SERVER_PATH pointing to dist/server.js (or default)
        - Node.js >= 18 on PATH

    All errors are visible. Never degrades silently.
    """

    def __init__(
        self,
        *,
        server_path: str | None = None,
        init_timeout: timedelta | None = None,
        tool_timeout: timedelta | None = None,
    ) -> None:
        self._server_path = server_path or os.environ.get(
            "PAPER_MCP_SERVER_PATH", _DEFAULT_SERVER_PATH
        )
        self._init_timeout = init_timeout or _INIT_TIMEOUT
        self._tool_timeout = tool_timeout or _TOOL_TIMEOUT

        if not self._server_path:
            raise RuntimeError(
                "PAPER_MCP_SERVER_PATH env var required for MCP search provider. "
                "Set it to your paper-mcp server.js path."
            )

        if not Path(self._server_path).is_file():
            raise RuntimeError(
                f"MCP server not found at: {self._server_path}. "
                f"Set PAPER_MCP_SERVER_PATH or verify the path."
            )

    def search(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> SearchProviderResult:
        _validate_query_and_limit(query, limit)

        # Run async implementation in event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an existing event loop — use nest-free approach
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self._search_async(query, sources=sources, limit=limit),
                )
                return future.result(timeout=self._tool_timeout.seconds + 5)
        else:
            return asyncio.run(self._search_async(query, sources=sources, limit=limit))

    async def _search_async(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        limit: int = 20,
    ) -> SearchProviderResult:
        """Async implementation using MCP SDK."""
        resolved_sources = sources or _DEFAULT_SOURCES
        server_params = StdioServerParameters(
            command="node",
            args=[self._server_path],
        )

        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    # 1. Initialize session with capability negotiation
                    try:
                        init_result = await asyncio.wait_for(
                            session.initialize(),
                            timeout=self._init_timeout.seconds,
                        )
                    except asyncio.TimeoutError as exc:
                        raise TimeoutError(
                            f"MCP server initialization timed out "
                            f"after {self._init_timeout.seconds}s"
                        ) from exc

                    server_info = {
                        "name": init_result.serverInfo.name,
                        "version": init_result.serverInfo.version,
                    }

                    # 2. Call search_papers tool
                    try:
                        tool_result = await asyncio.wait_for(
                            session.call_tool(
                                "search_papers",
                                arguments={
                                    "query": query,
                                    "sources": resolved_sources,
                                    "limit": limit,
                                },
                            ),
                            timeout=self._tool_timeout.seconds,
                        )
                    except asyncio.TimeoutError as exc:
                        raise TimeoutError(
                            f"MCP search_papers timed out after {self._tool_timeout.seconds}s"
                        ) from exc

                    # 3. Parse response
                    if not tool_result.content:
                        raise RuntimeError("MCP search_papers returned empty content")

                    from mcp.types import TextContent

                    first_content = tool_result.content[0]
                    if not isinstance(first_content, TextContent):
                        raise RuntimeError(
                            f"MCP returned non-text content: {type(first_content).__name__}"
                        )
                    text = first_content.text
                    try:
                        raw = json.loads(text)
                    except (json.JSONDecodeError, ValueError) as exc:
                        raise RuntimeError(f"MCP returned invalid JSON: {exc}") from exc

                    # 4. Check for MCP-level errors
                    if "error" in raw:
                        raise RuntimeError(f"MCP tool error: {raw['error']}")

                    results = raw.get("results", [])
                    if not isinstance(results, list):
                        raise RuntimeError(
                            f"MCP returned non-list results: {type(results).__name__}"
                        )

                    # 5. Normalize and deduplicate
                    papers = [_normalize_paper(r) for r in results]
                    papers = deduplicate_papers(papers)

                    return SearchProviderResult(
                        papers=papers,
                        raw_payload=raw,
                        provenance=SearchProvenance(
                            provider="mcp",
                            query=query,
                            retrieved_at=self._now_iso(),
                            tool_name="search_papers",
                            sources=resolved_sources,
                            server_info=server_info,
                        ),
                    )

        except TimeoutError:
            raise  # Already wrapped
        except RuntimeError:
            raise  # Already wrapped
        except Exception as exc:
            raise RuntimeError(f"MCP search failed: {type(exc).__name__}: {exc}") from exc

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone

        return datetime.now(tz=timezone.utc).isoformat()
