"""Table and figure generation from pipeline data.

Generates structured tables and diagrams from existing pipeline
metadata without requiring LLM calls:

1. PRISMA flow diagram (mermaid) from prisma_flow data
2. Study characteristics table (markdown) from screened evidence
3. Table/figure validator for draft sections
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def generate_prisma_mermaid(screened_evidence_path: Path) -> str:
    """Generate a PRISMA 2020 flow diagram in mermaid syntax.

    Args:
        screened_evidence_path: Path to screened_evidence.json with prisma_flow.

    Returns:
        Mermaid flowchart string.
    """
    try:
        data = json.loads(screened_evidence_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Cannot read screened evidence: {e}") from e

    flow = data.get("prisma_flow", {})
    if not flow:
        raise ValueError("No prisma_flow data in screened evidence")

    ident = flow.get("identification", {})
    scr = flow.get("screening", {})
    elig = flow.get("eligibility", {})
    inc = flow.get("included", {})

    db = ident.get("database_results", 0)
    other = ident.get("other_sources", 0)
    seeds = ident.get("seed_papers", 0)
    total_id = ident.get("total_identified", 0)
    dups = ident.get("duplicates_removed", 0)

    screened_n = scr.get("records_screened", 0)
    excluded_scr = scr.get("records_excluded", 0)

    assessed_n = elig.get("records_assessed", 0)
    excluded_elig = elig.get("records_excluded", 0)

    included_n = inc.get("studies_in_synthesis", 0)

    lines = [
        "flowchart TD",
        f'    A["Identification<br/>Database: {db}<br/>Other sources: {other}<br/>'
        f'Seeds: {seeds}"] --> B["Records after dedup<br/>{total_id}"]',
        f'    B --> C["Records screened<br/>{screened_n}"]',
        f'    C --> D["Records excluded<br/>{excluded_scr}"]',
        f'    C --> E["Records assessed<br/>{assessed_n}"]',
        f'    E --> F["Records excluded<br/>{excluded_elig}"]',
        f'    E --> G["Studies included<br/>{included_n}"]',
    ]

    return "\n".join(lines)


def generate_study_table(
    screened_evidence_path: Path,
    max_rows: int = 30,
) -> str:
    """Generate a markdown study characteristics table.

    Args:
        screened_evidence_path: Path to screened_evidence.json.
        max_rows: Maximum rows in the table.

    Returns:
        Markdown table string.
    """
    try:
        data = json.loads(screened_evidence_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Cannot read screened evidence: {e}") from e

    evidence = data.get("evidence", [])
    if not evidence:
        return "*No screened evidence available for table generation.*"

    rows = evidence[:max_rows]

    lines = [
        "| # | Study | Year | Venue | Citations | Tier | Score |",
        "|---:|-------|------|-------|----------:|------|------:|",
    ]

    for i, paper in enumerate(rows, 1):
        title = paper.get("title", "Untitled")
        if len(title) > 50:
            title = title[:47] + "..."
        year = paper.get("year", "—")
        venue = paper.get("venue", "—")
        if len(venue) > 15:
            venue = venue[:12] + "..."
        cites = paper.get("citation_count", 0)
        scoring = paper.get("scoring", {})
        tier = scoring.get("tier", "—")
        score = scoring.get("final_score", "—")
        lines.append(f"| {i} | {title} | {year} | {venue} | {cites} | {tier} | {score} |")

    if len(evidence) > max_rows:
        lines.append(f"\n*Showing {max_rows} of {len(evidence)} studies.*")

    return "\n".join(lines)


def validate_tables_figures(
    draft_dir: Path,
    required_tables: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Validate that draft sections contain required tables and figures.

    Checks markdown files for:
    - Markdown tables (| header | pattern)
    - Mermaid diagrams (```mermaid blocks)

    Args:
        draft_dir: Directory containing section markdown files.
        required_tables: List of required table identifiers.
            Default: ["study_characteristics", "comparison"].

    Returns:
        List of findings for missing tables/figures.
    """
    if required_tables is None:
        required_tables = ["study_characteristics", "comparison"]

    if not draft_dir.exists():
        return [
            {
                "rule_id": "tables_figures.missing_draft_dir",
                "severity": "P1",
                "message": f"Draft directory not found: {draft_dir}",
                "recommendation": "Run draft_all to generate section files.",
            }
        ]

    md_files = list(draft_dir.glob("*.md"))
    all_content = ""
    for f in md_files:
        try:
            all_content += f.read_text(encoding="utf-8") + "\n"
        except OSError:
            pass

    if not all_content.strip():
        return [
            {
                "rule_id": "tables_figures.empty_drafts",
                "severity": "P1",
                "message": "No content in draft files",
                "recommendation": "Generate section content before validation.",
            }
        ]

    findings: list[dict[str, Any]] = []

    # Check for markdown tables
    tables = re.findall(r"\|.+\|.+\|", all_content)
    if not tables:
        findings.append(
            {
                "rule_id": "tables_figures.no_tables",
                "severity": "P1",
                "message": "No markdown tables found in draft sections",
                "recommendation": (
                    "Add at least a study characteristics table "
                    "and a comparison table to the results section."
                ),
            }
        )

    # Check for mermaid diagrams
    mermaid_blocks = re.findall(r"```mermaid.*?```", all_content, re.DOTALL)
    if not mermaid_blocks:
        findings.append(
            {
                "rule_id": "tables_figures.no_figures",
                "severity": "P2",
                "message": "No mermaid diagrams found in draft sections",
                "recommendation": (
                    "Add a PRISMA flow diagram using mermaid syntax to the methods section."
                ),
            }
        )

    # Check for specific table types by keyword
    content_lower = all_content.lower()
    if "study_characteristics" in required_tables:
        has_study_table = (
            "study" in content_lower
            and ("characteristic" in content_lower or "comparison" in content_lower)
            and len(tables) > 0
        )
        if not has_study_table and not tables:
            findings.append(
                {
                    "rule_id": "tables_figures.no_study_table",
                    "severity": "P1",
                    "message": "Study characteristics table missing",
                    "recommendation": (
                        "Include a markdown table summarizing study "
                        "characteristics (year, venue, methodology, findings)."
                    ),
                }
            )

    return findings
