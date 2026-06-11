"""Reproducibility protocol generator.

Aggregates pipeline metadata into a structured reproducibility protocol
document suitable for systematic review submission. Reads:

- raw_results.json (search query, scoring weights)
- chain_provenance.json (chaining parameters, API call counts)
- screened_evidence.json (PRISMA flow, inclusion criteria)
- quality_appraisal.json (if exists — quality ratings)
- state.yaml (pipeline stage progression)

Generates a Markdown protocol covering:
1. Search strategy (databases, query, chaining parameters)
2. Screening criteria (inclusion/exclusion)
3. Search results (PRISMA flow diagram data)
4. Quality appraisal (method and summary)
5. Data extraction (fields extracted per study)
6. Synthesis method (analytical approach)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def generate_protocol(
    search_dir: Path,
    output_path: Path | None = None,
    project_name: str = "paper-writer",
) -> str:
    """Generate a reproducibility protocol from pipeline metadata.

    Args:
        search_dir: Directory containing pipeline output files.
        output_path: Optional path to write protocol.md.
        project_name: Project name for the protocol header.

    Returns:
        Markdown protocol string.
    """
    if not search_dir:
        search_dir = Path(".")
    sections: list[str] = []

    # Header
    sections.append(
        f"# Reproducibility Protocol — {project_name}\n\n"
        "> Auto-generated from pipeline metadata. "
        "Review and supplement before submission.\n"
    )

    # 1. Search Strategy
    sections.append(_build_search_strategy(search_dir))

    # 2. Screening Criteria
    sections.append(_build_screening_criteria(search_dir))

    # 3. Search Results (PRISMA Flow)
    sections.append(_build_search_results(search_dir))

    # 4. Quality Appraisal
    sections.append(_build_quality_appraisal(search_dir))

    # 5. Data Extraction
    sections.append(_build_data_extraction(search_dir))

    # 6. Synthesis Method
    sections.append(_build_synthesis_method(search_dir))

    protocol = "\n".join(sections)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(protocol, encoding="utf-8")

    return protocol


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load JSON file, return None if missing."""
    if not path.exists():
        return None
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return None


def _build_search_strategy(search_dir: Path) -> str:
    """Build search strategy section from raw_results.json and provenance."""
    raw = _load_json(search_dir / "raw_results.json")
    provenance = _load_json(search_dir / "chain_provenance.json")

    lines = ["## 1. Search Strategy\n"]

    if raw:
        query = raw.get("query", "N/A")
        weights = raw.get("weights", {})
        total_input = raw.get("total_input", 0)
        lines.append(f"**Primary query:** `{query}`\n")
        lines.append(f"**Scoring weights phase:** {weights.get('phase', 'balanced')}\n")
        lines.append(f"**Initial seed papers:** {total_input}\n")
    else:
        lines.append("*No search data available.*\n")

    if provenance:
        stats = provenance.get("stats", {})
        lines.append("### Citation Chaining\n")
        lines.append(f"- **Rounds completed:** {stats.get('rounds_completed', 'N/A')}\n")
        lines.append(f"- **Total API calls:** {stats.get('total_api_calls', 'N/A')}\n")
        lines.append(f"- **Saturation:** {'Yes' if stats.get('saturation') else 'No'}\n")
        lines.append(f"- **Papers by round:** {stats.get('papers_by_round', {})}\n")
        lines.append(f"- **Total unique papers:** {provenance.get('total_unique', 'N/A')}\n")
    else:
        lines.append("*No chaining provenance available.*\n")

    return "\n".join(lines) + "\n"


def _build_screening_criteria(search_dir: Path) -> str:
    """Build screening criteria section."""
    evidence = _load_json(search_dir / "screened_evidence.json")

    lines = ["## 2. Screening Criteria\n"]

    if evidence:
        min_tier = evidence.get("min_tier", "N/A")
        criteria = evidence.get("inclusion_criteria", [])
        lines.append(f"**Minimum tier threshold:** {min_tier}\n")
        lines.append("**Inclusion criteria:**\n")
        for c in criteria:
            lines.append(f"- {c}\n")
    else:
        lines.append("*No screening data available.*\n")

    return "\n".join(lines) + "\n"


def _build_search_results(search_dir: Path) -> str:
    """Build PRISMA flow section."""
    evidence = _load_json(search_dir / "screened_evidence.json")

    lines = ["## 3. Search Results (PRISMA Flow)\n"]

    if evidence and "prisma_flow" in evidence:
        flow = evidence["prisma_flow"]

        ident = flow.get("identification", {})
        lines.append("### Identification\n")
        lines.append("| Source | Count |\n|---|---|\n")
        lines.append(
            f"| Database results | {ident.get('database_results', 0)} |\n"
        )
        lines.append(f"| Other sources | {ident.get('other_sources', 0)} |\n")
        lines.append(f"| Seed papers | {ident.get('seed_papers', 0)} |\n")
        lines.append(f"| **Total identified** | **{ident.get('total_identified', 0)}** |\n")
        lines.append(f"| Duplicates removed | {ident.get('duplicates_removed', 0)} |\n")

        scr = flow.get("screening", {})
        lines.append("\n### Screening\n")
        lines.append(f"- Records screened: {scr.get('records_screened', 0)}\n")
        lines.append(f"- Records excluded: {scr.get('records_excluded', 0)}\n")
        reasons = scr.get("exclusion_reasons", {})
        if reasons:
            lines.append("- Exclusion reasons:\n")
            for reason, count in reasons.items():
                lines.append(f"  - {reason}: {count}\n")

        elig = flow.get("eligibility", {})
        lines.append("\n### Eligibility\n")
        lines.append(f"- Records assessed: {elig.get('records_assessed', 0)}\n")
        lines.append(f"- Records excluded: {elig.get('records_excluded', 0)}\n")

        inc = flow.get("included", {})
        lines.append("\n### Included\n")
        lines.append(f"- **Studies in synthesis: {inc.get('studies_in_synthesis', 0)}**\n")
    else:
        lines.append("*No PRISMA flow data available.*\n")

    return "\n".join(lines) + "\n"


def _build_quality_appraisal(search_dir: Path) -> str:
    """Build quality appraisal section.

    When a quality_appraisal.json exists, derive the method description
    from the actual appraisal data (dimensions, weights, results).
    When no appraisal file exists, state honestly that appraisal was
    not performed — do NOT declare a method that was never executed.
    """
    appraisal = _load_json(search_dir / "quality_appraisal.json")

    lines = ["## 4. Quality Appraisal\n"]

    if appraisal:
        # Derive method from appraisal metadata when available
        method = appraisal.get("method", {})
        dimensions = method.get("dimensions", None)

        if dimensions:
            lines.append("**Method:** Weighted multi-dimension scoring\n")
            lines.append("| Dimension | Weight | Description |\n|---|---|---|\n")
            for dim_name, dim_info in dimensions.items():
                label = dim_name.replace("_", " ").title()
                weight = dim_info.get("weight", "N/A")
                desc = dim_info.get("description", "")
                lines.append(f"| {label} | {weight} | {desc} |\n")
        else:
            lines.append("**Method:** Quality appraisal performed.\n")

        summary = appraisal.get("summary", {})
        lines.append("\n**Results:**\n")
        lines.append(f"- Total appraised: {appraisal.get('total_appraised', 'N/A')}\n")
        lines.append(f"- High quality: {summary.get('high', 0)}\n")
        lines.append(f"- Moderate quality: {summary.get('moderate', 0)}\n")
        lines.append(f"- Low quality: {summary.get('low', 0)}\n")
        lines.append(f"- Very low quality: {summary.get('very_low', 0)}\n")
        lines.append(f"- Mean weighted score: {summary.get('mean_score', 'N/A')}\n")
    else:
        lines.append(
            "*Quality appraisal was not performed for this review. "
            "If appraisal is planned, the reviewer should declare the "
            "method, dimensions, and scoring criteria before execution.*\n"
        )

    return "\n".join(lines) + "\n"


def _build_data_extraction(search_dir: Path) -> str:
    """Build data extraction section."""
    raw = _load_json(search_dir / "raw_results.json")

    lines = ["## 5. Data Extraction\n"]

    if raw:
        papers = raw.get("papers", [])
        if papers:
            sample = papers[0]
            fields = [k for k in sample.keys() if k != "scoring"]
            lines.append("**Fields extracted per study:**\n")
            for f in sorted(fields):
                lines.append(f"- `{f}`\n")
            if "scoring" in sample:
                scoring_fields = list(sample["scoring"].keys())
                lines.append("\n**Scoring fields:**\n")
                for f in sorted(scoring_fields):
                    lines.append(f"- `{f}`\n")
    else:
        lines.append("*No data extraction details available.*\n")

    return "\n".join(lines) + "\n"


def _build_synthesis_method(search_dir: Path) -> str:
    """Build synthesis section from actual pipeline metadata."""
    evidence = _load_json(search_dir / "screened_evidence.json")
    raw = _load_json(search_dir / "raw_results.json")

    lines = ["## 6. Synthesis Method\n"]

    if evidence:
        total = evidence.get("total_screened", 0)
        lines.append(f"**Included studies:** {total}\n")

        # Derive scoring info from raw_results metadata
        weights = raw.get("weights", {}).get("phase", "unknown") if raw else "unknown"
        lines.append(f"**Scoring weights phase:** {weights}\n")

        # Derive quality appraisal availability
        has_quality = (search_dir / "quality_appraisal.json").exists()
        if has_quality:
            lines.append("**Quality appraisal:** Performed. See Section 4.\n")
        else:
            lines.append("**Quality appraisal:** Not performed.\n")

        # Describe pipeline tooling honestly
        lines.append(
            "**Tooling:** Automated pipeline (search → screen → export). "
            "See sections above for actual databases, criteria, and filters applied.\n"
        )

        # Warn about unverified claims
        lines.append(
            "> **Note:** Synthesis approach (narrative, meta-analysis, etc.) "
            "must be declared by the reviewer. This protocol documents the "
            "search and screening process, not the analytical framework.\n"
        )
    else:
        lines.append("*No synthesis data available.*\n")

    return "\n".join(lines) + "\n"
