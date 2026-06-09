import pytest

from harness.services.gates import (
    validate_bib_normalized,
    validate_citation_verify_gate,
    validate_ethics_passed_gate,
    validate_outline_drafted,
    validate_ready_for_delivery,
    validate_render_passed,
    validate_repo_initialized,
    validate_screened_evidence,
    validate_search_completed,
    validate_sections_completed,
    validate_validator_gate,
)
from tests.harness.mocks import InMemoryArtifactChecker


@pytest.fixture
def checker() -> InMemoryArtifactChecker:
    return InMemoryArtifactChecker()


def test_validate_repo_initialized_success(checker: InMemoryArtifactChecker) -> None:
    checker.existing_paths.update(["templates", "outputs", "outputs/state.yaml"])
    result = validate_repo_initialized(checker)
    assert result.status == "pass"
    assert not result.blockers
    assert not result.warnings


def test_validate_repo_initialized_fail(checker: InMemoryArtifactChecker) -> None:
    checker.existing_paths.update(["outputs"])
    result = validate_repo_initialized(checker)
    assert result.status == "fail"
    assert any("dir_exists_templates" in b for b in result.blockers)


def test_validate_search_completed_success(checker: InMemoryArtifactChecker) -> None:
    checker.existing_paths.update(
        [
            "outputs/latest/search",
            "outputs/latest/search/search_plan.json",
            "outputs/latest/search/raw_results.json",
        ]
    )
    result = validate_search_completed(checker)
    assert result.status == "pass"


def test_validate_search_completed_fail(checker: InMemoryArtifactChecker) -> None:
    result = validate_search_completed(checker)
    assert result.status == "fail"
    assert len(result.blockers) == 2


def test_validate_screened_evidence(checker: InMemoryArtifactChecker) -> None:
    result1 = validate_screened_evidence(checker)
    assert result1.status == "fail"

    checker.existing_paths.update(
        ["outputs/latest/search", "outputs/latest/search/screened_evidence.json"]
    )
    result2 = validate_screened_evidence(checker)
    assert result2.status == "pass"


def test_validate_outline_drafted(checker: InMemoryArtifactChecker) -> None:
    result1 = validate_outline_drafted(checker)
    assert result1.status == "fail"

    checker.existing_paths.update(["outputs/latest/drafts", "outputs/latest/drafts/outline.md"])
    result2 = validate_outline_drafted(checker)
    assert result2.status == "pass"


def test_validate_sections_completed(checker: InMemoryArtifactChecker) -> None:
    result1 = validate_sections_completed(checker)
    assert result1.status == "fail"
    assert len(result1.blockers) == 4

    checker.existing_paths.update(["outputs/latest/drafts"])
    for sec in ["introduction.md", "methods.md", "results.md", "discussion.md"]:
        checker.existing_paths.add(f"outputs/latest/drafts/{sec}")

    result2 = validate_sections_completed(checker)
    assert result2.status == "pass"


def test_validate_bib_normalized(checker: InMemoryArtifactChecker) -> None:
    result1 = validate_bib_normalized(checker)
    assert result1.status == "fail"

    checker.existing_paths.update(["templates", "templates/references.bib"])
    result2 = validate_bib_normalized(checker)
    assert result2.status == "pass"


def test_validate_validator_gate() -> None:
    # Test missing result
    result = validate_validator_gate("style_passed", None)
    assert result.status == "fail"
    assert "No validation results found" in result.blockers[0]

    # Test pass result
    pass_res = {
        "status": "pass",
        "findings": [],
        "artifacts_checked": ["outputs/drafts/introduction.md"],
    }
    result_pass = validate_validator_gate("style_passed", pass_res)
    assert result_pass.status == "pass"

    # Test warn result
    warn_res = {
        "status": "pass",
        "findings": [
            {"code": "passive_voice", "severity": "warning", "message": "Use active voice."}
        ],
        "artifacts_checked": ["outputs/drafts/introduction.md"],
    }
    result_warn = validate_validator_gate("style_passed", warn_res)
    assert result_warn.status == "warn"
    assert "passive_voice" in result_warn.warnings[0]

    # Test fail result
    fail_res = {
        "status": "pass",
        "findings": [
            {"code": "unresolved_ref", "severity": "error", "message": "Ref smith2024 not found."}
        ],
    }
    result_fail = validate_validator_gate("style_passed", fail_res)
    assert result_fail.status == "fail"
    assert "unresolved_ref" in result_fail.blockers[0]


def test_validate_render_passed(checker: InMemoryArtifactChecker) -> None:
    result1 = validate_render_passed(checker)
    assert result1.status == "fail"

    checker.existing_paths.update(
        ["outputs/latest/render", "outputs/latest/render/manuscript.docx"]
    )
    result2 = validate_render_passed(checker)
    assert result2.status == "pass"


def test_validate_ready_for_delivery(checker: InMemoryArtifactChecker) -> None:
    gates_state = {
        "repo_initialized": True,
        "search_completed": True,
        "screened_evidence": True,
        "outline_drafted": True,
        "sections_completed": True,
        "bib_normalized": True,
        "citations_resolved": True,
        "refs_validated": True,
        "style_passed": True,
        "reporting_passed": True,
        "render_passed": True,
        "ready_for_delivery": False,
        "citation_verified": True,
        "ethics_passed": True,
    }

    result1 = validate_ready_for_delivery(checker, gates_state)
    assert result1.status == "pass"

    # Break one gate
    gates_state["style_passed"] = False
    result2 = validate_ready_for_delivery(checker, gates_state)
    assert result2.status == "fail"
    assert any("style_passed" in b for b in result2.blockers)


class TestValidateValidatorGateMalformed:
    """validate_validator_gate must handle malformed validator output."""

    def test_none_result_fails(self) -> None:
        result = validate_validator_gate("test", None)
        assert result.status == "fail"

    def test_empty_dict_fails(self) -> None:
        result = validate_validator_gate("test", {})
        assert result.status == "fail"

    def test_findings_not_list_no_crash(self) -> None:
        result = validate_validator_gate("test", {"status": "pass", "findings": "not a list"})
        assert result.status == "pass"  # no valid findings → no blockers

    def test_findings_none_no_crash(self) -> None:
        result = validate_validator_gate("test", {"status": "pass", "findings": None})
        assert result.status == "pass"

    def test_finding_not_dict_skipped(self) -> None:
        result = validate_validator_gate(
            "test",
            {
                "status": "pass",
                "findings": [
                    "string",
                    42,
                    None,
                    {"severity": "error", "code": "E1", "message": "real"},
                ],
            },
        )
        assert result.status == "fail"
        assert len(result.blockers) == 1  # only the dict finding counted


class TestCitationVerifyGate:
    """Soft gate: citation_verified warns when not satisfied."""

    def test_passes_when_gate_true(self) -> None:
        checker = InMemoryArtifactChecker()
        result = validate_citation_verify_gate(checker, {"citation_verified": True})
        assert result.gate == "citation_verified"
        assert result.status == "pass"

    def test_warns_when_gate_false(self) -> None:
        checker = InMemoryArtifactChecker()
        result = validate_citation_verify_gate(checker, {"citation_verified": False})
        assert result.gate == "citation_verified"
        assert result.status == "warn"
        assert len(result.warnings) > 0

    def test_warns_when_gate_missing(self) -> None:
        checker = InMemoryArtifactChecker()
        result = validate_citation_verify_gate(checker, {})
        assert result.status == "warn"


class TestEthicsPassedGate:
    """Soft gate: ethics_passed warns when not satisfied."""

    def test_passes_when_gate_true(self) -> None:
        checker = InMemoryArtifactChecker()
        result = validate_ethics_passed_gate(checker, {"ethics_passed": True})
        assert result.gate == "ethics_passed"
        assert result.status == "pass"

    def test_warns_when_gate_false(self) -> None:
        checker = InMemoryArtifactChecker()
        result = validate_ethics_passed_gate(checker, {"ethics_passed": False})
        assert result.gate == "ethics_passed"
        assert result.status == "warn"
        assert len(result.warnings) > 0

    def test_warns_when_gate_missing(self) -> None:
        checker = InMemoryArtifactChecker()
        result = validate_ethics_passed_gate(checker, {})
        assert result.status == "warn"
