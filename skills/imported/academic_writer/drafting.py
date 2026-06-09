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
import re
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

    content = bib_path.read_text(encoding="utf-8", errors="replace")
    return re.findall(r"@\w+\{(\w+)", content)


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


def _enrich_section(
    lines: list[str],
    key: str,
    total: int,
    evidence_items: list[dict[str, Any]],
    evidence_path: Path,
    output_dir: Path,
) -> None:
    """Append structured enrichment (study table, PRISMA diagram) to section lines.

    Called by both LLM and fallback paths so enrichment is never skipped.
    All operations are wrapped in try/except for graceful degradation.
    """
    # Enrich results with structured study table
    if key == "results" and total > 0:
        lines.append("## Study Characteristics")
        lines.append("")
        try:
            from validators.table_figure import generate_study_table

            evidence_file = output_dir / "_evidence_for_table.json"
            evidence_file.write_text(
                json.dumps(
                    {"evidence": evidence_items},
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            table_md = generate_study_table(evidence_file, max_rows=30)
            lines.append(table_md)
            lines.append("")
            evidence_file.unlink(missing_ok=True)
        except (ValueError, OSError):
            lines.append(f"{total} studies included in evidence base.")
            for item in evidence_items[:5]:
                title = item.get("title", "Untitled")
                doi = item.get("doi", "no DOI")
                scoring = item.get("scoring", {})
                tier = scoring.get("tier", "unclassified")
                score = scoring.get("final_score", "N/A")
                lines.append(f"- **{title}** — {tier} (score: {score}) DOI: {doi}")
            lines.append("")

    # Enrich methods with PRISMA flow diagram
    if key == "methods":
        try:
            from validators.table_figure import generate_prisma_mermaid

            ev_file = Path(str(evidence_path))
            if ev_file.exists():
                mermaid = generate_prisma_mermaid(ev_file)
                lines.append("## PRISMA Flow Diagram")
                lines.append("")
                lines.append("```mermaid")
                lines.append(mermaid)
                lines.append("```")
                lines.append("")
        except (ValueError, OSError):
            pass


def _convert_citations(content: str, bib_path: Path) -> str:
    """Convert (Author, Year) citations to @key format using bib file.

    Gracefully degrades: if bib file missing or conversion fails,
    returns content unchanged.
    """
    if not content or not bib_path or not bib_path.is_file():
        return content or ""
    try:
        from validators.citation_format import convert_citations

        bib_text = bib_path.read_text(encoding="utf-8", errors="replace")
        return convert_citations(content, bib_text)
    except (ValueError, OSError, TypeError):
        return content


def draft_section(
    section_name: str,
    outline_path: Path,
    evidence_path: Path,
    bib_path: Path,
    output_dir: Path,
    outline_context: str = "",
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
        outline_context: Previous sections' content for cross-section coherence.

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

    # Try LLM-powered content generation first
    llm_content = _try_llm_generation(
        key=key,
        display_name=display_name,
        query=query,
        evidence_items=evidence_items,
        cite_keys=cite_keys,
        subsections=subsections,
        model=model,
        tone=tone,
        word_count=word_count,
        rules=rules,
        outline_context=outline_context,
    )

    if llm_content is not None:
        # LLM succeeded — prepend header, convert citations, append enrichment
        section_path = output_dir / f"{key}.md"
        header = "\n".join(lines) + "\n"
        # Convert (Author, Year) citations to @key format if bib exists
        converted_content = _convert_citations(llm_content, bib_path)
        # Build enrichment as separate block (goes AFTER LLM content)
        enrich_lines: list[str] = []
        _enrich_section(
            enrich_lines,
            key,
            total,
            evidence_items,
            evidence_path,
            output_dir,
        )
        enrich_block = "\n".join(enrich_lines) + "\n" if enrich_lines else ""
        section_path.write_text(
            header + converted_content + "\n" + enrich_block,
            encoding="utf-8",
        )
        return {"artifacts": [str(section_path)]}

    # Fallback: structural placeholders (no LLM available)
    for sub in subsections:
        lines.append(f"## {sub}")
        lines.append(f"[Content placeholder: {sub} for {query} [{ref_list}]]")
        lines.append("")

    _enrich_section(
        lines,
        key,
        total,
        evidence_items,
        evidence_path,
        output_dir,
    )

    section_path = output_dir / f"{key}.md"
    section_path.write_text("\n".join(lines), encoding="utf-8")
    return {"artifacts": [str(section_path)]}


def draft_all(
    outline_path: Path,
    evidence_path: Path,
    bib_path: Path,
    output_dir: Path,
    section_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Draft all sections in dependency order with cross-section context.

    Generates sections sequentially, passing previously generated
    content as outline_context to each subsequent section. The
    abstract is generated last (after all other sections) so it
    can summarize the complete manuscript.

    Args:
        outline_path: Path to outline.md.
        evidence_path: Path to screened_evidence.json.
        bib_path: Path to references.bib.
        output_dir: Directory where sections are written.
        section_keys: Optional explicit list of section keys.
            If None, uses all sections from manifest.

    Returns:
        Dict with 'artifacts' list and 'sections' dict mapping
        section names to their file paths.
    """
    manifest = load_manifest()
    sections_config = manifest.get("sections", {})

    if section_keys is None:
        section_keys = list(sections_config.keys())

    # Separate abstract from body sections
    abstract_key = "abstract"
    body_keys = [k for k in section_keys if k != abstract_key]

    # Sort body sections by their manifest order
    body_keys.sort(key=lambda k: sections_config.get(k, {}).get("order", 99))

    # Build generation order: body sections first, abstract last
    generation_order = body_keys[:]
    if abstract_key in section_keys and abstract_key in sections_config:
        generation_order.append(abstract_key)

    output_dir.mkdir(parents=True, exist_ok=True)

    all_artifacts: list[str] = []
    section_paths: dict[str, str] = {}
    context_parts: list[str] = []

    for section_key in generation_order:
        result = draft_section(
            section_name=section_key,
            outline_path=outline_path,
            evidence_path=evidence_path,
            bib_path=bib_path,
            output_dir=output_dir,
            outline_context="\n\n".join(context_parts) if context_parts else "",
        )

        all_artifacts.extend(result.get("artifacts", []))

        # Read generated content for cross-section context
        for artifact_path in result.get("artifacts", []):
            section_paths[section_key] = artifact_path
            try:
                content = Path(artifact_path).read_text(encoding="utf-8")
                # Truncate context to avoid token explosion
                # (keep first 500 chars per section as context summary)
                context_parts.append(content[:500])
            except OSError:
                pass

    return {
        "artifacts": all_artifacts,
        "sections": section_paths,
        "generation_order": generation_order,
    }


def _read_section_prompt(section_key: str) -> str | None:
    """Read the full prompt text for a section from SKILL.md.

    The SKILL.md has prompts under ### N. SectionName blocks.
    Returns the prompt text or None if not found.
    """
    if not _SKILL_MD_PATH.exists():
        return None

    content = _SKILL_MD_PATH.read_text(encoding="utf-8")

    # Map section keys to their heading names in SKILL.md
    name_map = {
        "abstract": "1. Abstract",
        "introduction": "2. Introduction",
        "literature_review": "3. Literature Review",
        "methods": "4. Methods",
        "results": "5. Results",
        "discussion": "6. Discussion",
        "conclusion": "7. Conclusion",
    }

    heading = name_map.get(section_key)
    if not heading:
        return None

    # Find the section: ### N. Name followed by a ``` block
    pattern = rf"### {re.escape(heading)}\s*\n\n```\n(.*?)```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()

    return None


def _try_llm_generation(
    key: str,
    display_name: str,
    query: str,
    evidence_items: list[dict[str, Any]],
    cite_keys: list[str],
    subsections: list[str],
    model: str,
    tone: str,
    word_count: str | None,
    rules: list[str],
    outline_context: str,
) -> str | None:
    """Attempt LLM-powered section generation. Returns content or None.

    Never raises. If LLM is unavailable or fails, returns None
    and the caller falls back to structural placeholders.

    Requires PAPER_LLM_CLI to be set to one of: pi, claude, codex, gemini, auto.
    Empty string (default) returns None — no LLM generation, uses placeholders.
    """
    import os

    # Gate: PAPER_LLM_CLI must be explicitly set (pi|claude|codex|gemini|auto)
    mode = os.environ.get("PAPER_LLM_CLI", "").lower()
    if mode not in ("pi", "claude", "codex", "gemini", "auto"):
        return None

    try:
        from clients.llm_content import generate_section
    except ImportError:
        return None

    # Read the full prompt from SKILL.md
    prompt_template = _read_section_prompt(key)
    if not prompt_template:
        return None

    result = generate_section(
        section_name=key,
        evidence=evidence_items,
        bib_keys=cite_keys,
        outline_context=outline_context,
    )

    if result.success:
        return result.text

    # LLM failed — log and fall back
    import sys

    print(
        f"  Note: LLM generation failed for {key}: {result.error}",
        file=sys.stderr,
    )
    return None
