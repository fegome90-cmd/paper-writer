import sys
from pathlib import Path
from typing import Any

import pytest

from cli.paper import main as cli_main
from harness.services.orchestrator import OrchestratorRequest, OrchestratorResult


def _capture_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    exit_code: int = 0,
) -> OrchestratorRequest:
    captured: dict[str, OrchestratorRequest] = {}

    class FakeOrchestrator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            # Constructor intentionally no-op for monkeypatched test double.
            pass

        def execute(self, request: OrchestratorRequest) -> OrchestratorResult:
            captured["request"] = request
            return OrchestratorResult(
                command=request.command,
                success=exit_code == 0,
                stage_before="bootstrap",
                stage_after="bootstrap",
                exit_code=exit_code,
            )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(cli_main, "Orchestrator", FakeOrchestrator)

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main()

    assert exc_info.value.code == exit_code
    return captured["request"]


@pytest.mark.parametrize(
    ("argv", "expected_command", "expected_policy", "expected_args"),
    [
        (
            ["paper", "init", "--preset", "nature"],
            "init",
            "stop_on_error",
            {"preset": "nature"},
        ),
        (
            ["paper", "draft", "outline"],
            "draft_outline",
            "stop_on_error",
            {},
        ),
        (
            ["paper", "draft", "section", "introduction"],
            "draft_section",
            "stop_on_error",
            {"name": "introduction"},
        ),
        (
            ["paper", "lint", "bib"],
            "lint_bib",
            "continue_on_error",
            {},
        ),
        (
            ["paper", "lint", "style"],
            "lint_style",
            "continue_on_error",
            {},
        ),
        (
            ["paper", "check", "refs"],
            "check_refs",
            "continue_on_error",
            {},
        ),
        (
            ["paper", "audit", "reporting"],
            "audit_reporting",
            "continue_on_error",
            {},
        ),
        (
            [
                "paper",
                "import",
                "bib",
                "zotero.bib",
                "--target",
                "templates/custom.bib",
            ],
            "import_bib",
            "stop_on_error",
            {"source_bib": "zotero.bib", "target_bib": "templates/custom.bib"},
        ),
        (
            ["paper", "render"],
            "render",
            "stop_on_error",
            {
                "output_formats": ["docx", "pdf"],
                "csl": None,
                "reference_doc": None,
            },
        ),
        (
            ["paper", "render", "--format", "docx", "--csl", "styles/csl/apa.csl"],
            "render",
            "stop_on_error",
            {
                "output_formats": ["docx"],
                "csl": "styles/csl/apa.csl",
                "reference_doc": None,
            },
        ),
        (
            ["paper", "verify"],
            "verify",
            "stop_on_error",
            {},
        ),
    ],
)
def test_cli_maps_commands_to_orchestrator_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    expected_command: str,
    expected_policy: str,
    expected_args: dict[str, Any],
) -> None:
    request = _capture_request(tmp_path, monkeypatch, argv)

    assert request.command == expected_command
    assert request.failure_policy == expected_policy
    assert request.args == expected_args
    assert request.requested_stage == "unknown"
    assert request.context["actor"] == "cli"
    assert request.context["cwd"] == str(tmp_path)


def test_cli_exits_with_orchestrator_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _capture_request(tmp_path, monkeypatch, ["paper", "verify"], exit_code=3)

    assert request.command == "verify"


@pytest.mark.parametrize(
    ("argv", "expected_render_args"),
    [
        (
            ["paper", "render", "--format", "docx", "--format", "pdf"],
            {
                "output_formats": ["docx", "pdf"],
                "csl": None,
                "reference_doc": None,
            },
        ),
        (
            ["paper", "render", "--format", "pdf", "--format", "docx"],
            {
                "output_formats": ["pdf", "docx"],
                "csl": None,
                "reference_doc": None,
            },
        ),
        (
            [
                "paper",
                "render",
                "--format",
                "docx",
                "--format",
                "docx",
                "--csl",
                "styles/csl/vancouver.csl",
                "--reference-doc",
                "styles/reference.docx",
            ],
            {
                "output_formats": ["docx", "docx"],
                "csl": "styles/csl/vancouver.csl",
                "reference_doc": "styles/reference.docx",
            },
        ),
    ],
)
def test_cli_render_flags_are_forwarded_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    expected_render_args: dict[str, Any],
) -> None:
    request = _capture_request(tmp_path, monkeypatch, argv)

    assert request.command == "render"
    assert request.failure_policy == "stop_on_error"
    assert request.args == expected_render_args
