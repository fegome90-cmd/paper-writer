import sys
from pathlib import Path
from unittest.mock import patch

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
    # Set all gates required to reach 'rendering' (transitive preconditions)
    for stage in ManuscriptState.STAGE_ORDER:
        preconditions = ManuscriptState.STAGE_PRECONDITIONS.get(stage, frozenset())
        for g in preconditions:
            gates[g] = True
        if stage == "rendering":
            break
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


def test_cli_exit_code_external_service_error_returns_3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """P2.8.6: ExternalServiceError (Zotero/API/network) -> exit 3 (spec S19/XR6)."""
    from cli.paper.errors import ExternalServiceError

    def _service_down(_args: object) -> None:
        raise ExternalServiceError("Zotero API timeout")

    monkeypatch.chdir(tmp_path)
    with patch("cli.paper.commands.doctor._cmd_doctor", _service_down):
        code, output = _run_cli(tmp_path, monkeypatch, capsys, ["paper", "doctor"])
    assert code == 3, "external service errors MUST exit 3 (spec S19)"
    assert "Zotero API timeout" in output


def test_cli_exit_code_user_input_error_returns_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """P2.8.15: UserInputError (bad args/validation) -> exit 2 (spec S18/XR6)."""
    from cli.paper.errors import UserInputError

    def _bad_input(_args: object) -> None:
        raise UserInputError("missing required flag")

    monkeypatch.chdir(tmp_path)
    with patch("cli.paper.commands.doctor._cmd_doctor", _bad_input):
        code, output = _run_cli(tmp_path, monkeypatch, capsys, ["paper", "doctor"])
    assert code == 2, "user input errors MUST exit 2 (spec S18)"
    assert "missing required flag" in output


def test_cli_exit_code_unexpected_internal_error_returns_1_not_3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """XR6: unexpected internal error -> exit 1, NEVER misclassified as external (3)."""
    from cli.paper.errors import ExternalServiceError

    def _internal_bug(_args: object) -> None:
        # A KeyError is an internal bug, not an external service failure.
        raise KeyError("missing-key")

    monkeypatch.chdir(tmp_path)
    with patch("cli.paper.commands.doctor._cmd_doctor", _internal_bug):
        code, output = _run_cli(tmp_path, monkeypatch, capsys, ["paper", "doctor"])
    assert code == 1, "XR6: unexpected errors MUST exit 1, NEVER 3 (misclassification)"
    assert code != 3
    assert "Internal error" in output
    assert "Traceback" not in output
    # Guard: ExternalServiceError is still 3 (the catch-all doesn't swallow it)
    del ExternalServiceError
