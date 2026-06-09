"""Verify artifacts generator — produces 4 mandatory publication-readiness artifacts.

Called during ``paper verify`` to generate structured outputs that document
the systematic review process and verify citation integrity:

1. **search_manifest.yaml** — query, databases, filters, timestamps, result counts
2. **evidence_matrix.csv** — one row per included study with scoring dimensions
3. **included_excluded_ledger.yaml** — PRISMA-style inclusion/exclusion decisions
4. **claim_citation_audit.yaml** — every [@key] citation in text mapped to bib entry
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import yaml

# Regex to find Pandoc citation markers: [@key], [@key, @key2], @key
# Supports: bracketed groups [@key, @key2] and bare @key after whitespace/start-of-line/punctuation
_CITATION_RE = re.compile(
    r"(?:\[([^\]]*@[^\]]*)\])|(?:(?<=\s)@(\w[\w:.#+-]*)|(?<=^)@(\w[\w:.#+-]*))", re.MULTILINE
)


def generate_verify_artifacts(
    search_dir: Path,
    draft_dir: Path,
    bib_path: Path,
    output_dir: Path,
) -> list[str]:
    """Generate all 4 mandatory verify artifacts.

    Args:
        search_dir: Directory containing search_plan.json, screened_evidence.json,
                    raw_results.json.
        draft_dir: Directory containing manuscript.md and section files.
        bib_path: Path to references.bib.
        output_dir: Directory where artifacts will be written.

    Returns:
        List of paths to generated artifact files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    generated.extend(_generate_search_manifest(search_dir, output_dir))
    generated.extend(_generate_evidence_matrix(search_dir, output_dir))
    generated.extend(_generate_included_excluded_ledger(search_dir, output_dir))
    generated.extend(_generate_claim_citation_audit(draft_dir, bib_path, output_dir))

    return generated


# ------------------------------------------------------------------
# Artifact 1: search_manifest.yaml
# ------------------------------------------------------------------


def _generate_search_manifest(search_dir: Path, output_dir: Path) -> list[str]:
    """Produce search_manifest.yaml from search_plan.json + screened_evidence.json."""
    plan_path = search_dir / "search_plan.json"
    screened_path = search_dir / "screened_evidence.json"
    raw_path = search_dir / "raw_results.json"

    if not plan_path.is_file():
        return []

    import json

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []

    manifest: dict[str, Any] = {
        "schema": "search_manifest_v1",
        "query": plan.get("query", ""),
        "strategy": plan.get("strategy", ""),
        "date": plan.get("date", ""),
        "databases": plan.get("databases", []),
        "inclusion_criteria": plan.get("inclusion_criteria", []),
        "filters": {
            "year_range": plan.get("year_range", ""),
            "language": plan.get("language", "English"),
        },
    }

    # Initialize results section before conditional augmentation
    manifest["results"] = {}

    if screened_path.is_file():
        try:
            screened = json.loads(screened_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            screened = {}
        manifest["results"].update(
            {
                "total_raw": screened.get("total_raw", 0),
                "total_screened": screened.get("total_screened", 0),
                "min_tier": screened.get("min_tier", ""),
            }
        )
        prisma = screened.get("prisma_flow", {})
        if prisma:
            manifest["prisma_flow"] = prisma

    # Raw results count
    if raw_path.is_file():
        try:
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raw = None
        if isinstance(raw, dict):
            manifest["results"]["raw_by_source"] = {
                k: len(v) if isinstance(v, list) else 1 for k, v in raw.items()
            }
        elif isinstance(raw, list):
            manifest["results"]["raw_count"] = len(raw)

    out_path = output_dir / "search_manifest.yaml"
    out_path.write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )
    return [str(out_path)]


# ------------------------------------------------------------------
# Artifact 2: evidence_matrix.csv
# ------------------------------------------------------------------


def _generate_evidence_matrix(search_dir: Path, output_dir: Path) -> list[str]:
    """Produce evidence_matrix.csv — one row per study with scoring dimensions."""
    screened_path = search_dir / "screened_evidence.json"
    if not screened_path.is_file():
        return []

    import json

    try:
        screened = json.loads(screened_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    evidence = screened.get("evidence", [])
    if not evidence:
        return []

    out_path = output_dir / "evidence_matrix.csv"
    fields = [
        "cite_key",
        "author",
        "year",
        "title",
        "tier",
        "final_score",
        "venue_tier",
        "recency_score",
        "citation_score",
        "relevance_score",
        "rigor_score",
        "domain",
        "doi",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for entry in evidence:
            scoring = entry.get("scoring", {})
            # Derive cite_key from DOI or title
            doi = entry.get("doi", "")
            cite_key = _derive_cite_key(entry)
            writer.writerow(
                {
                    "cite_key": cite_key,
                    "author": entry.get("author", ""),
                    "year": entry.get("year", ""),
                    "title": entry.get("title", ""),
                    "tier": scoring.get("tier", ""),
                    "final_score": scoring.get("final_score", ""),
                    "venue_tier": scoring.get("venue_tier", ""),
                    "recency_score": scoring.get("recency_score", ""),
                    "citation_score": scoring.get("citation_score", ""),
                    "relevance_score": scoring.get("relevance_score", ""),
                    "rigor_score": scoring.get("rigor_score", ""),
                    "domain": scoring.get("domain", ""),
                    "doi": doi,
                }
            )

    return [str(out_path)]


def _derive_cite_key(entry: dict[str, Any]) -> str:
    """Derive a citation key from entry metadata.

    Matches the format used in references.bib: lastnameYYYYkeyword.
    Handles both "Last, First" and "First Last" author formats.
    Falls back to DOI-based key if author/year are unavailable.
    """
    author = entry.get("author", "")
    year = entry.get("year", "")
    title = entry.get("title", "")

    if author and year:
        first_author = author.split(" and ")[0].strip()
        # Handle "Last, First" format (BibTeX convention)
        if "," in first_author:
            last_name = first_author.split(",")[0].strip().lower().replace(" ", "")
        else:
            # "First Last" format — take last word as surname
            parts = first_author.split()
            last_name = parts[-1].lower() if parts else ""
        # Take first meaningful word from title
        title_word = ""
        if title:
            for word in title.split():
                clean = re.sub(r"[^a-zA-Z]", "", word)
                if len(clean) > 3:
                    title_word = clean.lower()
                    break
        return f"{last_name}{year}{title_word}"

    # Fallback: DOI-based
    doi = entry.get("doi", "")
    if doi:
        return str(doi.split("/")[-1].replace(".", "_").replace("-", "_"))

    return "unknown"


# ------------------------------------------------------------------
# Artifact 3: included_excluded_ledger.yaml
# ------------------------------------------------------------------


def _generate_included_excluded_ledger(search_dir: Path, output_dir: Path) -> list[str]:
    """Produce included_excluded_ledger.yaml — PRISMA-style decisions."""
    screened_path = search_dir / "screened_evidence.json"
    if not screened_path.is_file():
        return []

    import json

    try:
        screened = json.loads(screened_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    evidence = screened.get("evidence", [])

    # Categorize by tier
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for entry in evidence:
        scoring = entry.get("scoring", {})
        tier = scoring.get("tier", "Discard")
        cite_key = _derive_cite_key(entry)
        record = {
            "cite_key": cite_key,
            "title": entry.get("title", ""),
            "author": entry.get("author", ""),
            "year": entry.get("year", ""),
            "tier": tier,
            "final_score": scoring.get("final_score", 0),
        }

        # Tier ranking: Tier 1 (best) > Tier 2 > Tier 3 > Discard
        if tier in ("Tier 1", "Tier 2", "Tier 3"):
            included.append(record)
        else:
            record["exclusion_reason"] = f"Tier below threshold: {tier}"
            excluded.append(record)

    ledger: dict[str, Any] = {
        "schema": "included_excluded_ledger_v1",
        "total_identified": screened.get("total_raw", 0),
        "included": included,
        "excluded": excluded,
        "summary": {
            "total_included": len(included),
            "total_excluded": len(excluded),
            "inclusion_rate": f"{len(included) / max(len(evidence), 1) * 100:.1f}%",
        },
    }

    out_path = output_dir / "included_excluded_ledger.yaml"
    out_path.write_text(
        yaml.dump(ledger, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )
    return [str(out_path)]


# ------------------------------------------------------------------
# Artifact 4: claim_citation_audit.yaml
# ------------------------------------------------------------------


def _generate_claim_citation_audit(draft_dir: Path, bib_path: Path, output_dir: Path) -> list[str]:
    """Produce claim_citation_audit.yaml — every [@key] mapped to bib entry.

    Scans all section .md files and the assembled manuscript for citation
    markers. Cross-references each key with the bibliography.
    """
    # Parse bib entries (key → title)
    bib_entries = _parse_bib_keys(bib_path)

    # Collect all citations from section files
    # Note: we scan individual sections only (NOT assembled manuscript)
    # to avoid double-counting citations that appear in both.
    citations: dict[str, dict[str, Any]] = {}

    for section_file in sorted(draft_dir.glob("*.md")):
        if section_file.name == "manuscript.md":
            continue  # Assembled manuscript = concatenation of sections; skip to avoid double-count
        _extract_citations_from_file(section_file, citations)

    # Build audit
    audited: list[dict[str, Any]] = []
    ok_count = 0
    missing_count = 0
    for key, info in sorted(citations.items()):
        bib_match = key in bib_entries
        if bib_match:
            ok_count += 1
        else:
            missing_count += 1

        audited.append(
            {
                "cite_key": key,
                "in_bibliography": bib_match,
                "bib_title": bib_entries.get(key, ""),
                "occurrences": info.get("count", 0),
                "sections": info.get("sections", []),
            }
        )

    audit: dict[str, Any] = {
        "schema": "claim_citation_audit_v1",
        "total_unique_citations": len(audited),
        "citations_in_bib": ok_count,
        "citations_missing_from_bib": missing_count,
        "bib_total_entries": len(bib_entries),
        "entries": audited,
    }

    out_path = output_dir / "claim_citation_audit.yaml"
    out_path.write_text(
        yaml.dump(audit, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )
    return [str(out_path)]


def _parse_bib_keys(bib_path: Path) -> dict[str, str]:
    """Extract cite keys → titles from a BibTeX file.

    Uses brace-counting to correctly handle nested braces in titles
    (e.g. ``{A {Bold} New Approach}``).
    """
    if not bib_path or not bib_path.is_file():
        return {}

    text = bib_path.read_text(encoding="utf-8")
    entries: dict[str, str] = {}
    key_re = re.compile(r"@(\w+)\{([^,\s]+),")
    title_start_re = re.compile(r"title\s*=\s*\{", re.IGNORECASE)

    # Split into entries
    parts = re.split(r"\n(?=@)", text)
    for part in parts:
        key_match = key_re.search(part)
        if not key_match:
            continue
        cite_key = key_match.group(2)
        title_match = title_start_re.search(part)
        if not title_match:
            entries[cite_key] = ""
            continue

        # Brace-counting extraction: find matching closing brace
        start = title_match.end()  # position after the opening {
        depth = 1
        pos = start
        while pos < len(part) and depth > 0:
            if part[pos] == "{":
                depth += 1
            elif part[pos] == "}":
                depth -= 1
            pos += 1
        entries[cite_key] = part[start : pos - 1] if depth == 0 else part[start:]

    return entries


def _extract_citations_from_file(file_path: Path, citations: dict[str, dict[str, Any]]) -> None:
    """Extract all citation keys from a markdown file and update the dict."""
    section_name = file_path.stem
    text = file_path.read_text(encoding="utf-8")

    for match in _CITATION_RE.finditer(text):
        full = match.group(1) or match.group(2) or ""
        # Parse individual keys from bracketed groups: [@key1, @key2]
        keys = re.findall(r"@([\w:.#+-]+)", full)
        if not keys and full.startswith("@"):
            keys = [full[1:]]

        for key in keys:
            if key not in citations:
                citations[key] = {"count": 0, "sections": []}
            citations[key]["count"] += 1
            if section_name not in citations[key]["sections"]:
                citations[key]["sections"].append(section_name)


def generate_academic_artifacts(
    project_root: Path,
    output_dir: Path,
) -> list[str]:
    """Generate academic-mode verify artifacts: screening_ledger.csv.

    Called after standard verify artifacts when mode=academic.
    Returns list of generated artifact paths.
    """
    generated: list[str] = []

    # Find screened_evidence.json
    latest_dir = project_root / "outputs" / "runs" / "latest"
    evidence_path = latest_dir / "search" / "screened_evidence.json"
    if not evidence_path.exists():
        return generated

    evidence_data = json.loads(evidence_path.read_text(encoding="utf-8"))
    screening_records = evidence_data.get("screening_records", [])
    if not screening_records:
        return generated

    # Generate screening_ledger.csv
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "screening_ledger.csv"

    lines = ["record_id,included,final_stage,exclusion_reason"]
    for rec in screening_records:
        record_id = rec.get("record_id", "unknown")
        included = rec.get("included", False)
        history = rec.get("screening_history", [])

        # Derive final stage and exclusion reason from history
        final_stage = "unknown"
        exclusion_reason = ""
        if history:
            last = history[-1]
            final_stage = last.get("stage", "unknown")
            if not included:
                exclusion_reason = last.get("reason", "")

        lines.append(f"{record_id},{included},{final_stage},{exclusion_reason}")

    ledger_path.write_text("\n".join(lines), encoding="utf-8")
    generated.append(str(ledger_path))

    # Generate metadata_resolution_report.md (stub — full implementation in PR3)
    report_path = output_dir / "metadata_resolution_report.md"
    report_lines = ["# Metadata Resolution Report\n"]
    for rec in evidence_data.get("evidence", []):
        doi = rec.get("doi", "unknown")
        meta = rec.get("metadata_resolution", {"status": "not_assessed"})
        status = meta.get("status", "not_assessed") if meta else "not_assessed"
        report_lines.append(f"- **{doi}**: {status}")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    generated.append(str(report_path))

    return generated
