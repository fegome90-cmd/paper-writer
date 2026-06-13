"""Environment and dependency checker.

Reports the status of all external tools and internal capabilities.
Used by `paper doctor` CLI command to surface degraded mode explicitly.
"""

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolStatus:
    """Status of a single external tool."""

    name: str
    installed: bool
    version: str = ""
    install_hint: str = ""
    required_for: list[str] = field(default_factory=list)
    degraded_message: str = ""
    version_args: list[str] = field(default_factory=list)


def check_tool(name: str, version_args: list[str] | None = None) -> ToolStatus:
    """Check if a CLI tool is available on PATH."""
    tool_path = shutil.which(name)
    if not tool_path:
        return ToolStatus(
            name=name,
            installed=False,
            install_hint=_install_hint(name),
        )

    version = ""
    if version_args:
        try:
            result = subprocess.run(
                [name, *version_args],
                capture_output=True,
                text=True,
                timeout=5,
            )
            version = (result.stdout or result.stderr).strip().split("\n")[0]
        except (OSError, subprocess.SubprocessError):
            version = "unknown"

    return ToolStatus(name=name, installed=True, version=version)


def check_all_tools() -> list[ToolStatus]:
    """Check all external tools used by the pipeline."""
    tools = [
        _make("pandoc", ["--version"], "Render (docx/pdf)", "brew install pandoc"),
        _make("tectonic", ["--version"], "PDF render", "brew install tectonic"),
        _make("vale", ["--version"], "Style linting (vale rules)", "brew install vale"),
        _make(
            "bibtex-tidy",
            ["--version"],
            "Bibliography normalization",
            "npm install -g bibtex-tidy",
        ),
        _make(
            "pdftotext",
            ["-v"],
            "PDF text extraction (poppler)",
            "brew install poppler",
        ),
        _make(
            "pdfinfo",
            ["-v"],
            "PDF metadata extraction (poppler)",
            "brew install poppler",
        ),
    ]

    for t in tools:
        args = t.version_args if t.version_args else None
        status = check_tool(t.name, args)
        t.installed = status.installed
        t.version = status.version
        if not t.installed:
            t.degraded_message = (
                f"DEGRADED: {t.name} not found. {t.required_for[0]} uses built-in fallback. "
                f"Install: {t.install_hint}"
            )

    return tools


def check_internal_capabilities(repo_path: Path) -> list[ToolStatus]:
    """Check internal capabilities (no external deps).

    Resolves assets via get_project_asset() which implements the
    project-local → package-bundled waterfall automatically.
    """
    from harness.ports.assets import get_project_asset

    caps: list[ToolStatus] = []

    # Check Vale style packs exist
    styles_dir = get_project_asset(repo_path, "styles", "vale", "paper-writer")
    has_rules = styles_dir.is_dir() and any(styles_dir.glob("*.yml"))
    caps.append(
        ToolStatus(
            name="vale-styles",
            installed=has_rules,
            version="4 rules" if has_rules else "missing",
            required_for=["Style linting (built-in fallback)"],
            degraded_message=(
                "DEGRADED: Vale style packs not found. "
                "Built-in checks only (passive voice, long sentences)."
                if not has_rules
                else ""
            ),
        )
    )

    # Check CSL styles exist
    csl_dir = get_project_asset(repo_path, "styles", "csl")
    has_csl = csl_dir.is_dir() and any(csl_dir.glob("*.csl"))
    caps.append(
        ToolStatus(
            name="csl-styles",
            installed=has_csl,
            version="2 styles (vancouver, apa)" if has_csl else "missing",
            required_for=["Citation formatting"],
            degraded_message=(
                "DEGRADED: No CSL styles found. Pandoc will use default citation format."
                if not has_csl
                else ""
            ),
        )
    )

    # Check journal presets exist
    journals_dir = get_project_asset(repo_path, "templates", "journals")
    has_presets = journals_dir.is_dir() and any(journals_dir.iterdir())
    caps.append(
        ToolStatus(
            name="journal-presets",
            installed=has_presets,
            version="nature" if has_presets else "missing",
            required_for=["paper init --preset"],
            degraded_message=(
                "DEGRADED: No journal presets found. paper init uses empty templates."
                if not has_presets
                else ""
            ),
        )
    )

    # Check thesaurus store
    thesaurus_db = repo_path / "skills" / "local" / "thesaurus" / "workspace" / "thesaurus.db"
    has_thesaurus = thesaurus_db.exists() and thesaurus_db.stat().st_size > 0
    caps.append(
        ToolStatus(
            name="thesaurus",
            installed=has_thesaurus,
            version="active" if has_thesaurus else "missing",
            required_for=["Biomedical concept normalization (MeSH/DeCS)"],
            degraded_message=(
                "DEGRADED: Thesaurus DB not found. Run 'paper thesaurus import' to load concepts."
                if not has_thesaurus
                else ""
            ),
        )
    )

    # Check search provider configuration
    import os

    provider_name = os.environ.get("PAPER_SEARCH_PROVIDER", "").lower()
    provider_status = "missing"
    degraded_msg = ""
    version_str = "unconfigured"

    if provider_name:
        provider_status = "configured"
        version_str = provider_name

        if provider_name == "consensus_mcp_remote":
            try:
                import mcp  # noqa: F401
                from mcp.client.streamable_http import streamable_http_client  # noqa: F401

                has_mcp = True
            except ImportError:
                has_mcp = False

            api_key = os.environ.get("CONSENSUS_MCP_API_KEY", "")
            auth_mode = "Bearer token" if api_key else "Anonymous (3 papers limit)"

            if not has_mcp:
                provider_status = "degraded"
                degraded_msg = (
                    "DEGRADED: 'mcp' Python package missing or outdated. Install: pip install mcp"
                )
            else:
                url = os.environ.get("CONSENSUS_MCP_URL", "https://mcp.consensus.app/mcp")
                version_str = f"consensus_mcp_remote (url: {url}, auth: {auth_mode})"
    else:
        degraded_msg = (
            "DEGRADED: PAPER_SEARCH_PROVIDER is not set. "
            "Set to 'fixture', 'mcp', 'consensus', or 'consensus_mcp_remote'."
        )

    caps.append(
        ToolStatus(
            name="search-provider",
            installed=(provider_status != "degraded" and provider_status != "missing"),
            version=version_str,
            required_for=["Academic paper search"],
            degraded_message=degraded_msg,
        )
    )

    return caps


def format_doctor_report(tools: list[ToolStatus], caps: list[ToolStatus]) -> str:
    """Format a human-readable doctor report."""
    lines: list[str] = ["paper-writer environment check", "=" * 40, ""]

    # External tools
    lines.append("EXTERNAL TOOLS")
    lines.append("-" * 40)
    for t in tools:
        status = "OK" if t.installed else "MISSING"
        ver = f" ({t.version})" if t.version else ""
        lines.append(f"  [{status}] {t.name}{ver}")
        if t.required_for:
            lines.append(f"         Required for: {', '.join(t.required_for)}")
        if not t.installed:
            lines.append(f"         Install: {t.install_hint}")
    lines.append("")

    # Internal capabilities
    lines.append("INTERNAL CAPABILITIES")
    lines.append("-" * 40)
    for c in caps:
        status = "OK" if c.installed else "MISSING"
        lines.append(f"  [{status}] {c.name} ({c.version})")
    lines.append("")

    # Degraded mode summary
    degraded = [t for t in tools if not t.installed] + [c for c in caps if not c.installed]
    if degraded:
        lines.append("DEGRADED MODE ACTIVE")
        lines.append("-" * 40)
        for d in degraded:
            lines.append(f"  - {d.degraded_message or d.name + ': not available'}")
        lines.append("")
        lines.append(
            "Pipeline will use built-in fallbacks where available. "
            "Some gates may produce warnings instead of errors."
        )
    else:
        lines.append("ALL TOOLS AVAILABLE — Full capability mode.")

    return "\n".join(lines)


def _make(
    name: str,
    version_args: list[str],
    required_for: str,
    install_hint: str,
) -> ToolStatus:
    """Create a ToolStatus template (before checking)."""
    return ToolStatus(
        name=name,
        installed=False,
        install_hint=install_hint,
        required_for=[required_for],
        version_args=version_args,
    )


def _install_hint(name: str) -> str:
    """Provide install hints for known tools."""
    hints = {
        "pandoc": "brew install pandoc",
        "tectonic": "brew install tectonic",
        "vale": "brew install vale",
        "bibtex-tidy": "npm install -g bibtex-tidy",
    }
    return hints.get(name, f"Install {name} via your package manager")


def run_live_checks(run_search_probe: bool = False) -> str:
    """Run live remote connection checks for the active search provider."""
    import os

    provider_name = os.environ.get("PAPER_SEARCH_PROVIDER", "").lower()
    if not provider_name:
        return "LIVE CHECKS SKIPPED: No active search provider set."

    lines = ["LIVE CONNECTIVITY CHECKS", "-" * 40]

    if provider_name == "consensus_mcp_remote":
        url = os.environ.get("CONSENSUS_MCP_URL", "https://mcp.consensus.app/mcp")
        api_key = os.environ.get("CONSENSUS_MCP_API_KEY", "")
        lines.append(f"Target URL: {url}")
        lines.append(f"Auth Mode: {'Bearer token (masked)' if api_key else 'Anonymous'}")

        try:
            import asyncio

            import httpx
            from mcp.client.session import ClientSession
            from mcp.client.streamable_http import streamable_http_client

            async def _check() -> list[str]:
                results = []
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

                results.append("1. Attempting connection via Streamable HTTP...")
                async with httpx.AsyncClient(headers=headers) as http_client:
                    async with streamable_http_client(url, http_client=http_client) as streams:
                        read_stream, write_stream = streams[0], streams[1]
                        results.append("   [OK] Connected to Streamable HTTP stream.")
                        results.append("2. Starting Client Session...")
                        async with ClientSession(read_stream, write_stream) as session:
                            results.append("3. Initializing and negotiating capabilities...")
                            init_result = await asyncio.wait_for(session.initialize(), timeout=10)
                            results.append(
                                f"   [OK] Negotiated: name={init_result.serverInfo.name}, "
                                f"version={init_result.serverInfo.version}"
                            )

                            results.append("4. Querying tool list...")
                            tools_list = await session.list_tools()
                            tool_names = [t.name for t in tools_list.tools]
                            results.append(f"   [OK] Available tools: {', '.join(tool_names)}")

                            if "search" not in tool_names:
                                results.append(
                                    "   [ERROR] 'search' tool is missing from exposed tools."
                                )
                            elif run_search_probe:
                                results.append("5. Invoking safe minimal query search probe...")
                                try:
                                    await asyncio.wait_for(
                                        session.call_tool(
                                            "search",
                                            arguments={
                                                "query": "effects of exercise on depression",
                                                "limit": 1,
                                            },
                                        ),
                                        timeout=10,
                                    )
                                    results.append("   [OK] Minimal query search probe succeeded.")
                                except Exception as exc:
                                    results.append(f"   [ERROR] search probe failed: {exc}")
                return results

            # Run in loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, _check())
                    check_results = future.result(timeout=25)
            else:
                check_results = asyncio.run(_check())

            lines.extend(check_results)
            lines.append("\nALL LIVE CHECKS COMPLETED.")
        except Exception as exc:
            lines.append(f"   [CRITICAL FAIL] Connectivity test failed: {exc}")

    elif provider_name == "consensus":
        lines.append("Active provider is Consensus REST. Live connectivity is REST-based.")
        lines.append("REST connectivity checked by smoke test suite. Skipping live check here.")
    else:
        lines.append(
            f"Live diagnostics not implemented/required for provider mode: {provider_name}"
        )

    return "\n".join(lines)
