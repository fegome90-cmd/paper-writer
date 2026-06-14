"""Final P2.8 tests: json cleanliness + pipeline summary + mypy literal (P2.8.3 + P2.8.9 + P2.8.12).

P2.8.3: --output-format json output NEVER contains progress text ([ok] Step, etc.).
P2.8.9: pipeline --output-format json uses output.summary() serializer (emits JSON).
P2.8.12: effective_output_format returns a mypy Literal-safe value (type narrowing).

These are the last genuine P2.8 gaps after the output_policy chain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cli.paper import output
from cli.paper.main import main
from cli.paper.output import OutputFormat, effective_output_format
from cli.paper.parser import build_parser

if TYPE_CHECKING:
    pass


def _run_cli_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
) -> tuple[int, str, str]:
    """Run CLI, return (exit_code, stdout, stderr)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", argv)
    import io
    from contextlib import redirect_stderr, redirect_stdout

    out_buf, err_buf = io.StringIO(), io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        try:
            main()
            code = 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out_buf.getvalue(), err_buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_output_config() -> object:
    """Ensure each test starts from default config (no leak between tests)."""

    output.configure(quiet=False, output_format="text")
    yield
    output.configure(quiet=False, output_format="text")


class TestJsonNeverContainsProgressText:
    """P2.8.3: --output-format json output is clean JSON, no progress text."""

    def test_pipeline_json_no_progress_text(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """paper --output-format json init emits clean JSON (steps are NOT in stdout)."""
        code, out, _err = _run_cli_stdout(
            tmp_path, monkeypatch, ["paper", "--output-format", "json", "init"]
        )
        assert code == 0
        assert out.strip(), "json mode MUST emit JSON to stdout"
        parsed = json.loads(out)  # raises if not clean JSON
        assert parsed["command"] == "init"
        # Progress text MUST be absent from the JSON stdout (it goes to emit_info/stderr)
        assert "[ok] Step" not in out
        assert "Success: Stage" not in out
        assert "Pipeline Blocked" not in out


class TestPipelineJsonUsesSummarySerializer:
    """P2.8.9: pipeline --output-format json routes through output.summary() serializer."""

    def test_pipeline_json_emits_serialized_result(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The JSON shape matches _serialize_result (command, success, steps, blockers...)."""
        code, out, _err = _run_cli_stdout(
            tmp_path, monkeypatch, ["paper", "--output-format", "json", "init"]
        )
        assert code == 0
        parsed = json.loads(out)
        # _serialize_result keys per output.py
        expected_keys = {"command", "success", "stage_before", "stage_after", "steps"}
        assert expected_keys.issubset(parsed.keys())


class TestEffectiveOutputFormatLiteralSafe:
    """P2.8.12: effective_output_format returns a Literal["text","json"] value (mypy-safe)."""

    @pytest.mark.parametrize(
        "root_fmt,sub_output,expected",
        [
            ("text", None, "text"),
            ("json", None, "json"),
            ("text", "json", "json"),
            ("json", "terminal", "text"),
        ],
        ids=["root-text", "root-json", "subcmd-json-wins", "subcmd-terminal-wins"],
    )
    def test_returns_literal_safe_value(
        self, root_fmt: str, sub_output: str | None, expected: str
    ) -> None:
        """Return type is OutputFormat Literal — assignable to str-typed slot."""
        parser = build_parser()
        argv = [f"--output-format={root_fmt}", "audit", "prose", "x.md"]
        if sub_output is not None:
            argv.extend(["--output", sub_output])
        args = parser.parse_args(argv)
        result: OutputFormat = effective_output_format(args)
        assert result == expected
        assert result in ("text", "json"), "must be one of the Literal values"
