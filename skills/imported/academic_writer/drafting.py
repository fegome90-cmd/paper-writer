"""Academic writer skill using prompts from source SKILL.md.

The source skill at /Users/felipe_gonzalez/Developer/examen_grado/skills/academic-writer/
is a **prompt collection** — 7 section prompts for Q1 journal papers.
There is NO executable Python code in the source.

This module reads section structures from the vendored SKILL.md and
generates section skeletons. It does NOT call an LLM — for real content,
use the SKILL.md prompts directly with an LLM.

**Adaptation truth:**
- Section structure (CARS model for intro, CONSORT flow for methods, etc.)
  is extracted from the SKILL.md prompt guidelines.
- Tone rules ("human-like, conversational academic") inform the template style.
- Citation formatting follows APA 7th as specified in the prompts.
- The actual prompt text is preserved verbatim in SKILL.md for manual use.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _extract_cite_keys(bib_path: Path) -> list[str]:
    """Extract citation keys from a BibTeX file."""
    if not bib_path.exists():
        return []
    content = bib_path.read_text(encoding="utf-8")
    return re.findall(r"@\w+\{(\w+)", content)


def _evidence_cite_keys(evidence: list[dict[str, Any]]) -> list[str]:
    """Derive citation keys from evidence entries (firstauthorYEAR)."""
    keys: list[str] = []
    for entry in evidence:
        authors = str(entry.get("authors", "unknown"))
        first_author = authors.split(",")[0].strip().split()[-1].lower()
        year = entry.get("year", 2024)
        keys.append(f"@{first_author}{year}")
    return keys


# Section structures derived from SKILL.md prompt guidelines.
# Each section follows the structure specified in the corresponding prompt.
# The SKILL.md contains the FULL prompts with {placeholders} for manual use.
_SECTION_STRUCTURES: dict[str, dict[str, Any]] = {
    "introduction": {
        "model": "CARS",
        "subsections": [
            "Establish territory — why the topic matters",
            "Identify niche — what is missing or uncertain",
            "Occupy niche — purpose and direction of study",
        ],
        "tone": "human-like conversational academic with varied sentence lengths",
    },
    "methods": {
        "model": "CONSORT/PRISMA",
        "subsections": [
            "Study design and justification",
            "Setting and timeframe",
            "Ethics statement",
            "Participants/sampling with inclusion criteria",
            "Instruments and measures",
            "Data collection procedure",
            "Statistical analysis plan",
        ],
        "tone": "past tense, detailed enough for replication",
    },
    "results": {
        "model": "APA 7th reporting",
        "subsections": [
            "Descriptive statistics / demographics",
            "Main analyses with test statistics, df, p-values, effect sizes",
            "Secondary analyses",
            "Negative or non-significant results",
        ],
        "tone": "careful researcher presenting evidence, past tense",
    },
    "discussion": {
        "model": "critical synthesis",
        "subsections": [
            "Summary of key findings",
            "Comparison with previous literature",
            "Theoretical and practical implications",
            "Limitations and their impact",
            "Future research recommendations",
        ],
        "tone": "intelligent, natural, critical, 1000-1200 words",
    },
}


def draft_outline(
    evidence_path: Path,
    output_dir: Path,
    bib_path: Path,
) -> dict[str, Any]:
    """Create outline from screened evidence.

    Structure follows the CARS model and section guidelines from SKILL.md.

    Args:
        evidence_path: Path to screened_evidence.json.
        output_dir: Directory where outline.md is written.
        bib_path: Path to references.bib for citation key extraction.

    Returns:
        Dict with 'artifacts' list of created file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_data = json.loads(evidence_path.read_text(encoding="utf-8"))
    query = str(evidence_data.get("query", "unknown topic"))
    evidence_items = list(evidence_data.get("evidence", []))

    cite_keys = _extract_cite_keys(bib_path)
    ev_keys = _evidence_cite_keys(evidence_items)
    all_refs = cite_keys + ev_keys
    ref_list = ", ".join(all_refs[:8]) if all_refs else "see bibliography"

    lines: list[str] = [
        f"# Outline — {query}",
        "",
        "<!--",
        "Structure follows CARS model and section guidelines from SKILL.md.",
        "For full prompts, see skills/imported/academic-writer/SKILL.md",
        "Source: /Users/felipe_gonzalez/Developer/examen_grado/skills/academic-writer/",
        "-->",
        "",
        "## 1. Introduction (CARS model)",
        f"   - Establish territory: clinical significance of {query} [{ref_list}]",
        "   - Identify niche: what is missing or uncertain in current research",
        "   - Occupy niche: purpose, objectives, and direction of this study",
        "",
        "## 2. Methods (CONSORT/PRISMA flow)",
        "   - Study design and justification",
        "   - Setting, timeframe, ethics approval",
        "   - Participants: population, sampling, inclusion/exclusion criteria",
        "   - Instruments and measures with psychometric properties",
        "   - Data collection procedure (chronological)",
        "   - Statistical analysis plan (tests, significance level, software)",
        "",
        "## 3. Results (APA 7th reporting)",
        f"   - Study characteristics [{ref_list}]",
        "   - Descriptive statistics and demographics",
        "   - Main analyses: test statistics, df, p-values, effect sizes",
        "   - Secondary and non-significant results",
        "",
        "## 4. Discussion (critical synthesis, 1000-1200 words)",
        "   - Summary of key findings with comparison to prior literature",
        "   - Theoretical and practical implications",
        "   - Limitations and their potential impact on findings",
        "   - Future research recommendations",
        "",
    ]
    outline_path = output_dir / "outline.md"
    outline_path.write_text("\n".join(lines), encoding="utf-8")
    return {"artifacts": [str(outline_path)]}


def draft_section(
    section_name: str,
    outline_path: Path,
    evidence_path: Path,
    bib_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Draft a section skeleton following SKILL.md prompt structure.

    The generated skeleton provides the STRUCTURE from the source prompts.
    For real content, use the SKILL.md prompts with an LLM.

    Args:
        section_name: One of: introduction, methods, results, discussion.
        outline_path: Path to outline.md (for context).
        evidence_path: Path to screened_evidence.json.
        bib_path: Path to references.bib.
        output_dir: Directory where the section markdown is written.

    Returns:
        Dict with 'artifacts' list of created file paths.

    Raises:
        ValueError: If section_name is not recognized.
    """
    key = section_name.lower().strip()
    if key not in _SECTION_STRUCTURES:
        raise ValueError(
            f"Unknown section: {section_name}. "
            f"Available: {', '.join(_SECTION_STRUCTURES)}"
        )

    structure = _SECTION_STRUCTURES[key]
    output_dir.mkdir(parents=True, exist_ok=True)

    evidence_data = json.loads(evidence_path.read_text(encoding="utf-8"))
    query = str(evidence_data.get("query", "unknown topic"))
    evidence_items = list(evidence_data.get("evidence", []))
    total = len(evidence_items)

    cite_keys = _extract_cite_keys(bib_path)
    ev_keys = _evidence_cite_keys(evidence_items)
    all_refs = cite_keys + ev_keys
    ref_list = ", ".join(all_refs[:8]) if all_refs else "see bibliography"

    lines = [
        f"# {key.capitalize()}",
        "",
        "<!--",
        f"Structure: {structure['model']} model from SKILL.md",
        f"Tone: {structure['tone']}",
        "For full prompt, see skills/imported/academic-writer/SKILL.md",
        "-->",
        "",
    ]

    for sub in structure["subsections"]:
        lines.append(f"## {sub}")
        lines.append(f"[Content placeholder: {sub} for {query} [{ref_list}]]")
        lines.append("")

    if key == "results" and total > 0:
        lines.append("## Evidence summary")
        lines.append(f"{total} studies included in evidence base.")
        for item in evidence_items[:5]:
            title = item.get("title", "Untitled")
            doi = item.get("doi", "no DOI")
            scoring = item.get("scoring", {})
            tier = scoring.get("tier", "unclassified")
            score = scoring.get("final_score", "N/A")
            lines.append(f"- **{title}** — {tier} (score: {score}) DOI: {doi}")
        lines.append("")

    section_path = output_dir / f"{key}.md"
    section_path.write_text("\n".join(lines), encoding="utf-8")
    return {"artifacts": [str(section_path)]}
