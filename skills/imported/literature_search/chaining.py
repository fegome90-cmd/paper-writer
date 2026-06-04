"""Iterative search via Semantic Scholar API citation chaining.

Expands a seed set of papers by following citation graph edges:
- Backward chaining: references cited BY a paper (papers it builds on)
- Forward chaining: papers that CITE a paper (papers building on it)

Uses only stdlib (urllib.request) — no external dependencies.
Graceful degradation: returns empty results if API is down or rate-limited.

API docs: https://api.semanticscholar.org/api-docs/
Rate limit: 100 requests/5 minutes (no API key), 1000/5 min (with key).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Rate limiting: track last request time
_last_request_time: float = 0.0
_MIN_INTERVAL: float = 1.0  # seconds between requests (conservative)


def _api_get(url: str, timeout: float = 15.0) -> dict[str, Any] | None:
    """Make a rate-limited GET to Semantic Scholar API.

    Returns parsed JSON or None on failure. Never raises.
    """
    global _last_request_time

    # Rate limiting
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    try:
        api_key = os.environ.get("S2_API_KEY", "")
        headers = {"User-Agent": "paper-writer/1.0"}
        if api_key:
            headers["x-api-key"] = api_key

        req = Request(url, headers=headers)
        _last_request_time = time.monotonic()
        with urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = resp.read().decode("utf-8")
                return json.loads(data)  # type: ignore[no-any-return]
            return None
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def search_by_keyword(
    query: str,
    limit: int = 20,
    year: str | None = None,
    fields: str = "title,year,abstract,externalIds,citationCount",
) -> list[dict[str, Any]]:
    """Search Semantic Scholar by keyword query.

    Args:
        query: Search query string.
        limit: Max results (max 100).
        year: Year filter, e.g. "2020-2025".
        fields: Comma-separated fields to return.

    Returns:
        List of paper dicts, empty on failure.
    """
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={query}&limit={limit}&fields={fields}"
    )
    if year:
        url += f"&year={year}"

    result = _api_get(url)
    if result is None:
        return []

    return result.get("data", [])  # type: ignore[no-any-return]


def get_references(
    paper_id: str,
    limit: int = 50,
    fields: str = "title,year,abstract,externalIds,citationCount",
) -> list[dict[str, Any]]:
    """Get papers cited BY this paper (backward chaining).

    Args:
        paper_id: Semantic Scholar paper ID or DOI.
        limit: Max results.
        fields: Fields to return.

    Returns:
        List of paper dicts from references.
    """
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/references"
        f"?limit={limit}&fields={fields}"
    )

    result = _api_get(url)
    if result is None:
        return []

    # API returns {"data": [{"citedPaper": {...}}, ...]}
    refs = []
    for item in result.get("data", []):
        paper = item.get("citedPaper", {})
        if paper.get("paperId"):  # filter out null entries
            refs.append(paper)
    return refs


def get_citations(
    paper_id: str,
    limit: int = 50,
    fields: str = "title,year,abstract,externalIds,citationCount",
) -> list[dict[str, Any]]:
    """Get papers that CITE this paper (forward chaining).

    Args:
        paper_id: Semantic Scholar paper ID or DOI.
        limit: Max results.
        fields: Fields to return.

    Returns:
        List of paper dicts from citations.
    """
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"
        f"?limit={limit}&fields={fields}"
    )

    result = _api_get(url)
    if result is None:
        return []

    # API returns {"data": [{"citingPaper": {...}}, ...]}
    cites = []
    for item in result.get("data", []):
        paper = item.get("citingPaper", {})
        if paper.get("paperId"):
            cites.append(paper)
    return cites


def get_paper(
    paper_id: str,
    fields: str = "title,year,abstract,externalIds,citationCount,venue",
) -> dict[str, Any] | None:
    """Get a single paper's details by ID or DOI.

    Args:
        paper_id: Semantic Scholar paper ID, DOI, or arXiv ID.
        fields: Fields to return.

    Returns:
        Paper dict or None if not found.
    """
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
        f"?fields={fields}"
    )
    return _api_get(url)


def resolve_paper_id(paper: dict[str, Any]) -> str | None:
    """Resolve a paper dict to a Semantic Scholar paper ID.

    Tries: paperId → externalIds.DOI → externalIds.ArXiv.
    """
    # Direct S2 ID
    if paper.get("paperId"):
        return paper["paperId"]  # type: ignore[no-any-return]

    # DOI
    ext = paper.get("externalIds", {})
    if ext.get("DOI"):
        return f"DOI:{ext['DOI']}"

    # arXiv
    if ext.get("ArXiv"):
        return f"ArXiv:{ext['ArXiv']}"

    return None


def s2_paper_to_dict(paper: dict[str, Any], source: str = "chaining") -> dict[str, Any]:
    """Normalize a Semantic Scholar paper to our paper dict format.

    Args:
        paper: S2 API paper dict.
        source: Provenance tag ("chaining", "keyword_search").

    Returns:
        Normalized dict compatible with search.py pipeline.
    """
    ext = paper.get("externalIds", {}) or {}

    return {
        "title": paper.get("title", ""),
        "year": paper.get("year"),
        "abstract": paper.get("abstract", ""),
        "doi": ext.get("DOI", ""),
        "arxiv_id": ext.get("ArXiv", ""),
        "venue": paper.get("venue", ""),
        "citation_count": paper.get("citationCount"),
        "s2_id": paper.get("paperId", ""),
        "source": source,
    }


def iterative_search(
    seed_papers: list[dict[str, Any]],
    query: str,
    max_rounds: int = 3,
    max_papers: int = 80,
    relevance_threshold: float = 0.3,
) -> dict[str, Any]:
    """Run iterative citation chaining from seed papers.

    Algorithm:
    1. Start with seed_papers
    2. For each paper in frontier:
       a. Get references (backward chaining)
       b. Get citations (forward chaining)
    3. Score new papers for relevance to query
    4. Add relevant papers to corpus
    5. Repeat with new papers as frontier
    6. Stop when: max_rounds reached, max_papers reached, or saturation

    Args:
        seed_papers: Initial papers to start from.
        query: Research query for relevance filtering.
        max_rounds: Maximum chaining iterations.
        max_papers: Stop when corpus reaches this size.
        relevance_threshold: Minimum keyword overlap to include.

    Returns:
        Dict with: papers, provenance, stats.
    """
    from skills.imported.literature_search.scoring_cs import score_relevance

    # Track all papers by ID to avoid duplicates
    corpus: dict[str, dict[str, Any]] = {}
    provenance: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "rounds_completed": 0,
        "total_api_calls": 0,
        "papers_by_round": {},
        "saturation": False,
    }

    # Add seeds to corpus
    for paper in seed_papers:
        pid = resolve_paper_id(paper) or paper.get("doi") or paper.get("title", "")
        if pid and pid not in corpus:
            corpus[pid] = paper
            provenance.append({
                "paper_id": pid,
                "round": 0,
                "source": "seed",
                "chain_from": None,
            })

    stats["papers_by_round"][0] = len(corpus)

    # Iterative chaining
    frontier = list(corpus.keys())  # papers to expand

    for round_num in range(1, max_rounds + 1):
        if len(corpus) >= max_papers:
            break

        new_papers_this_round = 0
        next_frontier: list[str] = []

        for pid in frontier:
            if len(corpus) >= max_papers:
                break

            # Backward chaining (references)
            refs = get_references(pid, limit=20)
            stats["total_api_calls"] += 1

            for ref in refs:
                ref_id = ref.get("paperId")
                if not ref_id or ref_id in corpus:
                    continue
                if len(corpus) >= max_papers:
                    break

                # Quick relevance check
                title = ref.get("title", "")
                abstract = ref.get("abstract", "") or ""
                rel = score_relevance(query, title, abstract)
                if rel / 2.0 < relevance_threshold:
                    continue

                paper_dict = s2_paper_to_dict(ref, source="backward_chaining")
                corpus[ref_id] = paper_dict
                next_frontier.append(ref_id)
                provenance.append({
                    "paper_id": ref_id,
                    "round": round_num,
                    "source": "backward",
                    "chain_from": pid,
                })
                new_papers_this_round += 1

            # Forward chaining (citations)
            cites = get_citations(pid, limit=20)
            stats["total_api_calls"] += 1

            for cite in cites:
                cite_id = cite.get("paperId")
                if not cite_id or cite_id in corpus:
                    continue
                if len(corpus) >= max_papers:
                    break

                title = cite.get("title", "")
                abstract = cite.get("abstract", "") or ""
                rel = score_relevance(query, title, abstract)
                if rel / 2.0 < relevance_threshold:
                    continue

                paper_dict = s2_paper_to_dict(cite, source="forward_chaining")
                corpus[cite_id] = paper_dict
                next_frontier.append(cite_id)
                provenance.append({
                    "paper_id": cite_id,
                    "round": round_num,
                    "source": "forward",
                    "chain_from": pid,
                })
                new_papers_this_round += 1

        stats["papers_by_round"][round_num] = new_papers_this_round
        stats["rounds_completed"] = round_num

        # Saturation check
        if new_papers_this_round == 0:
            stats["saturation"] = True
            break

        frontier = next_frontier

    return {
        "papers": list(corpus.values()),
        "provenance": provenance,
        "stats": stats,
        "total_unique": len(corpus),
    }
