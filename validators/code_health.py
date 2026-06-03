"""Code health validator using Trifecta.

Finds dead code / orphans in paper-writer's codebase, filtering out known
false positives (tests, mixin inheritance, CLI dispatch). This is the first
integration of Trifecta tools into paper-writer's pipeline.

Why this exists:
    - paper-writer's existing audit (claims, prose, reporting) is content-focused
    - This adds a CODE-focused audit (dead code, unused methods, etc.)
    - It uses Trifecta's graph index which already has 1100+ edges for paper-writer
    - Without filtering, ~95% of orphans are false positives (pytest, mixin, dispatch)

Usage:
    from validators.code_health import analyze_code_health
    report = analyze_code_health()
    if report.trifecta_enabled and report.findings:
        for finding in report.findings:
            print(f"{finding.file_rel}::{finding.symbol_name}")

The validator degrades gracefully — if Trifecta is unavailable, the report
is empty with trifecta_enabled=False (no exception, no crash).

Why strict TDD:
    - We must not break the existing 574 tests
    - The filter is critical (95% FP rate without it)
    - The integration boundary (Trifecta subprocess) needs explicit testing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# False positive patterns based on docs/graph-audit-findings.md
# 91% of "orphans" are pytest calls (test_ prefix in tests/ dir)
# 4% are Mixin-inherited methods (name, gate, is_available from ToolWrapper)
# 1% are argparse callbacks (_cmd_ prefix)
# 1% are entry points (main function)
TEST_PREFIXES = ("test_", "Test", "_test")
ARG_PARSE_CALLBACK_PREFIX = "_cmd_"
ENTRY_POINT_NAMES = {"main", "cli", "run", "app"}
# ToolWrapper Mixin methods (4 of them, inherited by 8 tool classes)
MIXIN_INHERITED_METHODS = {"name", "gate", "is_available"}


@dataclass
class CodeHealthFinding:
    """A single actionable orphan finding."""

    file_rel: str
    symbol_name: str
    qualified_name: str
    kind: str
    orphan_type: str = "dead_code"

    def to_dict(self) -> dict[str, str]:
        """Convert to dict for JSON serialization."""
        return {
            "file_rel": self.file_rel,
            "symbol_name": self.symbol_name,
            "qualified_name": self.qualified_name,
            "kind": self.kind,
            "orphan_type": self.orphan_type,
        }


@dataclass
class CodeHealthReport:
    """Result of code_health analysis.

    Attributes:
        trifecta_enabled: True if Trifecta subprocess was available.
        findings: Actionable code health issues (filtered).
        filtered_count: Number of orphans excluded by the filter.
        total_orphans_seen: Total orphans reported by Trifecta before filtering.
        error: Description of any error encountered (empty if successful).
    """

    trifecta_enabled: bool
    findings: list[CodeHealthFinding] = field(default_factory=list)
    filtered_count: int = 0
    total_orphans_seen: int = 0
    error: str = ""

    def summary(self) -> str:
        """Human-readable summary for CLI output."""
        if not self.trifecta_enabled:
            return f"Code health: SKIPPED ({self.error})"
        if not self.findings:
            return (
                f"Code health: OK "
                f"({self.total_orphans_seen} orphans seen, "
                f"{self.filtered_count} filtered, 0 actionable)"
            )
        return (
            f"Code health: {len(self.findings)} actionable "
            f"({self.filtered_count} filtered from {self.total_orphans_seen})"
        )


def _is_test_file(file_rel: str) -> bool:
    """Check if file is in tests/ or verification/ directory."""
    return file_rel.startswith("tests/") or file_rel.startswith("verification/")


def _is_argparse_callback(symbol_name: str) -> bool:
    """Check if symbol is an argparse callback (registered via set_defaults(func=X))."""
    return symbol_name.startswith(ARG_PARSE_CALLBACK_PREFIX)


def _is_entry_point(symbol_name: str) -> bool:
    """Check if symbol is a CLI entry point (main, cli, run, app)."""
    return symbol_name in ENTRY_POINT_NAMES


def _is_test_symbol(symbol_name: str) -> bool:
    """Check if symbol follows pytest naming convention."""
    return any(symbol_name.startswith(p) for p in TEST_PREFIXES)


def _is_mixin_inherited(symbol_name: str) -> bool:
    """Check if symbol is a method inherited from ToolWrapper Mixin."""
    return symbol_name in MIXIN_INHERITED_METHODS


def _is_actionable(orphan: dict[str, Any]) -> bool:
    """Determine if an orphan is a real actionable finding.

    Returns False for known false positives:
    - Files in tests/ or verification/
    - Test-prefixed functions
    - Argparse callbacks (_cmd_ prefix)
    - Entry points (main, cli, run, app)
    - Mixin-inherited methods (name, gate, is_available)

    Returns True for everything else (potential dead code, validation gaps,
    data flow breaks, etc.).
    """
    file_rel = orphan.get("file_rel", "")
    symbol_name = orphan.get("symbol_name", "")

    if _is_test_file(file_rel):
        return False
    if _is_test_symbol(symbol_name):
        return False
    if _is_argparse_callback(symbol_name):
        return False
    if _is_entry_point(symbol_name):
        return False
    if _is_mixin_inherited(symbol_name):
        return False
    return True


def filter_actionable_orphans(orphans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter Trifecta's orphan list to actionable findings only.

    Args:
        orphans: List of orphan dicts from Trifecta's graph orphans output.

    Returns:
        Filtered list of actionable orphans (real dead code, not test/CLI/mixin).
    """
    return [o for o in orphans if _is_actionable(o)]


def _make_finding(orphan: dict[str, Any]) -> CodeHealthFinding:
    """Convert a Trifecta orphan dict to a CodeHealthFinding."""
    return CodeHealthFinding(
        file_rel=orphan.get("file_rel", ""),
        symbol_name=orphan.get("symbol_name", ""),
        qualified_name=orphan.get("qualified_name", ""),
        kind=orphan.get("kind", "function"),
        orphan_type=orphan.get("orphan_type", "dead_code"),
    )


@dataclass
class DependencyRiskFinding:
    """A symbol that is both highly-connected (hub) and orphaned (dead code).

    Dead hubs are high-risk because they represent code that is depended upon
    by many other symbols but is itself unreachable from any entry point.
    """

    file_rel: str
    symbol_name: str
    qualified_name: str
    kind: str
    in_degree: int
    risk_reason: str = "dead_hub"

    def to_dict(self) -> dict[str, str | int]:
        """Convert to dict for JSON serialization."""
        return {
            "file_rel": self.file_rel,
            "symbol_name": self.symbol_name,
            "qualified_name": self.qualified_name,
            "kind": self.kind,
            "in_degree": self.in_degree,
            "risk_reason": self.risk_reason,
        }


@dataclass
class DependencyRiskReport:
    """Result of dependency risk analysis using Trifecta graph hubs + orphans.

    Attributes:
        trifecta_enabled: True if Trifecta subprocess was available.
        findings: Dead hubs (highly-connected orphaned symbols).
        hub_count: Number of hubs analyzed.
        error: Description of any error encountered.
    """

    trifecta_enabled: bool
    findings: list[DependencyRiskFinding] = field(default_factory=list)
    hub_count: int = 0
    error: str = ""

    def summary(self) -> str:
        """Human-readable summary for CLI output."""
        if not self.trifecta_enabled:
            return f"Dependency risk: SKIPPED ({self.error})"
        if not self.findings:
            return f"Dependency risk: OK ({self.hub_count} hubs analyzed, 0 dead)"
        return (
            f"Dependency risk: {len(self.findings)} dead hubs "
            f"({self.hub_count} hubs analyzed)"
        )


HUB_IN_DEGREE_THRESHOLD = 5
"""Minimum in_degree for a symbol to be considered a hub."""


def _find_dead_hubs(
    hubs: list[dict[str, Any]],
    orphan_ids: set[str],
) -> list[DependencyRiskFinding]:
    """Find hubs that are also orphans — symbols depended upon but unreachable.

    These are the highest-risk dead code: removing them would break callers,
    but they are not reachable from any entry point.
    """
    dead_hubs: list[DependencyRiskFinding] = []
    for hub in hubs:
        hub_id = hub.get("id", "")
        in_degree = hub.get("in_degree", 0)
        if in_degree < HUB_IN_DEGREE_THRESHOLD:
            continue
        if hub_id in orphan_ids:
            dead_hubs.append(
                DependencyRiskFinding(
                    file_rel=hub.get("file_rel", ""),
                    symbol_name=hub.get("symbol_name", ""),
                    qualified_name=hub.get("qualified_name", ""),
                    kind=hub.get("kind", "function"),
                    in_degree=in_degree,
                    risk_reason="dead_hub",
                )
            )
    return dead_hubs


def analyze_dependency_risk(
    repo_path: str | None = None,
) -> DependencyRiskReport:
    """Analyze dependency risk using Trifecta graph hubs + orphan cross-reference.

    This adds a capability beyond simple orphan detection: it finds symbols
    that are (a) depended upon by many other symbols (hubs) AND (b) not
    reachable from any entry point (orphans). Dead hubs are high-risk because
    their removal would cascade-break many callers.

    The function NEVER raises. If Trifecta is unavailable, returns a report
    with trifecta_enabled=False and a descriptive error message.
    """
    from clients.trifecta import get_trifecta_client

    client = get_trifecta_client(repo_path=repo_path)  # type: ignore[arg-type]
    if client is None:
        return DependencyRiskReport(
            trifecta_enabled=False,
            error="Trifecta not enabled (set MCP_TRIFECTA_MODE=real)",
        )

    # Step 1: Get hubs (highly-connected symbols)
    hubs_result = client.find_hubs(top_n=50)
    if not hubs_result.success:
        return DependencyRiskReport(
            trifecta_enabled=True,
            error=hubs_result.error or "Trifecta find_hubs failed",
        )

    hubs = hubs_result.data if isinstance(hubs_result.data, list) else []

    # Step 2: Get orphans (unreachable symbols)
    orphans_result = client.find_orphans()
    if not orphans_result.success:
        return DependencyRiskReport(
            trifecta_enabled=True,
            error=orphans_result.error or "Trifecta find_orphans failed",
        )

    orphans = orphans_result.data if isinstance(orphans_result.data, list) else []
    orphan_ids = {o.get("id", "") for o in orphans}

    # Step 3: Cross-reference — find dead hubs
    dead_hubs = _find_dead_hubs(hubs, orphan_ids)

    # Filter out test-file dead hubs
    dead_hubs = [
        dh
        for dh in dead_hubs
        if not _is_test_file(dh.file_rel) and not _is_test_symbol(dh.symbol_name)
    ]

    return DependencyRiskReport(
        trifecta_enabled=True,
        findings=dead_hubs,
        hub_count=len(hubs),
        error="",
    )


def analyze_code_health(
    repo_path: str | None = None,
) -> CodeHealthReport:
    """Analyze code health using Trifecta graph index.

    This is the main entry point. It:
    1. Gets a Trifecta client (or None if MCP_TRIFECTA_MODE=off)
    2. Calls find_orphans() via subprocess
    3. Filters out known false positives
    4. Returns a CodeHealthReport

    Args:
        repo_path: Optional path to the repo. Defaults to client default (cwd).

    Returns:
        CodeHealthReport with findings, filter stats, and any errors.

    The function NEVER raises. If Trifecta is unavailable, returns a report
        with trifecta_enabled=False and a descriptive error message.
    """
    # Lazy import to avoid circular dependencies and to keep the import cheap
    # when Trifecta is disabled (default for safety)
    from clients.trifecta import get_trifecta_client

    client = get_trifecta_client(repo_path=repo_path)  # type: ignore[arg-type]
    if client is None:
        return CodeHealthReport(
            trifecta_enabled=False,
            error="Trifecta not enabled (set MCP_TRIFECTA_MODE=real)",
        )

    result = client.find_orphans()
    if not result.success:
        return CodeHealthReport(
            trifecta_enabled=True,
            error=result.error or "Trifecta find_orphans failed",
        )

    orphans = result.data if isinstance(result.data, list) else []
    total = len(orphans)
    actionable = filter_actionable_orphans(orphans)
    findings = [_make_finding(o) for o in actionable]

    return CodeHealthReport(
        trifecta_enabled=True,
        findings=findings,
        filtered_count=total - len(actionable),
        total_orphans_seen=total,
        error="",
    )
