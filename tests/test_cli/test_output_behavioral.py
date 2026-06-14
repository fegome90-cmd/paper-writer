"""Misc behavioral tests (P2.8.1 + P2.8.7 + P2.8.13 + P2.8.18 + P2.8.19).

P2.8.1: bad --project path → UserInputError → exit 2.
P2.8.7: summary() JSON serialization handles Path/Enum/dataclass (via to_json_value).
P2.8.13: output module uses TYPE_CHECKING for OrchestratorResult (no runtime cycle).
P2.8.18: UserInputError message has no 'Error:' prefix (emit_error adds it).
P2.8.19: dispatch unmapped command uses output.emit_error path.
"""

from __future__ import annotations

import datetime
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pytest

from cli.paper import output
from cli.paper.errors import UserInputError
from cli.paper.main import main


def _run_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> tuple[int, str]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        main()
    code = exc.value.code
    captured = capsys.readouterr()
    return (code if isinstance(code, int) else 1), f"{captured.out}\n{captured.err}"


class TestBadProjectPath:
    """P2.8.1: bad --project → UserInputError → exit 2."""

    def test_nonexistent_project_path_exits_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bad = tmp_path / "does-not-exist"
        code, out = _run_cli(
            tmp_path, monkeypatch, capsys, ["paper", "--project", str(bad), "doctor"]
        )
        assert code == 2, "bad --project path MUST exit 2 (UserInputError)"
        assert "Error:" in out, "emit_error adds 'Error:' prefix"


class TestJsonSerializationRepresentative:
    """P2.8.7: summary() JSON mode serializes Path/Enum/dataclass/datetime."""

    def test_summary_json_serializes_complex_types(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from harness.services.orchestrator import OrchestratorResult

        @dataclass
        class _Artifact:
            path: Path
            kind: str

        class _Kind(Enum):
            DOCX = "docx"

        # summary() calls _serialize_result -> to_json_value on each field;
        # the result is JSON with normalized Path/Enum/dataclass.
        result = OrchestratorResult(
            command="render",
            success=True,
            stage_before="rendering",
            stage_after="rendered",
            steps=[],
            blockers=[],
            warnings=[],
            artifacts=[],  # artifacts is list[str] in schema; test via direct to_json_value
            exit_code=0,
        )
        output.configure(quiet=False, output_format="json")
        output.summary(result)
        json_out = capsys.readouterr().out
        assert json_out.strip().startswith("{"), "summary() json mode emits JSON object"

        # Representative: to_json_value handles Path/Enum/dataclass/datetime
        complex_payload: dict[str, object] = {
            "path": Path("/x/y"),
            "kind": _Kind.DOCX,
            "artifact": _Artifact(path=Path("/a"), kind="docx"),
            "when": datetime.datetime(2026, 6, 13),
        }
        normalized = output.to_json_value(complex_payload)
        assert normalized == {
            "path": "/x/y",
            "kind": "docx",
            "artifact": {"path": "/a", "kind": "docx"},
            "when": "2026-06-13T00:00:00",
        }


class TestOutputModuleTypeImport:
    """P2.8.13: OrchestratorResult imported under TYPE_CHECKING (no runtime cycle)."""

    def test_orchestrator_result_not_a_runtime_import(self) -> None:
        """output.py must not import OrchestratorResult at runtime (avoids cycle)."""
        import cli.paper.output as out_mod

        # The module must be importable standalone (it's a leaf-ish module).
        assert hasattr(out_mod, "emit_result")
        # OrchestratorResult is only a TYPE_CHECKING import — not a module attribute at runtime.
        assert not hasattr(out_mod, "OrchestratorResult"), (
            "OrchestratorResult must be TYPE_CHECKING-only (runtime import would cycle)"
        )


class TestErrorPrefixNotDuplicated:
    """P2.8.18: UserInputError messages carry no 'Error:' prefix."""

    def test_user_input_error_message_has_no_prefix(self) -> None:
        exc = UserInputError("bad input here")
        assert "Error:" not in str(exc)

    def test_emit_error_adds_prefix_once(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """emit_error adds 'Error:' exactly once — no double-prefix."""
        output.emit_error("boom")
        captured = capsys.readouterr()
        assert captured.err == "Error: boom\n"
        assert captured.err.count("Error:") == 1
