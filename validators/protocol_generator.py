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
from typing import Any


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
        return json.loads(path.read_text(encoding="utf-8"))
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
        lines.append(f"| Database results (backward chaining) | {ident.get('database_results', 0)} |\n")
        lines.append(f"| Other sources (forward chaining) | {ident.get('other_sources', 0)} |\n")
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
    """Build quality appraisal section."""
    appraisal = _load_json(search_dir / "quality_appraisal.json")

    lines = ["## 4. Quality Appraisal\n"]

    lines.append("**Method:** Weighted 5-dimension scoring\n")
    lines.append("| Dimension | Weight | Description |\n|---|---|---|\n")
    lines.append("| Venue reputation | 0.20 | Top-tier conference/journal |\n")
    lines.append("| Citation impact | 0.25 | Community validation proxy |\n")
    lines.append("| Methodology rigor | 0.25 | Experimental design signals |\n")
    lines.append("| Reproducibility | 0.15 | Open code/data availability |\n")
    lines.append("| Recency | 0.15 | Recent studies reflect current state |\n")

    if appraisal:
        summary = appraisal.get("summary", {})
        lines.append("\n**Results:**\n")
        lines.append(f"- Total appraised: {appraisal.get('total_appraised', 'N/A')}\n")
        lines.append(f"- High quality: {summary.get('high', 0)}\n")
        lines.append(f"- Moderate quality: {summary.get('moderate', 0)}\n")
        lines.append(f"- Low quality: {summary.get('low', 0)}\n")
        lines.append(f"- Very low quality: {summary.get('very_low', 0)}\n")
        lines.append(f"- Mean weighted score: {summary.get('mean_score', 'N/A')}\n")
    else:
        lines.append("\n*Quality appraisal data not yet generated.*\n")

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
                scoring_fields = [k for k in sample["scoring"].keys()]
                lines.append("\n**Scoring fields:**\n")
                for f in sorted(scoring_fields):
                    lines.append(f"- `{f}`\n")
    else:
        lines.append("*No data extraction details available.*\n")

    return "\n".join(lines) + "\n"


def _build_synthesis_method(search_dir: Path) -> str:
    """Build synthesis method section."""
    evidence = _load_json(search_dir / "screened_evidence.json")

    lines = ["## 6. Synthesis Method\n"]

    if evidence:
        total = evidence.get("total_screened", 0)
        lines.append(f"**Included studies:** {total}\n")
        lines.append("**Approach:** Narrative synthesis with structured evidence tables.\n")
        lines.append(
            "**Tooling:** Automated pipeline (search → chain → screen → export). "
            "Scoring via domain-adapted CS engine with balanced weights.\n"
        )
    else:
        lines.append("*No synthesis data available.*\n")

    return "\n".join(lines) + "\n"
