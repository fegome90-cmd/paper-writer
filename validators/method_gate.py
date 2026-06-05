"""Methodological gate for paper gate method.

Phase 0: deterministic, heading-based IMRAD parsing, keyword checks.
Post-MVP: LLM-assisted item verification for ambiguous items.

Applies EQUATOR-derived checklists as fail-closed gates:
  - CONSORT 2025 for randomized controlled trials
  - STROBE for observational studies (cohort, case-control, cross-sectional)
  - PRISMA 2020 for systematic reviews
  - Generic checklist (applies to ALL study types)

Core principle:
  - P0 items missing → gate fails (fail-closed)
  - P1 items missing → warnings, gate can pass
  - P2 items missing → suggestions only
  - N/A items → recorded for audit trail, not penalized

Inspired by:
  - EQUATOR Network (checklist structure)
  - Penelope.ai (heading-based section mapping)
  - CONSORT-NLP (section → sentence → item mapping)
  - SciScore (detected/not_detected distinction)
"""

from __future__ import annotations

import time
from typing import Any

from validators.gate_verdict import GateVerdict, tier_from_findings


class MethodGateValidator:
    """Apply methodological gate based on EQUATOR-derived checklists.

    Steps:
    1. Load checklist YAML for the study type
    2. Parse manuscript into sections via heading detection
    3. For each item in checklist:
       a. Determine expected manuscript section
       b. Apply check_type (keyword_presence, section_presence, etc.)
       c. Record status: present, missing (with severity), or not_applicable
    4. Gate fails if any P0 item is missing
    """

    def __init__(self) -> None:
        self.checklists: dict[str, dict[str, Any]] = {}

    def validate(
        self,
        manuscript: Any,
        study_type: str,
        checklist_name: str | None = None,
        na_items: list[str] | None = None,
    ) -> dict[str, Any]:
        """Apply gate checklists against manuscript.

        Args:
            manuscript: Manuscript dataclass from parsers/manuscript.py
            study_type: e.g. 'rct', 'cohort', 'systematic_review', '*'
            checklist_name: Optional explicit checklist. Auto-selected if None.
            na_items: Optional list of item IDs marked not applicable

        Returns:
            GateResult dict conforming to schemas/method_gate.schema.json
        """
        # 1. Resolve checklist based on study_type
        t0 = time.perf_counter()
        checklist = self._resolve_checklist(study_type, checklist_name)
        if checklist is None:
            elapsed = int((time.perf_counter() - t0) * 1000)
            return {
                "command": "gate_method",
                "file": manuscript.path,
                "study_type": study_type,
                "guideline": "none",
                "gate_passed": True,
                "blockers": [],
                "warnings": [],
                "not_applicable": [],
                "passed_items": [],
                "summary": {
                    "total_items": 0,
                    "passed": 0,
                    "blockers": 0,
                    "warnings": 0,
                    "not_applicable": 0,
                },
                "metadata": {
                    "checklist_version": "1.0",
                    "rules_loaded": 0,
                    "execution_time_ms": elapsed,
                },
                "gate_verdict": GateVerdict(
                    tier="none",
                    message="No checklist resolved",
                ).to_dict(),
            }

        na_set = set(na_items or [])
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        not_applicable: list[dict[str, Any]] = []
        passed_items: list[dict[str, Any]] = []

        # 2. Run critical items
        for item in checklist.get("critical_items", []):
            item_id = item["id"]
            if item_id in na_set:
                not_applicable.append(
                    {
                        "item_id": item_id,
                        "description": item.get("description", ""),
                        "reason": "User-declared not applicable",
                        "status": "not_applicable",
                    }
                )
                continue

            result = self._check_item(item, manuscript)
            if result["status"] == "missing":
                severity = item.get("severity_if_missing", "P1")
                if severity == "P0":
                    blockers.append(result)
                else:
                    # P1/P2 items in critical_items → warnings
                    warnings.append(result)
            elif result["status"] == "not_applicable":
                not_applicable.append(result)
            else:
                passed_items.append(result)

        # 3. Run non-critical items
        for item in checklist.get("non_critical_items", []):
            item_id = item["id"]
            if item_id in na_set:
                not_applicable.append(
                    {
                        "item_id": item_id,
                        "description": item.get("description", ""),
                        "reason": "User-declared not applicable",
                        "status": "not_applicable",
                    }
                )
                continue

            result = self._check_item(item, manuscript)
            if result["status"] == "missing":
                severity = item.get("severity_if_missing", "P2")
                if severity == "P0":
                    blockers.append(result)
                elif severity in ("P1", "P2"):
                    warnings.append(result)
            elif result["status"] == "not_applicable":
                not_applicable.append(result)
            else:
                passed_items.append(result)

        # 4. Determine gate status
        gate_passed = len(blockers) == 0
        total = len(checklist.get("critical_items", [])) + len(
            checklist.get("non_critical_items", [])
        )

        # 5. Compute tiered gate verdict from all findings
        all_findings = blockers + warnings
        verdict = tier_from_findings(all_findings)

        return {
            "command": "gate_method",
            "file": manuscript.path,
            "study_type": study_type,
            "guideline": checklist.get("guideline", "unknown"),
            "guideline_source": (
                f"https://www.equator-network.org/reporting-guidelines/"
                f"{checklist.get('guideline', '').lower()}/"
            ),
            "gate_passed": gate_passed,
            "gate_verdict": verdict.to_dict(),
            "blockers": blockers,
            "warnings": warnings,
            "not_applicable": not_applicable,
            "passed_items": passed_items,
            "summary": {
                "total_items": total,
                "passed": len(passed_items),
                "blockers": len(blockers),
                "warnings": len(warnings),
                "not_applicable": len(not_applicable),
            },
            "metadata": {
                "checklist_version": checklist.get("version", "1.0"),
                "rules_loaded": total,
                "execution_time_ms": int((time.perf_counter() - t0) * 1000),
            },
        }

    def _resolve_checklist(
        self,
        study_type: str,
        checklist_name: str | None,
    ) -> dict[str, Any] | None:
        """Select checklist based on study type.

        Args:
            study_type: Declared study type (e.g. 'rct', 'cohort')
            checklist_name: Explicit checklist override

        Returns:
            Merged checklist dict (generic + specific) or None if no match.
        """

        from engine.loader import load_checklist
        from harness.ports.assets import get_rules_dir

        rules_dir = get_rules_dir("method_gate")
        generic_path = rules_dir / "generic.yml"

        # Base: always load generic
        base = load_checklist(generic_path)
        if base is None:
            base = {
                "guideline": "Generic",
                "version": "1.0",
                "critical_items": [],
                "non_critical_items": [],
            }

        # Specific checklist
        specific = None
        if checklist_name:
            specific = load_checklist(rules_dir / f"{checklist_name}.yml")
        else:
            for fpath in sorted(str(p) for p in rules_dir.glob("*.yml")):
                if fpath.endswith("generic.yml"):
                    continue
                cl = load_checklist(fpath)
                if cl and study_type in cl.get("study_types", []):
                    specific = cl
                    break

        if specific is None and checklist_name is None and study_type != "*":
            return {
                "guideline": "Generic",
                "version": base.get("version", "1.0"),
                "critical_items": list(base.get("critical_items", [])),
                "non_critical_items": list(base.get("non_critical_items", [])),
                "study_types": ["*"],
            }

        if specific is None:
            specific = base

        merged = dict(base)
        merged["guideline"] = specific.get("guideline", base.get("guideline", "Generic"))
        merged["version"] = specific.get("version", base.get("version", "1.0"))

        seen_critical = {i["id"] for i in base.get("critical_items", [])}
        seen_non_critical = {i["id"] for i in base.get("non_critical_items", [])}

        merged["critical_items"] = list(base.get("critical_items", []))
        for item in specific.get("critical_items", []):
            if item["id"] not in seen_critical:
                merged["critical_items"].append(item)
                seen_critical.add(item["id"])

        merged["non_critical_items"] = list(base.get("non_critical_items", []))
        for item in specific.get("non_critical_items", []):
            if item["id"] not in seen_non_critical:
                merged["non_critical_items"].append(item)
                seen_non_critical.add(item["id"])

        return merged

    def _check_item(
        self,
        item: dict[str, Any],
        manuscript: Any,
    ) -> dict[str, Any]:
        """Check a single checklist item against the manuscript.

        Args:
            item: Checklist item dict
            manuscript: Parsed manuscript

        Returns:
            Result dict with status, evidence, and message
        """
        check_type = item.get("check_type", "keyword_presence")
        # Normalize to lowercase to match manuscript.sections keys
        expected_location = item.get("expected_location", "").lower()

        # Get the Section dataclass (or None if missing)
        section = manuscript.sections.get(expected_location)
        section_text = section.text if section else ""

        if check_type == "section_presence":
            # Check if the section heading exists
            if expected_location in manuscript.sections:
                return {
                    "item_id": item["id"],
                    "description": item.get("description", ""),
                    "status": "present",
                    "evidence": f"Section '{expected_location}' found",
                }
            else:
                return {
                    "item_id": item["id"],
                    "description": item.get("description", ""),
                    "expected_location": expected_location,
                    "check_type": check_type,
                    "status": "missing",
                    "severity": item.get("severity_if_missing", "P1"),
                    "message": item.get("message", ""),
                }

        elif check_type == "keyword_presence":
            # Check for keywords in the expected section
            import re

            keywords = item.get("keywords", [])
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", section_text, re.IGNORECASE):
                    return {
                        "item_id": item["id"],
                        "description": item.get("description", ""),
                        "status": "present",
                        "evidence": f"Keyword '{kw}' found in {expected_location}",
                    }
            return {
                "item_id": item["id"],
                "description": item.get("description", ""),
                "expected_location": expected_location,
                "check_type": check_type,
                "status": "missing",
                "severity": item.get("severity_if_missing", "P1"),
                "message": item.get("message", ""),
                "keywords_checked": keywords,
            }

        elif check_type == "section_content":
            # Check if section has minimum content
            threshold = item.get("min_characters", 100)
            if len(section_text.strip()) >= threshold:
                return {
                    "item_id": item["id"],
                    "description": item.get("description", ""),
                    "status": "present",
                    "evidence": f"Section has {len(section_text.strip())} characters",
                }
            else:
                return {
                    "item_id": item["id"],
                    "description": item.get("description", ""),
                    "expected_location": expected_location,
                    "check_type": check_type,
                    "status": "missing",
                    "severity": item.get("severity_if_missing", "P1"),
                    "message": (
                        f"Section appears to have insufficient content "
                        f"({len(section_text.strip())} chars)."
                    ),
                }

        else:
            return {
                "item_id": item["id"],
                "description": item.get("description", ""),
                "status": "not_applicable",
                "message": f"Unsupported check_type: {check_type}",
            }
