"""Citation verification orchestrator.

Orchestrates Crossref and Semantic Scholar clients to verify all citations
in a manuscript. Classifies each citation as verified/partial/not_found/title_mismatch.
Also detects preprint venue usage and flags informational warnings.
"""

from __future__ import annotations

import re
from typing import Any

from clients._text_similarity import TITLE_SIMILARITY_THRESHOLD
from clients.arxiv import ArxivClient, ArxivResult
from clients.crossref import CrossrefClient, CrossrefResult
from clients.openalex import OpenAlexClient, OpenAlexResult
from clients.semantic_scholar import S2Result, SemanticScholarClient
from engine.deduplicator import deduplicate_findings
from parsers.manuscript import Manuscript
from validators.contamination_signals import compute_contamination_signal

DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+")

# arXiv ID patterns in reference text.
# Matches: arXiv:2301.00001, arXiv:2301.00001v2, 2301.00001,
#           https://arxiv.org/abs/2301.00001, http://arxiv.org/abs/2301.00001v2
# Bare numeric IDs (NNNN.NNNNN) are ONLY matched when NOT inside a DOI string,
# to avoid false positives on journal DOIs like 10.1038/nature.2023.12345.
# Use extract_arxiv_id_from_doi() for arXiv DOIs (10.48550/arXiv.*).
ARXIV_ID_PATTERN = re.compile(
    r"(?:arXiv[:\s]*|arxiv\.org/abs/|10\.48550/arXiv\.)"
    r"(\d{4}\.\d{4,5}(?:v\d+)?)",
    re.IGNORECASE,
)

# arXiv DOI prefix per DataCite (https://arxiv.org/help/bulk_data)
ARXIV_DOI_PREFIX = "10.48550/arXiv."


def extract_arxiv_id_from_doi(doi: str) -> str | None:
    """Extract arXiv ID from a DataCite arXiv DOI (10.48550/arXiv.NNNN.NNNNN).

    Returns the arXiv ID, or None if the DOI is not an arXiv DOI.
    This is the ONLY safe way to extract arXiv IDs from DOI strings —
    other DOI registrants (Nature, IEEE, etc.) can have NNNN.NNNNN patterns
    that are NOT arXiv IDs.
    """
    if not doi or not doi.startswith(ARXIV_DOI_PREFIX):
        return None
    # Strip the prefix and validate the remaining ID format
    arxiv_id = doi[len(ARXIV_DOI_PREFIX) :].rstrip("/")
    if re.match(r"^\d{4}\.\d{4,5}(?:v\d+)?$", arxiv_id, re.IGNORECASE):
        return arxiv_id
    return None


# Import PREPRINT_VENUES from contamination_signals to avoid circular import
# Re-exported for backward compatibility
from validators.contamination_signals import PREPRINT_VENUES as PREPRINT_VENUES  # noqa: E402


class CitationVerifyValidator:
    """Orchestrate Crossref + Semantic Scholar to verify citations.

    When offline=True, returns P2 skipped findings without API calls.
    """

    def __init__(
        self,
        crossref_client: CrossrefClient | None = None,
        s2_client: SemanticScholarClient | None = None,
        openalex_client: OpenAlexClient | None = None,
        arxiv_client: ArxivClient | None = None,
        offline: bool = False,
    ) -> None:
        self.offline = offline
        self.crossref_client = crossref_client or CrossrefClient(offline=offline)
        self.s2_client = s2_client or SemanticScholarClient(offline=offline)
        self.openalex_client = openalex_client or OpenAlexClient(offline=offline)
        self.arxiv_client = arxiv_client or ArxivClient(offline=offline)

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
        """Verify a single citation. Public API for single-citation verification.

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
        arxiv = self._query_arxiv(citation)

        verdict, _sev = self._classify_citation(crossref, s2, openalex, arxiv)

        # Extract venue + year from first available resolver result
        venue, year = self._extract_venue_year(crossref, s2, openalex, arxiv)
        contamination = compute_contamination_signal(venue, year)

        if verdict == "verified":
            # Even verified citations get flagged if contamination detected
            if contamination.is_preprint:
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
                        **contamination.to_dict(),
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
                    "arxiv_found": arxiv.found if arxiv else False,
                    **contamination.to_dict(),
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
                    "openalex_title": openalex.title if openalex else None,
                    "arxiv_title": arxiv.title if arxiv else None,
                    **contamination.to_dict(),
                },
            )

        if verdict == "partial":
            resolved_by = []
            if crossref and crossref.found:
                resolved_by.append("crossref")
            if s2 and s2.found:
                resolved_by.append("semantic_scholar")
            if openalex and openalex.found:
                resolved_by.append("openalex")
            if arxiv and arxiv.found:
                resolved_by.append("arxiv")
            return self._make_finding(
                rule_id="citation_verify.partial",
                severity="P2",
                message=f"Citation found in only one source: {ref}",
                line=citation.get("line", 0),
                section=citation.get("section", "references"),
                evidence={
                    "doi": citation.get("doi"),
                    "resolved_by": resolved_by,
                    "crossref_found": crossref.found if crossref else False,
                    "s2_found": s2.found if s2 else False,
                    "openalex_found": openalex.found if openalex else False,
                    "arxiv_found": arxiv.found if arxiv else False,
                    **contamination.to_dict(),
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
        # Match common reference number formats:
        #   1.  — numbered dot (APA, Chicago, Nature)
        #   1)  — numbered paren
        #   [1] — bracketed (IEEE, Vancouver, common in CS/medical)
        #   (1) — parenthesized (some journal styles)
        ref_start_re = re.compile(r"^\s*(?:\d+[\.\)]\s|\[\d+\]\s|\(\d+\)\s)")
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
                        "title": self._extract_title(ref_text),
                        "line": start_line,
                        "section": "references",
                        "raw": ref_text,
                    }
                )

        return citations

    @staticmethod
    def _extract_title(ref_text: str) -> str:
        """Extract a clean paper title from a raw reference string.

        Reference formats vary, but common patterns:
        - "1. Authors. Title. Venue Year."
        - "Authors, Title, Conference, Year."
        - "Authors (Year) Title."

        Heuristics (in priority order):
        1. Strip leading reference number (e.g. "1. ", "[1] ")
        2. Strip arXiv IDs and URLs
        3. Split on sentence boundaries after author-like content
        4. The title is typically the SECOND segment (after authors)
        5. Strip trailing venue/year noise
        """
        # Strip reference number prefix
        text = re.sub(r"^[\d\[\(]+[\.\]\)]*\s*", "", ref_text.strip())

        # Strip arXiv IDs and URLs before splitting
        text = ARXIV_ID_PATTERN.sub("", text)
        text = re.sub(r"https?://\S+", "", text)
        text = text.strip()
        if not text:
            return ref_text.strip()

        # Split into segments on ". " boundaries
        segments = re.split(r"\.\s+", text)

        # Filter empty segments (from stripped arXiv IDs)
        segments = [s.strip() for s in segments if s.strip()]

        if len(segments) < 2:
            # Single segment — return as-is (probably just a title)
            return CitationVerifyValidator._clean_title_segment(text)

        # First segment is usually authors (contains names, "et al.", commas)
        # Second segment is usually the title
        # Heuristics: authors contain patterns like "et al", "J.", "A.B."
        first = segments[0]

        # Check if first segment looks like authors
        looks_like_authors = bool(
            re.search(r"et\s+al|,\s*[A-Z]\.|[A-Z][a-z]+\s+[A-Z]\b|\d{4}", first)
        )

        if looks_like_authors and len(segments) >= 2:
            candidate = segments[1]
        else:
            # First segment might BE the title
            candidate = first

        return CitationVerifyValidator._clean_title_segment(candidate)

    @staticmethod
    def _clean_title_segment(text: str) -> str:
        """Remove trailing venue/year noise from a title candidate."""
        # Strip arXiv ID suffix FIRST (before year strip, which would eat
        # the trailing digits of an ID like "arXiv:2301.00001").
        # NOTE: "arXiv" is only stripped when followed by an arXiv ID
        # (e.g., "arXiv:2301.00001"), NOT when used as a standalone word
        # in a title (e.g., "Survey of arXiv submissions").
        text = re.sub(
            r"\s*arXiv:\s*\d{4}\.\d{4,5}(?:v\d+)?\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        # Remove trailing year: " 2023", " (2023)"
        text = re.sub(r"\s*\(\d{4}\)\s*$", "", text)
        text = re.sub(r"\s*\d{4}\s*$", "", text)
        # Remove trailing venue-like words: "Nature", "NeurIPS", "IEEE Trans"
        text = re.sub(
            r"\s*(?:Nature|Science|NeurIPS|ICML|ICLR|ACL|EMNLP|AAAI|CVPR|IEEE\s+\w+)\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        # Remove trailing semicolon+page noise: ";15(2):45-67"
        text = re.sub(r";.*$", "", text)
        return text.strip()

    def _resolve_title(self, citation: dict[str, Any]) -> str | None:
        """Get the best available title for title-based search.

        Priority: explicit title field > extracted title from raw text.
        Used by resolvers as fallback when DOI verification fails.
        """
        title = citation.get("title")
        if isinstance(title, str):
            return title
        raw = citation.get("raw", "") or ""
        if raw:
            extracted = self._extract_title(raw)
            if extracted and len(extracted) > 5:
                return extracted
        return None

    def _query_crossref(self, citation: dict[str, Any]) -> CrossrefResult | None:
        """Query Crossref for a citation."""
        if self.offline:
            return None
        try:
            if citation.get("doi"):
                result = self.crossref_client.verify_doi(citation["doi"])
                if result and result.found:
                    return result
            # Fallback to title search (from explicit field or extracted from raw)
            title = self._resolve_title(citation)
            if title:
                results = self.crossref_client.search_by_title(title)
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
                result = self.s2_client.verify_doi(citation["doi"])
                if result and result.found:
                    return result
            # Fallback to title search (from explicit field or extracted from raw)
            title = self._resolve_title(citation)
            if title:
                results = self.s2_client.search_by_title(title)
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
                result = self.openalex_client.verify_doi(citation["doi"])
                if result and result.found:
                    return result
            # Fallback to title search (from explicit field or extracted from raw)
            title = self._resolve_title(citation)
            if title:
                results = self.openalex_client.search_by_title(title)
                return results[0] if results else OpenAlexResult(found=False)
        except Exception:
            return OpenAlexResult(found=False)
        return OpenAlexResult(found=False)

    def _query_arxiv(self, citation: dict[str, Any]) -> ArxivResult | None:
        """Query arXiv for a citation (fourth resolver).

        arXiv is best for preprints and CS/Physics/Math papers.
        Strategy:
        1. Extract arXiv ID from raw text (arXiv:NNN, arxiv.org/abs/NNN)
        2. Extract arXiv ID from arXiv DOI (10.48550/arXiv.NNNN.NNNNN)
        3. Fall back to title search via _resolve_title
        """
        if self.offline:
            return None
        try:
            # Strategy 1: Extract arXiv ID from raw text
            raw_text = citation.get("raw", "") or ""
            arxiv_id = self._extract_arxiv_id(raw_text)
            if arxiv_id:
                return self.arxiv_client.verify_arxiv_id(arxiv_id)

            # Strategy 2: Extract arXiv ID from arXiv DOI (10.48550/arXiv.*)
            doi = citation.get("doi", "") or ""
            arxiv_id = extract_arxiv_id_from_doi(doi)
            if arxiv_id:
                return self.arxiv_client.verify_arxiv_id(arxiv_id)

            # Strategy 3: Title search (from explicit field or extracted from raw)
            title = self._resolve_title(citation)
            if title:
                results = self.arxiv_client.search_by_title(title)
                return results[0] if results else ArxivResult(found=False)
        except Exception:
            return ArxivResult(found=False)
        return ArxivResult(found=False)

    @staticmethod
    def _extract_arxiv_id(raw_text: str) -> str | None:
        """Extract arXiv ID from reference text.

        Matches patterns like:
        - arXiv:2301.00001, arXiv:2301.00001v2
        - https://arxiv.org/abs/2301.00001
        - 10.48550/arXiv.2301.00001 (arXiv DOI)

        Bare numeric IDs (NNNN.NNNNN) are NOT matched to avoid false positives
        on journal DOIs like 10.1038/nature.2023.12345.
        For DOI-based extraction, use extract_arxiv_id_from_doi() instead.
        """
        if not raw_text:
            return None
        match = ARXIV_ID_PATTERN.search(raw_text)
        if match:
            return match.group(1)
        return None

    def _extract_venue_year(
        self,
        crossref: CrossrefResult | None,
        s2: S2Result | None,
        openalex: OpenAlexResult | None = None,
        arxiv: ArxivResult | None = None,
    ) -> tuple[str | None, int | None]:
        """Extract venue and year from first available resolver result."""
        venue: str | None = None
        year: int | None = None

        for result in (crossref, s2, openalex, arxiv):
            if result and result.found:
                if not venue and getattr(result, "venue", None):
                    venue = result.venue  # type: ignore[union-attr]
                if year is None and getattr(result, "year", None) is not None:
                    year = result.year
                if venue and year is not None:
                    break

        return venue, year

    def _detect_preprint(
        self,
        crossref: CrossrefResult | None,
        s2: S2Result | None,
        openalex: OpenAlexResult | None = None,
        arxiv: ArxivResult | None = None,
    ) -> dict[str, Any]:
        """Detect if a citation is from a known preprint venue.

        Uses venue and year from Crossref/S2/OpenAlex/arXiv API results.
        Returns empty dict if not a preprint, or preprint metadata.
        """
        venues: list[str] = []
        year: int | None = None

        for result in (crossref, s2, openalex, arxiv):
            if result and result.found and getattr(result, "venue", None):
                venues.append(result.venue.lower())  # type: ignore[union-attr]
            if result and result.found and getattr(result, "year", None) is not None:
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
        arxiv: ArxivResult | None = None,
    ) -> tuple[str, str | None]:
        """Classify citation based on multi-source voting.

        Returns (verdict, severity). Uses all available resolvers
        (Crossref, S2, OpenAlex, arXiv) for triangulation.
        """
        cr_found = crossref.found if crossref else False
        s2_found = s2.found if s2 else False
        oa_found = openalex.found if openalex else False
        ar_found = arxiv.found if arxiv else False
        sources_found = sum([cr_found, s2_found, oa_found, ar_found])

        if sources_found >= 2:
            # Collect scores only from sources that found the citation
            found_scores = []
            if cr_found and crossref:
                found_scores.append(crossref.score)
            if s2_found and s2:
                found_scores.append(s2.score)
            if oa_found and openalex:
                found_scores.append(openalex.score)
            if ar_found and arxiv:
                found_scores.append(arxiv.score)

            max_score = max(found_scores) if found_scores else 0
            if max_score < TITLE_SIMILARITY_THRESHOLD:
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
