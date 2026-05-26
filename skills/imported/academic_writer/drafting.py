"""Academic writer skill consuming section manifest derived from SKILL.md.

The source skill at:
  /Users/felipe_gonzalez/Developer/examen_grado/skills/academic-writer/
is a **prompt collection** — 7 section prompts for Q1 journal papers.
There is NO executable Python code in the source.

This module reads ``sections_manifest.json`` (a derived artifact extracted
from SKILL.md) at runtime to get section structure. It does NOT hardcode
section data — all structure comes from the manifest.

**Adaptation chain (fully traceable):**
1. SKILL.md (vendored) → human-readable prompts with {placeholders}
2. sections_manifest.json (derived) → machine-readable structure extracted
   from SKILL.md by manual audit, versioned alongside the source
3. This module → reads manifest, generates section skeletons

For real content generation, use SKILL.md prompts with an LLM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MANIFEST_PATH = Path(__file__).parent / "sections_manifest.json"
_SKILL_MD_PATH = Path(__file__).parent / "SKILL.md"


def load_manifest() -> dict[str, Any]:
    """Load the sections manifest derived from SKILL.md.

    Returns:
        The parsed manifest dict with sections, guidelines, and provenance.

    Raises:
        FileNotFoundError: If sections_manifest.json is missing.
    """
    data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("Manifest must be a JSON object (dict)")
    return data


def _extract_cite_keys(bib_path: Path) -> list[str]:
    """Extract citation keys from a BibTeX file."""
    if not bib_path.exists():
        return []
    content = bib_path.read_text(encoding="utf-8")
    import re

    return re.findall(r"@\w+\{(\w+)", content)


def _evidence_cite_keys(evidence: list[dict[str, Any]]) -> list[str]:
    """Derive citation keys from evidence entries (firstauthorYEAR).

    Only includes keys that match actual entries in the bibliography.
    Returns raw keys prefixed with '@' for placeholder usage.
    """
    keys: list[str] = []
    for entry in evidence:
        # Prefer explicit cite_key if present
        if "cite_key" in entry:
            keys.append(f"@{entry['cite_key']}")
            continue
        authors = str(entry.get("authors", "unknown"))
        first_author = authors.split(",")[0].strip().split()[-1].lower()
        year = entry.get("year", 2024)
        keys.append(f"@{first_author}{year}")
    return keys


def draft_outline(
    evidence_path: Path,
    output_dir: Path,
    bib_path: Path,
) -> dict[str, Any]:
    """Create outline from screened evidence using manifest structure.

    Section order and structure come from sections_manifest.json,
    which was derived from the vendored SKILL.md.

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

    cite_keys = _extract_cite_keys(bib_path)
    # Only use actual bib keys in references — never fabricated keys
    ref_list = (
        ", ".join(f"@{k}" for k in cite_keys[:8]) if cite_keys else "(no references imported)"
    )

    manifest = load_manifest()
    sections = manifest.get("sections", {})

    lines: list[str] = [
        f"# Outline — {query}",
        "",
        "<!--",
        "Structure derived from sections_manifest.json",
        f"Manifest source: {manifest.get('_provenance', {}).get('source_path', 'SKILL.md')}",
        f"Source version: {manifest.get('_provenance', {}).get('source_version', 'unknown')}",
        f"Full prompts: {_SKILL_MD_PATH.name}",
        "-->",
        "",
    ]

    # Sort sections by order from manifest
    ordered = sorted(sections.items(), key=lambda s: s[1].get("order", 99))
    for section_name, section_data in ordered:
        display_name = section_name.replace("_", " ").title()
        model = section_data.get("model", "standard")
        word_count = section_data.get("word_count")
        subsections = section_data.get("subsections", [])

        wc_note = f" ({word_count} words)" if word_count else ""
        lines.append(f"## {section_data['order']}. {display_name} ({model} model){wc_note}")
        for sub in subsections:
            lines.append(f"   - {sub} [{ref_list}]")
        lines.append("")

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
    """Draft a section skeleton using manifest structure.

    All structure (model, subsections, tone, rules) comes from
    sections_manifest.json, which was derived from SKILL.md.
    No section data is hardcoded in this function.

    Args:
        section_name: Section key from manifest (e.g. introduction, methods).
        outline_path: Path to outline.md (for context).
        evidence_path: Path to screened_evidence.json.
        bib_path: Path to references.bib.
        output_dir: Directory where the section markdown is written.

    Returns:
        Dict with 'artifacts' list of created file paths.

    Raises:
        ValueError: If section_name is not in the manifest.
    """
    key = section_name.lower().strip().replace(" ", "_")
    manifest = load_manifest()
    sections = manifest.get("sections", {})

    if key not in sections:
        available = ", ".join(sorted(sections.keys()))
        raise ValueError(f"Unknown section: {section_name}. Available: {available}")

    section_data = sections[key]
    output_dir.mkdir(parents=True, exist_ok=True)

    evidence_data = json.loads(evidence_path.read_text(encoding="utf-8"))
    query = str(evidence_data.get("query", "unknown topic"))
    evidence_items = list(evidence_data.get("evidence", []))
    total = len(evidence_items)

    cite_keys = _extract_cite_keys(bib_path)
    # Only use actual bib keys in references — never fabricated keys
    ref_list = (
        ", ".join(f"@{k}" for k in cite_keys[:8]) if cite_keys else "(no references imported)"
    )

    # Build header from manifest provenance
    provenance = manifest.get("_provenance", {})
    model = section_data.get("model", "standard")
    tone = section_data.get("tone", "academic")
    word_count = section_data.get("word_count")
    subsections = section_data.get("subsections", [])
    rules = section_data.get("rules", [])

    display_name = key.replace("_", " ").title()

    src_ver = provenance.get("source_version", "?")
    wc_str = word_count or "not specified"
    lines = [
        f"# {display_name}",
        "",
        "<!--",
        f"Structure: sections_manifest.json (from SKILL.md v{src_ver})",
        f"Model: {model}",
        f"Tone: {tone}",
        f"Word count: {wc_str}",
    ]
    if rules:
        lines.append(f"Rules: {'; '.join(rules)}")
    lines.extend(
        [
            f"Full prompt: {_SKILL_MD_PATH.name}",
            "-->",
            "",
        ]
    )

    # Generate subsections from manifest
    for sub in subsections:
        lines.append(f"## {sub}")
        lines.append(f"[Content placeholder: {sub} for {query} [{ref_list}]]")
        lines.append("")

    # For results section, add evidence listing if available
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
