"""Literature search skill using real scoring engine from source skill.

Applies imported scoring functions (deduplicate, classify_tier, ScoringWeights)
to search results. Does NOT call external APIs — that is the agent's job,
guided by SKILL.md.

The adapter layer (skills.local.adapters) calls this module, which in turn
uses the vendored scoring.py from:
  /Users/felipe_gonzalez/Developer/examen_grado/skills/literature-search/resources/scoring.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from skills.imported.literature_search.scoring import (
    PaperMetrics,
    calculate_d_score,
    calculate_final_score,
    classify_tier,
    deduplicate,
    get_default_weights,
)


def search(
    query: str,
    output_dir: Path,
    raw_papers: list[dict[str, Any]] | None = None,
    weights_phase: str = "balanced",
) -> dict[str, Any]:
    """Execute search pipeline: deduplicate → score → classify → write artifacts.

    When raw_papers is provided, applies the real scoring engine.
    When raw_papers is None, writes a search plan only (no results yet —
    the agent must follow SKILL.md to collect papers).

    Args:
        query: Research query string.
        output_dir: Directory for search artifacts.
        raw_papers: Papers collected by an external agent following SKILL.md.
                    If None, only a search plan is written.
        weights_phase: Scoring phase preset (balanced, problem_definition,
                       intervention_design, outcome_selection).

    Returns:
        Dict with 'artifacts' list of created file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[str] = []

    # 1. Write search plan
    search_plan = {
        "query": query,
        "date": date.today().isoformat(),
        "strategy": "systematic_keyword_search",
        "databases": ["PubMed", "Embase", "CINAHL", "Semantic Scholar"],
        "inclusion_criteria": [
            "Published between 2019 and 2024",
            "Peer-reviewed",
            "English language",
            f"Related to: {query}",
        ],
        "weights_phase": weights_phase,
    }
    plan_path = output_dir / "search_plan.json"
    plan_path.write_text(
        json.dumps(search_plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    artifacts.append(str(plan_path))

    if raw_papers is None:
        # No papers provided — agent must collect them following SKILL.md
        return {"artifacts": artifacts}

    # 2. Deduplicate using real scoring.deduplicate()
    unique_papers, dedup_log = deduplicate(raw_papers)

    # 3. Score and classify using domain-aware scoring engine
    scored_papers: list[dict[str, Any]] = []
    for paper in unique_papers:
        paper["_search_query"] = query  # available to _extract_metrics
        metrics = _extract_metrics(paper)
        domain = paper.get("_domain", "clinical")

        if domain == "cs":
            from skills.imported.literature_search.scoring_cs import (
                calculate_cs_final_score,
                get_default_cs_weights,
            )

            cs_weights = get_default_cs_weights(weights_phase)
            final_score = calculate_cs_final_score(metrics, cs_weights)
            tier = classify_tier(final_score)
            scored_papers.append(
                {
                    **paper,
                    "scoring": {
                        "domain": "cs",
                        "final_score": final_score,
                        "tier": tier,
                        "venue_tier": metrics.venue_tier,
                        "recency_score": metrics.recency_score,
                        "citation_score": metrics.citation_score,
                        "relevance_score": metrics.relevance_score,
                        "rigor_score": metrics.rigor_score,
                    },
                }
            )
        else:
            weights = get_default_weights(weights_phase)
            d_score = calculate_d_score(metrics)
            final_score = calculate_final_score(metrics, weights)
            tier = classify_tier(final_score)
            scored_papers.append(
                {
                    **paper,
                    "scoring": {
                        "domain": "clinical",
                        "d_score": d_score,
                        "final_score": final_score,
                        "tier": tier,
                        "population_score": metrics.population_score,
                        "intervention_score": metrics.intervention_score,
                        "outcome_score": metrics.outcome_score,
                        "context_score": metrics.context_score,
                        "evidence_score": metrics.evidence_score,
                        "sample_score": metrics.sample_score,
                        "journal_score": metrics.journal_score,
                        "citations_score": metrics.citations_score,
                        "coi_penalty": metrics.coi_penalty,
                    },
                }
            )

    # 4. Write raw results (post-dedup, scored)
    # Use clinical weights for metadata output (backward compat with raw_results format)
    clinical_weights = get_default_weights(weights_phase)
    results = {
        "query": query,
        "date": date.today().isoformat(),
        "total_input": len(raw_papers),
        "total_after_dedup": len(unique_papers),
        "dedup_log": dedup_log,
        "papers": scored_papers,
        "weights": {
            "phase": weights_phase,
            "A": clinical_weights.A_weight,
            "B": clinical_weights.B_weight,
            "C": clinical_weights.C_weight,
            "D": clinical_weights.D_weight,
            "E": clinical_weights.E_weight,
        },
    }
    results_path = output_dir / "raw_results.json"
    results_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    artifacts.append(str(results_path))

    return {"artifacts": artifacts}


def screen(
    search_dir: Path,
    output_dir: Path,
    min_tier: str = "Tier 3",
) -> dict[str, Any]:
    """Screen scored search results by tier threshold.

    Reads raw_results.json (produced by search()), filters by tier,
    and writes screened_evidence.json.

    Args:
        search_dir: Directory containing raw_results.json.
        output_dir: Directory for screened_evidence.json.
        min_tier: Minimum tier to include (Tier 1, Tier 2, Tier 3).
                  Papers classified as "Discard" are always excluded.

    Returns:
        Dict with 'artifacts' list of created file paths.

    Raises:
        FileNotFoundError: If raw_results.json is missing.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = search_dir / "raw_results.json"
    raw_data = json.loads(raw_path.read_text(encoding="utf-8"))
    all_papers = raw_data.get("papers", [])

    # If papers have metrics but no scoring (e.g. fallback data),
    # compute scoring using the domain-aware engine.
    for paper in all_papers:
        if "scoring" not in paper and "metrics" in paper:
            metrics = _extract_metrics(paper)
            domain = paper.get("_domain", "clinical")

            if domain == "cs":
                from skills.imported.literature_search.scoring_cs import (
                    calculate_cs_final_score,
                    get_default_cs_weights,
                )

                cs_weights = get_default_cs_weights("balanced")
                final_score = calculate_cs_final_score(metrics, cs_weights)
            else:
                weights = get_default_weights("balanced")
                calculate_d_score(metrics)
                final_score = calculate_final_score(metrics, weights)

            tier = classify_tier(final_score)
            paper["scoring"] = {
                "final_score": final_score,
                "tier": tier,
            }

    # Filter by tier using real classify_tier output from scoring
    tier_order = {"Tier 1": 1, "Tier 2": 2, "Tier 3": 3, "Discard": 4}
    if min_tier not in tier_order:
        raise ValueError(f"Invalid min_tier: {min_tier!r}. Must be one of: {', '.join(tier_order)}")
    min_level = tier_order[min_tier]
    screened = [
        p
        for p in all_papers
        if tier_order.get(p.get("scoring", {}).get("tier", "Discard"), 4) <= min_level
    ]

    # Build PRISMA 2020 flow data from source provenance and tier screening
    source_counts: dict[str, int] = {}
    for p in all_papers:
        src = p.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    # Count exclusions by reason
    excluded = [p for p in all_papers if p not in screened]
    exclusion_reasons: dict[str, int] = {}
    for p in excluded:
        tier = p.get("scoring", {}).get("tier", "Discard")
        reason = f"tier_{tier.lower().replace(' ', '_')}"
        exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1

    prisma_flow = {
        "identification": {
            "database_results": source_counts.get("backward_chaining", 0),
            "other_sources": source_counts.get("forward_chaining", 0)
            + source_counts.get("keyword_search", 0),
            "seed_papers": source_counts.get("seed", 0),
            "total_identified": len(all_papers),
            "duplicates_removed": raw_data.get("total_input", 0)
            - raw_data.get("total_after_dedup", len(all_papers)),
        },
        "screening": {
            "records_screened": len(all_papers),
            "records_excluded": len(excluded),
            "exclusion_reasons": exclusion_reasons,
        },
        "eligibility": {
            "records_assessed": len(screened),
            "records_excluded": 0,  # full-text exclusion (future: add full-text review)
        },
        "included": {
            "studies_in_synthesis": len(screened),
        },
    }

    evidence = {
        "query": raw_data.get("query", ""),
        "date": raw_data.get("date", ""),
        "total_raw": len(all_papers),
        "total_screened": len(screened),
        "min_tier": min_tier,
        "inclusion_criteria": [f"tier <= {min_tier}", "has title", "has DOI"],
        "prisma_flow": prisma_flow,
        "evidence": screened,
    }
    evidence_path = output_dir / "screened_evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {"artifacts": [str(evidence_path)]}


def _extract_metrics(paper: dict[str, Any]) -> Any:
    """Extract metrics from paper dict. Dispatches CS vs clinical based on content.

    For CS papers: returns CSMetrics from scoring_cs.
    For clinical papers: returns PaperMetrics from scoring.py (unchanged).
    Stores detected domain in paper['_domain'] for later routing.
    """
    from skills.imported.literature_search.scoring_cs import (
        detect_domain,
        extract_cs_metrics,
    )

    domain = detect_domain(paper)
    paper["_domain"] = domain

    if domain == "cs":
        query = paper.get("_search_query", paper.get("query", ""))
        return extract_cs_metrics(paper, query)

    # Existing PICO path — UNCHANGED
    m = paper.get("metrics", {})
    return PaperMetrics(
        population_score=float(m.get("population_score", 0.0)),
        intervention_score=float(m.get("intervention_score", 0.0)),
        outcome_score=float(m.get("outcome_score", 0.0)),
        evidence_score=float(m.get("evidence_score", 0.0)),
        sample_score=float(m.get("sample_score", 0.0)),
        journal_score=float(m.get("journal_score", 0.0)),
        citations_score=float(m.get("citations_score", 0.0)),
        coi_penalty=float(m.get("coi_penalty", 0.0)),
        context_score=float(m.get("context_score", 0.0)),
    )


def papers_to_bibtex(papers: list[dict[str, Any]]) -> str:
    """Convert screened papers to BibTeX entries.

    Generates a @article or @inproceedings entry for each paper.
    BibTeX key format: firstauthorYYYY_firstword (e.g., vaswani2017_attention).

    Args:
        papers: List of paper dicts with title, year, doi, authors, venue fields.

    Returns:
        BibTeX string with one entry per paper.
    """
    import re

    entries: list[str] = []

    for paper in papers:
        title = paper.get("title", "").strip()
        year = paper.get("year")
        doi = paper.get("doi", "").strip()
        authors = paper.get("authors", "").strip()
        venue = paper.get("venue", "").strip()
        arxiv_id = paper.get("arxiv_id", "").strip()

        if not title or not year:
            continue

        # Generate BibTeX key: firstauthor_year_firstword
        first_author = "unknown"
        if authors:
            first_author = authors.split(" and ")[0].split(",")[0].strip()
            # Normalize: lowercase, remove accents/spaces
            first_author = re.sub(r"[^a-z]", "", first_author.lower()) or "unknown"

        # First significant word from title
        title_words = re.findall(r"[a-zA-Z]+", title)
        first_word = title_words[0].lower() if title_words else "untitled"

        key = f"{first_author}{year}_{first_word}"

        # Deduplicate keys by appending letter suffix
        existing_keys = {e.split("{")[1].split(",")[0] for e in entries}
        if key in existing_keys:
            suffix = "b"
            while f"{key}{suffix}" in existing_keys:
                suffix = chr(ord(suffix) + 1)
            key = f"{key}{suffix}"

        # Build entry
        entry_type = "article"
        venue_tag = "journal"
        if venue and any(
            kw in venue.lower()
            for kw in [
                "conf",
                "proc",
                "neurips",
                "icml",
                "iclr",
                "emnlp",
                "acl",
                "naacl",
                "fse",
                "ase",
                "icse",
            ]
        ):
            entry_type = "inproceedings"
            venue_tag = "booktitle"

        lines = [f"@{entry_type}{{{key},"]
        lines.append(f"  title = {{{title}}},")
        if authors:
            lines.append(f"  author = {{{authors}}},")
        lines.append(f"  year = {{{year}}},")
        if venue:
            lines.append(f"  {venue_tag} = {{{venue}}},")
        if doi:
            lines.append(f"  doi = {{{doi}}},")
        if arxiv_id:
            lines.append(f"  eprint = {{{arxiv_id}}},")
        lines.append("}")

        entries.append("\n".join(lines))

    return "\n\n".join(entries)
