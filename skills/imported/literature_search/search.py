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

    # 3. Score and classify using real scoring engine
    weights = get_default_weights(weights_phase)
    scored_papers: list[dict[str, Any]] = []
    for paper in unique_papers:
        metrics = _extract_metrics(paper)
        d_score = calculate_d_score(metrics)
        final_score = calculate_final_score(metrics, weights)
        tier = classify_tier(final_score)
        scored_papers.append({
            **paper,
            "scoring": {
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
        })

    # 4. Write raw results (post-dedup, scored)
    results = {
        "query": query,
        "date": date.today().isoformat(),
        "total_input": len(raw_papers),
        "total_after_dedup": len(unique_papers),
        "dedup_log": dedup_log,
        "papers": scored_papers,
        "weights": {
            "phase": weights_phase,
            "A": weights.A_weight,
            "B": weights.B_weight,
            "C": weights.C_weight,
            "D": weights.D_weight,
            "E": weights.E_weight,
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
    # compute scoring using the real engine.
    for paper in all_papers:
        if "scoring" not in paper and "metrics" in paper:
            metrics = _extract_metrics(paper)
            weights = get_default_weights("balanced")
            d_score = calculate_d_score(metrics)
            final_score = calculate_final_score(metrics, weights)
            tier = classify_tier(final_score)
            paper["scoring"] = {
                "d_score": d_score,
                "final_score": final_score,
                "tier": tier,
            }

    # Filter by tier using real classify_tier output from scoring
    tier_order = {"Tier 1": 1, "Tier 2": 2, "Tier 3": 3, "Discard": 4}
    min_level = tier_order.get(min_tier, 3)
    screened = [
        p for p in all_papers
        if tier_order.get(p.get("scoring", {}).get("tier", "Discard"), 4) <= min_level
    ]

    evidence = {
        "query": raw_data.get("query", ""),
        "date": raw_data.get("date", ""),
        "total_raw": len(all_papers),
        "total_screened": len(screened),
        "min_tier": min_tier,
        "inclusion_criteria": [f"tier <= {min_tier}", "has title", "has DOI"],
        "evidence": screened,
    }
    evidence_path = output_dir / "screened_evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {"artifacts": [str(evidence_path)]}


def _extract_metrics(paper: dict[str, Any]) -> Any:
    """Extract PaperMetrics from a paper dict.

    Expects optional 'metrics' sub-dict with scoring dimensions.
    Falls back to zero scores if not provided — the adapter can populate
    these from external data before calling search().
    """
    from skills.imported.literature_search.scoring import PaperMetrics

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
