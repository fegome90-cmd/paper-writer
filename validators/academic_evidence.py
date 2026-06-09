"""Academic evidence validation helpers.

Provides scope-discipline, search-window integrity, and metadata-resolution
validation for academic-mode evidence curation. All functions return lists
of finding dicts with severity and message keys.
"""

from __future__ import annotations

from typing import Any


def validate_scope_discipline(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate scope classification discipline.

    Checks:
    - scope_classification must be present
    - protocol_only records cannot be treated as core observed evidence
    """
    findings: list[dict[str, Any]] = []

    scope = record.get("scope_classification")
    if not scope:
        findings.append(
            {
                "severity": "error",
                "message": "Missing scope_classification on academic record",
            }
        )
        return findings

    epistemic = record.get("epistemic_classification", "")

    # protocol_only + observed is contradictory
    if scope == "protocol_only" and epistemic == "observed":
        findings.append(
            {
                "severity": "warning",
                "message": (
                    "protocol_only record classified as 'observed' — "
                    "protocol papers cannot satisfy core observed evidence requirements"
                ),
            }
        )

    # horizon_scan narrated as core
    if scope in ("protocol_only", "horizon_scan"):
        findings.append(
            {
                "severity": "info",
                "message": (
                    f"Non-core scope ({scope}) — verify this is not narrated as core evidence"
                ),
            }
        )

    return findings


def validate_search_window_integrity(
    records: list[dict[str, Any]],
    search_window: dict[str, int] | None,
    amendments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate that all records fall within the declared search window.

    Out-of-window records require an explicit amendment.
    """
    if not search_window:
        return []

    findings: list[dict[str, Any]] = []
    start = search_window.get("start_year", 0)
    end = search_window.get("end_year", 9999)

    # Build set of amended record IDs
    amended_ids: set[str] = set()
    for amendment in amendments or []:
        for rec_id in amendment.get("records", []):
            amended_ids.add(rec_id)

    for rec in records:
        year = rec.get("year")
        doi = rec.get("doi", "")
        if year is None:
            continue
        if year < start or year > end:
            if doi not in amended_ids:
                findings.append(
                    {
                        "severity": "error",
                        "message": (
                            f"Record {doi} (year={year}) outside search window "
                            f"[{start}, {end}] without amendment"
                        ),
                    }
                )

    return findings


def validate_metadata_resolution(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate metadata resolution for critical claims.

    Records supporting critical claims must have resolved metadata.
    """
    findings: list[dict[str, Any]] = []

    for rec in records:
        if not rec.get("supports_critical_claim"):
            continue

        meta = rec.get("metadata_resolution", {})
        status = meta.get("status", "unresolved") if meta else "unresolved"
        if status != "resolved":
            doi = rec.get("doi", "unknown")
            findings.append(
                {
                    "severity": "error",
                    "message": (
                        f"Unresolved metadata for critical-claim record {doi} — "
                        f"academic completeness blocked"
                    ),
                }
            )

    return findings


def validate_academic_completeness(
    evidence_data: dict[str, Any],
    search_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run all academic validation checks on evidence data.

    Returns combined findings from scope, search-window, and metadata checks.
    """
    findings: list[dict[str, Any]] = []

    # Scope discipline on each evidence record
    for rec in evidence_data.get("evidence", []):
        findings.extend(validate_scope_discipline(rec))

    # Search window integrity
    if search_plan:
        window = search_plan.get("search_window")
        amendments = search_plan.get("amendments", [])
        evidence_records = evidence_data.get("evidence", [])
        findings.extend(validate_search_window_integrity(evidence_records, window, amendments))

    # Metadata resolution for critical claims
    findings.extend(validate_metadata_resolution(evidence_data.get("evidence", [])))

    # Check screening_records exist
    if "screening_records" not in evidence_data:
        findings.append(
            {
                "severity": "error",
                "message": "Academic mode requires screening_records in evidence output",
            }
        )

    return findings
