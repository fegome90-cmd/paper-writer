"""Citation verification orchestrator.

Orchestrates Crossref and Semantic Scholar clients to verify all citations
in a manuscript. Classifies each citation as verified/partial/not_found/title_mismatch.
"""
from __future__ import annotations

import re
from typing import Any

from clients._text_similarity import TITLE_SIMILARITY_THRESHOLD
from clients.crossref import CrossrefClient, CrossrefResult
from clients.semantic_scholar import S2Result, SemanticScholarClient
from engine.deduplicator import deduplicate_findings
from parsers.manuscript import Manuscript

DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+")


class CitationVerifyValidator:
    """Orchestrate Crossref + Semantic Scholar to verify citations.

    When offline=True, returns P2 skipped findings without API calls.
    """

    def __init__(
        self,
        crossref_client: CrossrefClient | None = None,
        s2_client: SemanticScholarClient | None = None,
        offline: bool = False,
    ) -> None:
        self.offline = offline
        self.crossref_client = crossref_client or CrossrefClient(offline=offline)
        self.s2_client = s2_client or SemanticScholarClient(offline=offline)

    def validate(self, manuscript: Manuscript) -> list[dict[str, Any]]:
        """Verify all citations in the manuscript.

        Returns findings in paper-writer format.
        """
        citations = self._extract_citations(manuscript)
        findings: list[dict[str, Any]] = []

        for citation in citations:
            finding = self.verify_single(citation)
            if finding:
                findings.append(finding)

        return deduplicate_findings(findings)

    def verify_single(self, citation: dict[str, Any]) -> dict[str, Any] | None:
        """Verify a single citation. Used by ClaimAlignmentValidator.

        Returns a finding dict or None if citation is verified.
        """
        if self.offline:
            ref = citation.get("doi") or citation.get("title", "unknown")
            return self._make_finding(
                rule_id="citation_verify.skipped",
                severity="P2",
                message=f"Citation verification skipped (offline): {ref}",
                line=citation.get("line", 0),
                section=citation.get("section", "references"),
                evidence={"doi": citation.get("doi"), "title": citation.get("title")},
            )

        crossref = self._query_crossref(citation)
        s2 = self._query_s2(citation)

        verdict, _sev = self._classify_citation(crossref, s2)

        if verdict == "verified":
            return None

        ref = citation.get("doi") or citation.get("title", "unknown")

        if verdict == "not_found":
            return self._make_finding(
                rule_id="citation_verify.not_found",
                severity="P0",
                message=f"Citation not found in any database: {ref}",
                line=citation.get("line", 0),
                section=citation.get("section", "references"),
                evidence={
                    "doi": citation.get("doi"),
                    "crossref_found": crossref.found if crossref else False,
                    "s2_found": s2.found if s2 else False,
                },
            )

        if verdict == "title_mismatch":
            return self._make_finding(
                rule_id="citation_verify.title_mismatch",
                severity="P1",
                message=f"DOI resolves but title does not match: {ref}",
                line=citation.get("line", 0),
                section=citation.get("section", "references"),
                evidence={
                    "doi": citation.get("doi"),
                    "crossref_title": crossref.title if crossref else None,
                    "s2_title": s2.title if s2 else None,
                },
            )

        if verdict == "partial":
            return self._make_finding(
                rule_id="citation_verify.partial",
                severity="P2",
                message=f"Citation found in only one source: {ref}",
                line=citation.get("line", 0),
                section=citation.get("section", "references"),
                evidence={
                    "doi": citation.get("doi"),
                    "crossref_found": crossref.found if crossref else False,
                    "s2_found": s2.found if s2 else False,
                },
            )

        return None

    def _extract_citations(self, manuscript: Manuscript) -> list[dict[str, Any]]:
        """Extract DOIs and reference strings from the manuscript."""
        citations: list[dict[str, Any]] = []

        ref_section = manuscript.sections.get("references")
        if ref_section:
            # Track position iteratively to avoid str.find() fragility
            text = ref_section.text
            search_start = 0
            for line in text.split("\n"):
                stripped = line.strip()
                if not stripped:
                    search_start += len(line) + 1  # +1 for newline
                    continue

                # Find this line's position relative to search_start
                idx = text.find(stripped, search_start)
                if idx == -1:
                    idx = search_start
                offset = ref_section.line_start + text[:idx].count("\n") + 1
                search_start = idx + len(stripped)

                dois = DOI_PATTERN.findall(stripped)
                if dois:
                    for doi in dois:
                        citations.append({
                            "doi": doi,
                            "title": None,
                            "line": offset,
                            "section": "references",
                            "raw": stripped,
                        })
                else:
                    citations.append({
                        "doi": None,
                        "title": stripped,
                        "line": offset,
                        "section": "references",
                        "raw": stripped,
                    })

        return citations

    def _query_crossref(self, citation: dict[str, Any]) -> CrossrefResult | None:
        """Query Crossref for a citation."""
        if self.offline:
            return None
        try:
            if citation.get("doi"):
                return self.crossref_client.verify_doi(citation["doi"])
            elif citation.get("title"):
                results = self.crossref_client.search_by_title(citation["title"])
                return results[0] if results else CrossrefResult(found=False)
        except Exception:
            return CrossrefResult(found=False)
        return CrossrefResult(found=False)

    def _query_s2(self, citation: dict[str, Any]) -> S2Result | None:
        """Query Semantic Scholar for a citation."""
        if self.offline:
            return None
        try:
            if citation.get("doi"):
                return self.s2_client.verify_doi(citation["doi"])
            elif citation.get("title"):
                results = self.s2_client.search_by_title(citation["title"])
                return results[0] if results else S2Result(found=False)
        except Exception:
            return S2Result(found=False)
        return S2Result(found=False)

    def _classify_citation(
        self,
        crossref: CrossrefResult | None,
        s2: S2Result | None,
    ) -> tuple[str, str | None]:
        """Classify citation based on dual-source voting.

        Returns (verdict, severity).
        """
        cr_found = crossref.found if crossref else False
        s2_found = s2.found if s2 else False

        if cr_found and s2_found:
            cr_score = crossref.score if crossref else 0
            s2_score = s2.score if s2 else 0

            if cr_score < TITLE_SIMILARITY_THRESHOLD or s2_score < TITLE_SIMILARITY_THRESHOLD:
                return "title_mismatch", "P1"
            return "verified", None

        if cr_found or s2_found:
            return "partial", "P2"

        return "not_found", "P0"

    def _make_finding(
        self,
        rule_id: str,
        severity: str,
        message: str,
        line: int = 0,
        section: str = "references",
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a finding dict in paper-writer format."""
        return {
            "command": "audit_citations",
            "rule_id": rule_id,
            "finding_id": "",
            "severity": severity,
            "file": "",
            "line": line,
            "column": 0,
            "span": [line, line],
            "message": message,
            "section": section,
            "evidence": evidence or {},
            "recommendation": "Verify DOI is correct. If fabricated, remove citation.",
        }
