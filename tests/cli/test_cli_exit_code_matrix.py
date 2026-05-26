import sys
from pathlib import Path

import pytest
import yaml

from cli.paper.main import main
from harness.adapters.filesystem_action_runner import FilesystemActionRunner
from harness.domain.state import ManuscriptState
from integrations.tools.pandoc import PandocRenderer


def _run_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> tuple[int, str]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc_info:
        main()
    captured = capsys.readouterr()
    code = exc_info.value.code
    normalized_code = code if isinstance(code, int) else 1
    return normalized_code, f"{captured.out}\n{captured.err}"


def _bootstrap_rendering_state(tmp_path: Path) -> None:
    """Set state to 'rendering' with all precondition gates satisfied."""
    state_path = tmp_path / "outputs" / "state.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state["stage"] = "rendering"
    gates = dict.fromkeys(ManuscriptState.REQUIRED_GATES, False)
    # Rendering requires these precondition gates to be True
    for g in [
        "repo_initialized",
        "search_completed",
        "screened_evidence",
        "outline_drafted",
        "sections_completed",
        "bib_normalized",
        "citations_resolved",
        "refs_validated",
        "style_passed",
        "reporting_passed",
    ]:
        gates[g] = True
    state["gates"] = gates
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")


def test_cli_exit_code_parser_error_epub_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, output = _run_cli(
        tmp_path,
        monkeypatch,
        capsys,
        ["paper", "render", "--format", "epub"],
    )

    assert code == 2
    assert "invalid choice" in output


def test_cli_exit_code_precondition_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_code, _ = _run_cli(tmp_path, monkeypatch, capsys, ["paper", "init"])
    assert init_code == 0

    code, output = _run_cli(
        tmp_path,
        monkeypatch,
        capsys,
        ["paper", "render", "--format", "docx"],
    )

    assert code == 1
    assert "requires stage 'rendering'" in output


def test_cli_exit_code_action_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original_run_action = FilesystemActionRunner.run_action

    def _failing_run_action(
        self: FilesystemActionRunner,
        command: str,
        args: dict[str, object],
    ) -> list[str]:
        if command == "init":
            raise OSError("simulated init action failure")
        return original_run_action(self, command, args)

    monkeypatch.setattr(FilesystemActionRunner, "run_action", _failing_run_action)

    code, output = _run_cli(tmp_path, monkeypatch, capsys, ["paper", "init"])

    assert code == 1
    assert "Action failed" in output


def test_cli_exit_code_wrapper_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_code, _ = _run_cli(tmp_path, monkeypatch, capsys, ["paper", "init"])
    assert init_code == 0

    _bootstrap_rendering_state(tmp_path)

    monkeypatch.setattr(PandocRenderer, "is_available", lambda self: False)

    code, output = _run_cli(
        tmp_path,
        monkeypatch,
        capsys,
        ["paper", "render", "--format", "docx"],
    )

    assert code == 1
    assert "Tool not available for gate 'render_passed'" in output
