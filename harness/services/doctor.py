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
        _make("pdflatex", [], "PDF render", "brew install --cask mactex-no-gui (or basictex)"),
        _make("vale", ["--version"], "Style linting (vale rules)", "brew install vale"),
        _make(
            "bibtex-tidy",
            ["--version"],
            "Bibliography normalization",
            "npm install -g bibtex-tidy",
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

    Resolves assets first from repo_path (cwd), then from package-bundled
    assets via the centralized resolver for portable installations.
    """
    from harness.ports.assets import (
        get_csl_styles_dir,
        get_preset_dir,
        get_vale_styles_dir,
    )

    caps: list[ToolStatus] = []

    # Check Vale style packs exist
    # Try repo_path first, then package-bundled fallback
    styles_dir = repo_path / "styles" / "vale" / "paper-writer"
    if not styles_dir.is_dir():
        bundled = get_vale_styles_dir() / "paper-writer"
        if bundled.is_dir():
            styles_dir = bundled
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
    csl_dir = repo_path / "styles" / "csl"
    if not csl_dir.is_dir():
        csl_dir = get_csl_styles_dir()
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
    journals_dir = repo_path / "templates" / "journals"
    if not journals_dir.is_dir():
        journals_dir = get_preset_dir("")  # parent of any preset
        if not journals_dir.is_dir():
            journals_dir = repo_path / "templates" / "journals"
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
        "pdflatex": "brew install --cask mactex-no-gui (or basictex)",
        "vale": "brew install vale",
        "bibtex-tidy": "npm install -g bibtex-tidy",
    }
    return hints.get(name, f"Install {name} via your package manager")
