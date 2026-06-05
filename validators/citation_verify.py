"""Citation verification orchestrator.

Orchestrates Crossref and Semantic Scholar clients to verify all citations
in a manuscript. Classifies each citation as verified/partial/not_found/title_mismatch.
Also detects preprint venue usage and flags informational warnings.
"""

from __future__ import annotations

import re
from typing import Any

from clients._text_similarity import TITLE_SIMILARITY_THRESHOLD
from clients.crossref import CrossrefClient, CrossrefResult
from clients.openalex import OpenAlexClient, OpenAlexResult
from clients.semantic_scholar import S2Result, SemanticScholarClient
from engine.deduplicator import deduplicate_findings
from parsers.manuscript import Manuscript

DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+")

PREPRINT_VENUES: frozenset[str] = frozenset(
    {
        "arxiv",
        "biorxiv",
        "medrxiv",
        "ssrn",
        "research square",
        "preprints.org",
        "chemrxiv",
        "eartharxiv",
        "osf preprints",
        "techrxiv",
        "psyarxiv",
        "socarxiv",
    }
)


class CitationVerifyValidator:
    """Orchestrate Crossref + Semantic Scholar to verify citations.

    When offline=True, returns P2 skipped findings without API calls.
    """

    def __init__(
        self,
        crossref_client: CrossrefClient | None = None,
        s2_client: SemanticScholarClient | None = None,
        openalex_client: OpenAlexClient | None = None,
        offline: bool = False,
    ) -> None:
        self.offline = offline
        self.crossref_client = crossref_client or CrossrefClient(offline=offline)
        self.s2_client = s2_client or SemanticScholarClient(offline=offline)
        self.openalex_client = openalex_client or OpenAlexClient(offline=offline)

    def validate(self, manuscript: Manuscript) -> list[dict[str, Any]]:
        """Verify all citations in the manuscript.

        Returns findings in paper-writer format. The last finding includes
        an aggregated citation verification verdict via reduce_citation_verdict.
        """
        self._manuscript_path = manuscript.path
        citations = self._extract_citations(manuscript)
        findings: list[dict[str, Any]] = []

        for citation in citations:
            finding = self.verify_single(citation)
            if finding:
                findings.append(finding)

        findings = deduplicate_findings(findings)

        # Append aggregated verdict summary
        verdict = reduce_citation_verdict(findings)
        findings.append(
            {
                "command": "audit_citations",
                "rule_id": "citation_verification_summary",
                "finding_id": "",
                "severity": "P2" if verdict != "fabricated" else "P0",
                "file": manuscript.path,
                "line": 0,
                "column": 0,
                "span": [0, 0],
                "message": f"Citation verification verdict: {verdict}",
                "section": "summary",
                "evidence": {"verdict": verdict, "total_findings": len(findings)},
                "recommendation": {
                    "verified": "All citations verified successfully.",
                    "unresolvable": (
                        "Some citations could not be fully verified. "
                        "Check citations without DOI for accuracy."
                    ),
                    "fabricated": (
                        "At least one DOI failed to resolve. "
                        "Verify DOIs carefully — this may indicate "
                        "fabricated references."
                    ),
                }.get(verdict, ""),
            }
        )

        return findings

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
        openalex = self._query_openalex(citation)

        verdict, _sev = self._classify_citation(crossref, s2, openalex)

        # Preprint venue detection using API-returned venue+year
        preprint_info = self._detect_preprint(crossref, s2, openalex)

        if verdict == "verified":
            # Even verified citations get flagged if from preprint venue
            if preprint_info:
                ref = citation.get("doi") or citation.get("title", "unknown")
                return self._make_finding(
                    rule_id="citation_verify.preprint_source",
                    severity="P2",
                    message=f"Citation is a preprint: {ref}",
                    line=citation.get("line", 0),
                    section=citation.get("section", "references"),
                    evidence={
                        "doi": citation.get("doi"),
                        "title": citation.get("title"),
                        **preprint_info,
                    },
                    recommendation=(
                        "Consider citing the peer-reviewed version if available. "
                        "Preprints have not undergone formal peer review."
                    ),
                )
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
                    "openalex_found": openalex.found if openalex else False,
                    **preprint_info,
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
                    **preprint_info,
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
                    "openalex_found": openalex.found if openalex else False,
                    **preprint_info,
                },
            )

        return None

    def _extract_citations(self, manuscript: Manuscript) -> list[dict[str, Any]]:
        """Extract DOIs and reference strings from the manuscript.

        Joins multi-line references before extraction. A new reference
        starts with a pattern like "1. ", "2. ", etc. Continuation lines
        are appended to the current reference.
        """
        ref_section = manuscript.sections.get("references")
        if not ref_section:
            return []

        text = ref_section.text
        ref_start_re = re.compile(r"^\s*\d+[\.\)]\s")
        merged_refs: list[tuple[str, int]] = []  # (merged_text, start_line)
        current_ref: list[str] = []
        current_start = 0
        line_num = ref_section.line_start

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                if current_ref:
                    merged_refs.append(("\n".join(current_ref), current_start))
                    current_ref = []
                line_num += 1
                continue

            if ref_start_re.match(stripped):
                # New reference — save previous if any
                if current_ref:
                    merged_refs.append(("\n".join(current_ref), current_start))
                current_ref = [stripped]
                current_start = line_num
            else:
                # Continuation line
                current_ref.append(stripped)

            line_num += 1

        # Don't forget the last reference
        if current_ref:
            merged_refs.append(("\n".join(current_ref), current_start))

        # Now extract DOIs and titles from merged references
        citations: list[dict[str, Any]] = []
        for ref_text, start_line in merged_refs:
            dois = DOI_PATTERN.findall(ref_text)
            if dois:
                for doi in dois:
                    citations.append(
                        {
                            "doi": doi,
                            "title": None,
                            "line": start_line,
                            "section": "references",
                            "raw": ref_text,
                        }
                    )
            else:
                citations.append(
                    {
                        "doi": None,
                        "title": ref_text,
                        "line": start_line,
                        "section": "references",
                        "raw": ref_text,
                    }
                )

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

    def _query_openalex(self, citation: dict[str, Any]) -> OpenAlexResult | None:
        """Query OpenAlex for a citation (third resolver)."""
        if self.offline:
            return None
        try:
            if citation.get("doi"):
                return self.openalex_client.verify_doi(citation["doi"])
            elif citation.get("title"):
                results = self.openalex_client.search_by_title(citation["title"])
                return results[0] if results else OpenAlexResult(found=False)
        except Exception:
            return OpenAlexResult(found=False)
        return OpenAlexResult(found=False)

    def _detect_preprint(
        self,
        crossref: CrossrefResult | None,
        s2: S2Result | None,
        openalex: OpenAlexResult | None = None,
    ) -> dict[str, Any]:
        """Detect if a citation is from a known preprint venue.

        Uses venue and year from Crossref/S2/OpenAlex API results.
        Returns empty dict if not a preprint, or preprint metadata.
        """
        venues: list[str] = []
        year: int | None = None

        for result in (crossref, s2, openalex):
            if result and result.found and result.venue:
                venues.append(result.venue.lower())
            if result and result.found and result.year is not None:
                year = result.year

        for venue in venues:
            for known in PREPRINT_VENUES:
                if known in venue:
                    return {
                        "preprint_venue": venue,
                        "preprint_year": year,
                        "preprint_flag": True,
                    }

        return {}

    def _classify_citation(
        self,
        crossref: CrossrefResult | None,
        s2: S2Result | None,
        openalex: OpenAlexResult | None = None,
    ) -> tuple[str, str | None]:
        """Classify citation based on multi-source voting.

        Returns (verdict, severity). Uses all available resolvers
        (Crossref, S2, OpenAlex) for triangulation.
        """
        cr_found = crossref.found if crossref else False
        s2_found = s2.found if s2 else False
        oa_found = openalex.found if openalex else False
        sources_found = sum([cr_found, s2_found, oa_found])

        if sources_found >= 2:
            cr_score = crossref.score if crossref else 0
            s2_score = s2.score if s2 else 0

            if cr_score < TITLE_SIMILARITY_THRESHOLD or s2_score < TITLE_SIMILARITY_THRESHOLD:
                return "title_mismatch", "P1"
            return "verified", None

        if sources_found == 1:
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
        recommendation: str = "Verify DOI is correct. If fabricated, remove citation.",
    ) -> dict[str, Any]:
        """Build a finding dict in paper-writer format."""
        return {
            "command": "audit_citations",
            "rule_id": rule_id,
            "finding_id": "",
            "severity": severity,
            "file": getattr(self, "_manuscript_path", ""),
            "line": line,
            "column": 0,
            "span": [line, line],
            "message": message,
            "section": section,
            "evidence": evidence or {},
            "recommendation": recommendation,
        }


def reduce_citation_verdict(findings: list[dict[str, Any]]) -> str:
    """Reduce per-citation findings to a 3-class aggregated verdict.

    Ported from ARS citation_verification_summary (v3.11, C-V6(a)).
    Produces a human- and machine-readable summary of citation verification
    status across the entire manuscript.

    Classes:
        "verified" — all citations resolved successfully (no findings).
        "unresolvable" — citations lack DOI/title for verification (coverage
            gap), or verification was skipped (offline mode). Not fabrication.
        "fabricated" — at least one citation with a DOI that provably fails
            to resolve. Strong fabrication evidence.

    Args:
        findings: List of finding dicts from CitationVerifyValidator.

    Returns:
        One of "verified", "unresolvable", or "fabricated".
    """
    if not findings:
        return "verified"

    # Separate by severity and type
    has_doi_failure = False
    has_title_failure = False
    has_title_mismatch = False
    has_unresolvable = False

    for f in findings:
        rule_id = f.get("rule_id", "")
        severity = f.get("severity", "")

        if "title_mismatch" in rule_id:
            has_title_mismatch = True
        elif "not_found" in rule_id:
            # Check if it had a DOI (ID-keyed) or only title
            evidence = f.get("evidence", {})
            if evidence.get("doi"):
                has_doi_failure = True
            else:
                has_title_failure = True
        elif "unresolvable" in rule_id or severity == "P3":
            has_unresolvable = True
        elif "partial" in rule_id:
            has_unresolvable = True

    # Decision logic (mirrors ARS C-V6(a)):
    # 1. DOI-keyed not_found = fabrication evidence
    if has_doi_failure:
        return "fabricated"

    # 2. Title-only failures = coverage gap (unresolvable)
    if has_title_failure or has_unresolvable:
        return "unresolvable"

    # 3. Title mismatch but not missing = needs review but not fabrication
    if has_title_mismatch:
        return "unresolvable"

    # 4. All other findings = verified (e.g., preprint warnings)
    return "verified"
