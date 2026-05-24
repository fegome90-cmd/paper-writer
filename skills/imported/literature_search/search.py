"""Simplified literature search skill for Phase 3 MVP.

Generates structured search artifacts from a query using semantic placeholders.
Does NOT call real APIs yet — produces realistic-looking results based on
the query terms.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

_QUERY_PAPER_TEMPLATES: list[dict[str, str]] = [
    {
        "title_suffix": "a systematic review and meta-analysis",
        "template": (
            "Background: Understanding {topic} remains a critical challenge in "
            "clinical practice. Objective: To systematically review the evidence "
            "on {topic} and quantify effect sizes where possible. Methods: We "
            "searched PubMed, Embase, and CINAHL for studies published between "
            "2019 and 2024. Results: {n} studies met inclusion criteria. "
            "Conclusion: Further research is needed on {topic}."
        ),
    },
    {
        "title_suffix": "prevalence and associated factors",
        "template": (
            "Objective: To estimate the prevalence of {topic} and identify "
            "associated risk factors. Methods: Cross-sectional study of patients "
            "presenting with {topic}-related complaints (n={n}). Results: "
            "Prevalence was {pct}%. Significant predictors included age, duration "
            "of exposure, and training intensity. Conclusion: {topic} is highly "
            "prevalent and warrants routine screening."
        ),
    },
    {
        "title_suffix": "diagnostic accuracy and clinical utility",
        "template": (
            "Purpose: To evaluate diagnostic approaches for {topic}. Methods: "
            "Prospective cohort of {n} consecutive patients assessed with "
            "standardized protocols. Results: Sensitivity ranged from 72% to 94% "
            "across modalities. Conclusion: A multimodal assessment strategy is "
            "recommended for {topic}."
        ),
    },
    {
        "title_suffix": "longitudinal outcomes and prognostic indicators",
        "template": (
            "Background: Long-term outcomes of {topic} are poorly characterized. "
            "Methods: We followed {n} patients over 24 months. Results: "
            "Approximately 60% showed improvement, 25% remained stable, and 15% "
            "deteriorated. Conclusion: Early intervention for {topic} is "
            "associated with better prognosis."
        ),
    },
    {
        "title_suffix": "assessment tool validation and reliability",
        "template": (
            "Objective: To validate a screening instrument for {topic}. "
            "Methods: {n} participants completed the instrument; inter-rater "
            "reliability (kappa = 0.82) and internal consistency (alpha = 0.89) "
            "were computed. Conclusion: The instrument demonstrates strong "
            "psychometric properties for {topic}."
        ),
    },
]

_AUTHOR_POOL = [
    "Smith JR",
    "Garcia M",
    "Chen L",
    "Patel A",
    "Kim S",
    "Johansson K",
    "Müller R",
    "Nakamura T",
    "O'Brien E",
    "Santos V",
]


def _generate_papers(query: str) -> list[dict[str, Any]]:
    """Generate semantically relevant placeholder papers from a query."""
    topic = query.strip()
    papers: list[dict[str, Any]] = []
    for idx, tpl in enumerate(_QUERY_PAPER_TEMPLATES):
        n = 120 + idx * 47
        pct = 18 + idx * 6
        authors = _AUTHOR_POOL[: 3 + (idx % 3)]
        year = 2020 + idx
        abstract = tpl["template"].format(topic=topic, n=n, pct=pct)
        papers.append(
            {
                "title": f"{topic}: {tpl['title_suffix']}",
                "doi": f"10.1000/example-{2024 - idx}.{100 + idx}",
                "year": year,
                "authors": ", ".join(authors),
                "abstract": abstract,
            }
        )
    return papers


class LiteratureSearchSkill:
    """Simplified literature search skill.

    In production, this would call PubMed, Semantic Scholar, etc.
    For Phase 3 MVP, it generates structured search artifacts from a query.
    """

    def search(self, query: str, output_dir: Path) -> dict[str, Any]:
        """Execute search and return artifact paths.

        Args:
            query: The literature search query string.
            output_dir: Directory where search artifacts are written.

        Returns:
            Dict with 'artifacts' list of created file paths.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        search_plan_path = output_dir / "search_plan.json"
        raw_results_path = output_dir / "raw_results.json"

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
        }
        search_plan_path.write_text(
            json.dumps(search_plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        papers = _generate_papers(query)
        raw_results = {
            "query": query,
            "total_results": len(papers),
            "papers": papers,
        }
        raw_results_path.write_text(
            json.dumps(raw_results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "artifacts": [
                str(search_plan_path),
                str(raw_results_path),
            ],
        }

    def screen(self, search_dir: Path, output_dir: Path) -> dict[str, Any]:
        """Screen search results to produce an evidence set.

        Applies basic inclusion criteria: entry must have a non-empty title
        and a valid DOI.

        Args:
            search_dir: Directory containing raw_results.json.
            output_dir: Directory where screened_evidence.json is written.

        Returns:
            Dict with 'artifacts' list of created file paths.

        Raises:
            FileNotFoundError: If raw_results.json is missing.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        raw_path = search_dir / "raw_results.json"

        raw_data = json.loads(raw_path.read_text(encoding="utf-8"))
        all_papers = raw_data.get("papers", [])

        screened = [p for p in all_papers if p.get("title") and p.get("doi")]

        evidence_path = output_dir / "screened_evidence.json"
        evidence = {
            "query": raw_data.get("query", ""),
            "total_raw": len(all_papers),
            "total_screened": len(screened),
            "inclusion_criteria": ["has title", "has DOI"],
            "evidence": screened,
        }
        evidence_path.write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "artifacts": [str(evidence_path)],
        }
