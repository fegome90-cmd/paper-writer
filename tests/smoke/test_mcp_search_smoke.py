"""Smoke test: real MCP session init + capability negotiation + search_papers.

Marked slow — excluded from CI fast path by default.
Run with: pytest tests/smoke/test_mcp_search_smoke.py -v --run-slow
"""

import json
import os

import pytest

# Skip entire module unless explicitly requested
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_MCP_SMOKE"),
    reason="Set RUN_MCP_SMOKE=1 to run real MCP smoke tests",
)


def test_mcp_sdk_session_init() -> None:
    """Verify MCP SDK can initialize session and negotiate capabilities."""
    import asyncio

    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    server_path = os.environ.get(
        "PAPER_MCP_SERVER_PATH",
        "/Users/felipe_gonzalez/.openclaw/mcp-servers/paper-mcp/dist/server.js",
    )

    async def _run() -> None:
        params = StdioServerParameters(command="node", args=[server_path])
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                result = await session.initialize()
                assert result.serverInfo.name == "paper-mcp"
                assert result.capabilities.tools is not None

    asyncio.run(_run())


def test_mcp_search_papers_returns_results() -> None:
    """Verify search_papers tool returns valid results from real MCP server."""
    import asyncio

    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    server_path = os.environ.get(
        "PAPER_MCP_SERVER_PATH",
        "/Users/felipe_gonzalez/.openclaw/mcp-servers/paper-mcp/dist/server.js",
    )

    async def _run() -> None:
        params = StdioServerParameters(command="node", args=[server_path])
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tool_result = await session.call_tool(
                    "search_papers",
                    arguments={
                        "query": "machine learning systematic review",
                        "sources": ["arxiv"],
                        "limit": 3,
                    },
                )

                assert tool_result.content
                text = tool_result.content[0].text
                data = json.loads(text)

                assert "results" in data
                assert isinstance(data["results"], list)
                assert len(data["results"]) > 0
                assert data["results"][0].get("title")

    asyncio.run(_run())


def test_mcp_provider_search_real() -> None:
    """McpPaperSearchProvider returns real papers from MCP server."""
    from integrations.tools.mcp_paper_client import McpPaperSearchProvider

    server_path = os.environ.get(
        "PAPER_MCP_SERVER_PATH",
        "/Users/felipe_gonzalez/.openclaw/mcp-servers/paper-mcp/dist/server.js",
    )

    provider = McpPaperSearchProvider(server_path=server_path)
    result = provider.search("transformer attention", sources=["arxiv"], limit=3)

    assert len(result.papers) > 0
    assert result.provenance.provider == "mcp"
    assert result.provenance.server_info.get("name") == "paper-mcp"
    assert all(p.title for p in result.papers)
    assert all(p.year > 0 for p in result.papers)


def test_pipeline_fixture_mode_generates_outputs(tmp_path) -> None:
    """Minimal pipeline test: fixture provider produces raw + normalized output."""
    from harness.ports.paper_search_provider import (
        _DEFAULT_FIXTURE_PATH,
        FixturePaperSearchProvider,
    )
    from skills.imported.literature_search import search as search_module

    provider = FixturePaperSearchProvider(fixture_path=_DEFAULT_FIXTURE_PATH)
    provider_result = provider.search("test query", limit=10)

    output_dir = tmp_path / "search"
    output_dir.mkdir()

    # Write raw + normalized
    raw_path = output_dir / "raw_results.json"
    raw_path.write_text(
        json.dumps(
            {**provider_result.raw_payload, "provenance": provider_result.provenance.to_dict()},
            indent=2,
        )
    )

    norm_path = output_dir / "normalized_results.json"
    norm_path.write_text(
        json.dumps(
            {"provenance": provider_result.provenance.to_dict(), "papers": [p.to_dict() for p in provider_result.papers]},
            indent=2,
        )
    )

    # Pass to scoring pipeline
    raw_papers = [p.to_dict() for p in provider_result.papers]
    result = search_module.search(query="test query", output_dir=output_dir, raw_papers=raw_papers)

    assert "artifacts" in result
    assert (output_dir / "search_plan.json").is_file()
    assert (output_dir / "raw_results.json").is_file()

    # Verify scoring worked
    scored = json.loads((output_dir / "raw_results.json").read_text())
    assert scored.get("papers")
    first = scored["papers"][0]
    assert "scoring" in first
