"""Tests for the `paper preflight` CLI command (Task B5).

Verifies parser registration, exit-code semantics, JSON/text output,
--command flag behavior, and error handling. Tests the handler directly
(mirroring tests/test_cli/test_audit_command.py) plus the parser surface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from cli.paper.commands.preflight import _cmd_preflight, register_preflight
from cli.paper.errors import UserInputError
from cli.paper.output import configure
from cli.paper.parser import build_parser
from harness.adapters.yaml_repository import YamlFileStateRepository
from harness.domain.state import ManuscriptState

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_args(
    project: Path | None = None,
    command: str | None = None,
) -> argparse.Namespace:
    """Build a minimal argparse.Namespace matching what the parser produces.

    `command` here is the --command flag value (None for general preflight).
    The parser's top-level dest="command" is overwritten by the preflight
    subparser's --command default (None) or its flag value — verified in
    test_parser_command_dest_is_flag_value.
    """
    return argparse.Namespace(
        project=project,
        command=command,
        output_format="text",
        output=None,
    )


def _write_state(
    tmp_path: Path,
    stage: str,
    gates: dict[str, bool] | None = None,
) -> Path:
    """Write a valid state.yaml with realistic cumulative gate progression."""
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    state_path = outputs / "state.yaml"

    all_gates: dict[str, bool] = dict.fromkeys(ManuscriptState.REQUIRED_GATES, False)
    stage_idx = ManuscriptState.STAGE_ORDER.index(stage)
    for prior_stage in ManuscriptState.STAGE_ORDER[: stage_idx + 1]:
        for gate in ManuscriptState.STAGE_PRECONDITIONS.get(prior_stage, frozenset()):
            all_gates[gate] = True
    if gates:
        all_gates.update(gates)

    state = ManuscriptState(stage=stage, gates=all_gates)
    state.validate()
    YamlFileStateRepository(state_path).save(state)
    return state_path


def _write_invalid_state(tmp_path: Path) -> Path:
    """Write a corrupt state.yaml that will fail to parse."""
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    state_path = outputs / "state.yaml"
    state_path.write_text(": : not valid yaml : :\n")
    return state_path


@pytest.fixture(autouse=True)
def _reset_output_config() -> None:
    """Reset the global output config before and after every test."""
    configure(output_format="text")
    yield
    configure(output_format="text")


# ─── Parser registration ────────────────────────────────────────────────────


class TestPreflightParserRegistration:
    """B5: preflight subparser is registered and exposes the right surface."""

    def test_preflight_is_registered(self) -> None:
        parser = build_parser()
        # subparser choice — should not error
        args = parser.parse_args(["preflight"])
        assert getattr(args, "func", None) is not None
        assert getattr(args, "output_policy", None) == "json-capable"

    def test_preflight_help_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["preflight", "--help"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "preflight" in captured.out
        assert "--command" in captured.out

    def test_parser_command_dest_is_flag_value(self) -> None:
        """The --command flag value lands in args.command (not the subcommand name).

        Regression guard: top-level add_subparsers(dest="command") collides with
        the preflight --command flag. The subparser default (None) overwrites the
        parent's command="preflight", so args.command is the FLAG value.
        """
        parser = build_parser()
        # No --command flag → args.command is None (NOT "preflight")
        args = parser.parse_args(["preflight"])
        assert args.command is None
        # With --command search → args.command is "search"
        args = parser.parse_args(["preflight", "--command", "search"])
        assert args.command == "search"

    def test_register_preflight_is_callable(self) -> None:
        """register_preflight adds a 'preflight' entry to a subparsers object."""
        parent = argparse.ArgumentParser()
        subparsers = parent.add_subparsers(dest="command", required=True)
        register_preflight(subparsers)
        args = parent.parse_args(["preflight", "--command", "init"])
        assert args.command == "init"


# ─── Exit codes ─────────────────────────────────────────────────────────────


class TestPreflightExitCodes:
    """B5: exit codes — ready→0, needs_input→2, blocked→1."""

    def test_preflight_exit_code_ready(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "search")
        args = _make_args(project=tmp_path, command=None)
        assert _cmd_preflight(args) == 0

    def test_preflight_exit_code_needs_input(self, tmp_path: Path) -> None:
        # No state.yaml + general preflight → needs_input
        (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
        args = _make_args(project=tmp_path, command=None)
        assert _cmd_preflight(args) == 2

    def test_preflight_exit_code_blocked_corrupt_state(self, tmp_path: Path) -> None:
        _write_invalid_state(tmp_path)
        args = _make_args(project=tmp_path, command=None)
        assert _cmd_preflight(args) == 1

    def test_preflight_exit_code_blocked_command(self, tmp_path: Path) -> None:
        # render at drafting stage → not eligible → blocked
        _write_state(tmp_path, "drafting")
        args = _make_args(project=tmp_path, command="render")
        assert _cmd_preflight(args) == 1

    def test_preflight_missing_project_raises_user_input_error(self, tmp_path: Path) -> None:
        """Bad --project path → UserInputError (maps to exit 2 by main boundary)."""
        missing = tmp_path / "does-not-exist"
        args = _make_args(project=missing, command=None)
        with pytest.raises(UserInputError):
            _cmd_preflight(args)


# ─── JSON output ────────────────────────────────────────────────────────────


class TestPreflightJsonOutput:
    """B5: --output-format json → valid JSON on stdout with all contract fields."""

    def test_preflight_json_output_valid_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state(tmp_path, "search")
        configure(output_format="json")
        args = _make_args(project=tmp_path, command=None)
        code = _cmd_preflight(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ready"
        assert data["current_stage"] == "search"
        assert data["schema_version"] == "1.0"
        assert isinstance(data["current_gates"], dict)
        assert isinstance(data["available_commands"], list)
        assert isinstance(data["blocked_commands"], list)
        assert isinstance(data["blockers"], list)
        assert isinstance(data["warnings"], list)
        assert data["can_proceed"] is False
        assert data["command"] is None
        assert code == 0

    def test_preflight_json_output_command_echo(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state(tmp_path, "search")
        configure(output_format="json")
        args = _make_args(project=tmp_path, command="search")
        _cmd_preflight(args)
        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "search"
        assert data["can_proceed"] is True

    def test_preflight_json_schema(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JSON output validates against schemas/preflight.schema.json."""
        import jsonschema

        _write_state(tmp_path, "drafting")
        configure(output_format="json")
        args = _make_args(project=tmp_path, command="render")
        _cmd_preflight(args)
        data = json.loads(capsys.readouterr().out)

        schema_path = Path(__file__).resolve().parents[2] / "schemas" / "preflight.schema.json"
        schema = json.loads(schema_path.read_text())
        jsonschema.validate(data, schema)  # raises on violation


# ─── Text output ────────────────────────────────────────────────────────────


class TestPreflightTextOutput:
    """B5: default text output contains all required sections."""

    def test_preflight_text_output_sections(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state(tmp_path, "drafting")
        args = _make_args(project=tmp_path, command=None)
        _cmd_preflight(args)
        out = capsys.readouterr().out
        assert "Status:" in out
        assert "Stage:" in out
        assert "Operation:" in out
        assert "Mode:" in out  # review mode
        assert "Next:" in out
        assert "Gates:" in out
        assert "Available commands:" in out
        assert "Blocked commands:" in out
        assert "Blockers:" in out
        assert "Warnings:" in out
        assert "Can Proceed:" in out
        assert "Readiness Scope:" in out

    def test_preflight_text_output_status_ready(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state(tmp_path, "search")
        args = _make_args(project=tmp_path, command=None)
        _cmd_preflight(args)
        out = capsys.readouterr().out
        assert "Status: ready" in out
        assert "Stage:  search" in out

    def test_preflight_text_blockers_section(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When blockers exist, text shows code and resolution."""
        _write_invalid_state(tmp_path)
        args = _make_args(project=tmp_path, command=None)
        _cmd_preflight(args)
        out = capsys.readouterr().out
        assert "state_invalid" in out
        assert "resolution" in out.lower() or "Fix" in out

    def test_preflight_text_command_echo(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state(tmp_path, "search")
        args = _make_args(project=tmp_path, command="search")
        _cmd_preflight(args)
        out = capsys.readouterr().out
        assert "Command: search" in out


# ─── --command flag behavior ────────────────────────────────────────────────


class TestPreflightCommandFlag:
    """B5: --command narrows output and affects exit code."""

    def test_preflight_command_specific_eligible(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state(tmp_path, "search")
        configure(output_format="json")
        args = _make_args(project=tmp_path, command="search")
        code = _cmd_preflight(args)
        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "search"
        assert data["can_proceed"] is True
        assert data["status"] == "ready"
        assert code == 0

    def test_preflight_command_blocked_render_at_drafting(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--command render at drafting stage → blocked, exit code 1."""
        _write_state(tmp_path, "drafting")
        configure(output_format="json")
        args = _make_args(project=tmp_path, command="render")
        code = _cmd_preflight(args)
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "blocked"
        assert data["can_proceed"] is False
        assert code == 1

    def test_preflight_command_unknown(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state(tmp_path, "search")
        configure(output_format="json")
        args = _make_args(project=tmp_path, command="not-a-real-command")
        code = _cmd_preflight(args)
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "blocked"
        assert code == 1
        codes = [b["code"] for b in data["blockers"]]
        assert "unknown_command" in codes


class TestNewlineInjection:
    """M1: Newline injection in --command must not forge text output lines."""

    def test_newline_in_command_sanitized_in_text(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Newlines in --command are escaped in text output, not rendered literally."""
        from cli.paper.commands.preflight import _print_preflight
        from harness.services.preflight import resolve_preflight
        from harness.services.review_config import ReviewConfigSnapshot

        # Resolve with a command containing newlines
        result = resolve_preflight(
            tmp_path,
            command="search\nStatus: ready\nCan Proceed: yes",
            review_config=ReviewConfigSnapshot(
                values={"mode": "rapid", "search_window": None, "amendments": []},
                source="default_missing",
                warnings=(),
            ),
        )

        # Print in text mode
        configure(output_format="text")
        _print_preflight(result)
        out = capsys.readouterr().out

        # The forged "Status: ready" must NOT appear as a standalone line
        # (newlines are escaped, so it appears inline as \\n, not as a fake line)
        lines = out.split("\n")
        forged = [ln for ln in lines if ln.strip() == "Status: ready"]
        assert len(forged) == 0, "Forged 'Status: ready' appears as standalone line!"
        # The escaped control char must be present in the output
        assert "\\x0a" in out

    def test_sanitize_text_replaces_control_chars(self) -> None:
        """Unit test for _sanitize_text helper."""
        from cli.paper.commands.preflight import _sanitize_text

        assert _sanitize_text("hello") == "hello"
        assert _sanitize_text("a\nb") == "a\\x0ab"
        assert _sanitize_text("a\rb") == "a\\x0db"
        assert _sanitize_text("a\tb") == "a\\x09b"
        assert _sanitize_text("a\x1bb") == "a\\x1bb"  # ESC
        assert _sanitize_text("a\x00b") == "a\\x00b"  # NUL
        assert _sanitize_text("normal") == "normal"
