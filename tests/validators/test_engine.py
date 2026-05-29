"""Tests for engine/ modules (loader, deduplicator, formatter)."""

import json
from pathlib import Path

import yaml

from engine.deduplicator import deduplicate_findings
from engine.formatter import format_claims_output, format_gate_result, format_json, format_terminal
from engine.loader import load_checklist, load_checklists, load_rules


def _write_yaml(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f)


# ---------------------------------------------------------------------------
# loader tests
# ---------------------------------------------------------------------------


class TestLoadRules:
    def test_load_single_rule_file(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "test.yml",
            {
                "rule_group": "prose.test",
                "severity_default": "P1",
                "rules": [
                    {
                        "id": "prose.test.simple",
                        "patterns": ["\\btest\\b"],
                        "message": "Test rule",
                        "severity": "P1",
                        "scope": "sentence",
                    }
                ],
            },
        )
        rules = load_rules(tmp_path)
        assert len(rules) == 1
        assert rules[0]["id"] == "prose.test.simple"
        assert rules[0]["rule_group"] == "prose.test"

    def test_empty_dir_returns_empty_list(self) -> None:
        rules = load_rules("/tmp/nonexistent_dir_12345")
        assert rules == []

    def test_missing_rules_key_skipped(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "empty.yml", {"rule_group": "empty"})
        rules = load_rules(tmp_path)
        assert rules == []

    def test_defaults_applied(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "defaults.yml",
            {
                "rule_group": "defaults",
                "rules": [
                    {
                        "id": "test.no_severity",
                        "patterns": ["\\bfoo\\b"],
                        "message": "No severity given",
                    },
                ],
            },
        )
        rules = load_rules(tmp_path)
        assert len(rules) == 1
        assert rules[0]["severity"] == "P2"  # default
        assert rules[0]["scope"] == "sentence"  # default
        assert rules[0]["recommendation"] == ""  # default


class TestLoadChecklist:
    def test_load_valid_checklist(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "checklist.yml",
            {
                "guideline": "Test",
                "version": "1.0",
                "critical_items": [{"id": "item1", "check_type": "section_presence"}],
            },
        )
        result = load_checklist(tmp_path / "checklist.yml")
        assert result is not None
        assert result["guideline"] == "Test"
        assert "file" in result

    def test_load_nonexistent(self) -> None:
        result = load_checklist("/tmp/nonexistent_12345.yml")
        assert result is None

    def test_load_invalid_no_guideline(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "bad.yml", {"some_key": "some_value"})
        result = load_checklist(tmp_path / "bad.yml")
        assert result is None


class TestLoadChecklists:
    def test_load_all_checklists(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "generic.yml",
            {"guideline": "Generic", "study_types": ["*"], "critical_items": []},
        )
        _write_yaml(
            tmp_path / "consort.yml",
            {"guideline": "CONSORT", "study_types": ["rct"], "critical_items": []},
        )
        checklists = load_checklists(tmp_path)
        assert "*" in checklists
        assert "rct" in checklists

    def test_empty_dir(self) -> None:
        assert load_checklists("/tmp/nonexistent_dir_67890") == {}


# ---------------------------------------------------------------------------
# deduplicator tests
# ---------------------------------------------------------------------------


class TestDeduplicateFindings:
    def test_empty_list(self) -> None:
        assert deduplicate_findings([]) == []

    def test_no_overlap(self) -> None:
        findings = [
            {"finding_id": "", "span": [0, 5]},
            {"finding_id": "", "span": [10, 15]},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2

    def test_overlap_longest_wins(self) -> None:
        findings = [
            {"finding_id": "", "span": [0, 10], "rule_id": "short"},
            {"finding_id": "", "span": [0, 20], "rule_id": "long"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0]["rule_id"] == "long"

    def test_adjacent_no_overlap(self) -> None:
        findings = [
            {"finding_id": "", "span": [0, 10]},
            {"finding_id": "", "span": [10, 20]},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2

    def test_finding_ids_assigned(self) -> None:
        findings = [
            {"finding_id": "", "span": [0, 5]},
            {"finding_id": "", "span": [10, 15]},
        ]
        result = deduplicate_findings(findings)
        assert result[0]["finding_id"] == "F-001"
        assert result[1]["finding_id"] == "F-002"

    # === Regression: C5 — sweep-line dedup ===
    def test_partial_overlap_extends_coverage(self) -> None:
        """[0,50] and [30,80]: second extends beyond first → KEEP both."""
        findings = [
            {"finding_id": "", "span": [0, 50], "rule_id": "first"},
            {"finding_id": "", "span": [30, 80], "rule_id": "second"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2, f"Expected 2 findings, got {len(result)}"
        assert result[0]["rule_id"] == "first"
        assert result[1]["rule_id"] == "second"

    def test_completely_subsumed_dropped(self) -> None:
        """[0,50] and [10,20]: second is within first → DROP."""
        findings = [
            {"finding_id": "", "span": [0, 50], "rule_id": "outer"},
            {"finding_id": "", "span": [10, 20], "rule_id": "inner"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0]["rule_id"] == "outer"

    def test_multiple_extending_overlaps(self) -> None:
        """[0,10], [5,15], [10,20]: each extends the coverage."""
        findings = [
            {"finding_id": "", "span": [0, 10], "rule_id": "a"},
            {"finding_id": "", "span": [5, 15], "rule_id": "b"},
            {"finding_id": "", "span": [10, 20], "rule_id": "c"},
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# formatter tests
# ---------------------------------------------------------------------------


class TestFormatters:
    def test_format_json(self) -> None:
        data = {"key": "value"}
        output = format_json(data)
        parsed = json.loads(output)
        assert parsed["key"] == "value"

    def test_format_terminal_empty(self) -> None:
        output = format_terminal([])
        assert "No findings" in output

    def test_format_terminal_with_findings(self) -> None:
        findings = [
            {"severity": "P0", "rule_id": "test.a", "message": "Critical!", "line": 5, "column": 3},
            {"severity": "P1", "rule_id": "test.b", "message": "Warning", "line": 10, "column": 0},
        ]
        output = format_terminal(findings)
        assert "[!!]" in output
        assert "[!]" in output
        assert "test.a" in output

    def test_format_gate_result_terminal_blocked(self) -> None:
        result = {
            "gate_passed": False,
            "guideline": "CONSORT",
            "study_type": "rct",
            "summary": {
                "total_items": 5,
                "passed": 3,
                "blockers": 1,
                "warnings": 1,
                "not_applicable": 0,
            },
            "blockers": [
                {
                    "description": "Missing consent",
                    "expected_location": "Methods",
                    "message": "Not found",
                }
            ],
            "warnings": [
                {
                    "description": "Missing funding",
                    "message": "No funding disclosure",
                }
            ],
        }
        output = format_gate_result(result, "terminal")
        assert "BLOCKED" in output
        assert "CONSORT" in output
        assert "Missing consent" in output

    def test_format_gate_result_json(self) -> None:
        result = {"gate_passed": True, "summary": {}}
        output = format_gate_result(result, "json")
        parsed = json.loads(output)
        assert parsed["gate_passed"] is True

    def test_format_claims_output_json(self) -> None:
        result = {
            "candidates": [],
            "summary": {"total_candidates": 0, "by_type": {}, "by_risk": {}},
        }
        output = format_claims_output(result, "json")
        parsed = json.loads(output)
        assert "candidates" in parsed

    def test_format_claims_output_terminal(self) -> None:
        result = {
            "candidates": [
                {
                    "claim_type": "causal",
                    "text": "X causes Y",
                    "section": "Discussion",
                    "risk": "high",
                    "line": 5,
                    "triggers": ["causes"],
                },
            ],
            "summary": {"total_candidates": 1, "by_type": {"causal": 1}, "by_risk": {"high": 1}},
        }
        output = format_claims_output(result, "terminal")
        assert "causal" in output
        assert "X causes Y" in output
