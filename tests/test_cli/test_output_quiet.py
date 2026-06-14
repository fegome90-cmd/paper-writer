"""Tests for --quiet semantics + output.configure reset (P2.8.2 + P2.8.20).

P2.8.2: --quiet suppresses emit_info/emit_warning (stderr) but NEVER
emit_result/emit_json/emit_error.
P2.8.20: output.configure() resets _config cleanly across repeated invocations
(idempotent — important for tests calling main() multiple times).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from cli.paper import output


@pytest.fixture(autouse=True)
def _reset_output_config() -> Iterator[None]:
    """Ensure each test starts from default config (no leak between tests)."""
    output.configure(quiet=False, output_format="text")
    yield
    output.configure(quiet=False, output_format="text")


class TestQuietSemantics:
    """P2.8.2: --quiet suppresses info/warnings, preserves results/json/errors."""

    def test_quiet_suppresses_emit_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        """emit_info is suppressed when quiet=True (per spec S11)."""
        output.configure(quiet=True, output_format="text")
        output.emit_info("progress info")
        captured = capsys.readouterr()
        assert captured.err == "", "emit_info MUST be suppressed by --quiet"
        assert captured.out == ""

    def test_quiet_suppresses_emit_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        """emit_warning is suppressed when quiet=True (per spec S11)."""
        output.configure(quiet=True, output_format="text")
        output.emit_warning("a warning")
        captured = capsys.readouterr()
        assert captured.err == "", "emit_warning MUST be suppressed by --quiet"

    def test_quiet_preserves_emit_result(self, capsys: pytest.CaptureFixture[str]) -> None:
        """emit_result is NEVER suppressed by --quiet (per spec S11)."""
        output.configure(quiet=True, output_format="text")
        output.emit_result("the result")
        captured = capsys.readouterr()
        assert "the result" in captured.out, "emit_result MUST survive --quiet"

    def test_quiet_preserves_emit_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """emit_json is NEVER suppressed by --quiet (per spec S11)."""
        output.configure(quiet=True, output_format="text")
        output.emit_json({"key": "value"})
        captured = capsys.readouterr()
        assert "key" in captured.out, "emit_json MUST survive --quiet"

    def test_quiet_preserves_emit_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        """emit_error is NEVER suppressed by --quiet (per spec S11)."""
        output.configure(quiet=True, output_format="text")
        output.emit_error("fatal")
        captured = capsys.readouterr()
        assert "Error: fatal" in captured.err, "emit_error MUST survive --quiet"

    def test_no_quiet_shows_emit_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Without --quiet, emit_info is shown on stderr (default behavior)."""
        output.configure(quiet=False, output_format="text")
        output.emit_info("progress")
        captured = capsys.readouterr()
        assert "progress" in captured.err


class TestConfigureResetsAcrossInvocations:
    """P2.8.20: output.configure() resets _config cleanly (no leak between calls)."""

    def test_configure_resets_quiet_from_true_to_false(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Setting quiet=True then quiet=False must fully restore emit_info visibility."""
        output.configure(quiet=True, output_format="text")
        output.emit_info("hidden")
        capsys.readouterr()  # discard

        output.configure(quiet=False, output_format="text")
        output.emit_info("visible")
        captured = capsys.readouterr()
        assert "visible" in captured.err
        assert "hidden" not in captured.err, "configure must reset — no leak of prior quiet=True"

    def test_configure_resets_output_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Setting output_format=json then text must switch summary() rendering."""
        from harness.services.orchestrator import OrchestratorResult

        result = OrchestratorResult(
            command="init",
            success=True,
            stage_before="init",
            stage_after="initialized",
            steps=[],
            blockers=[],
            warnings=[],
            artifacts=[],
            exit_code=0,
        )
        output.configure(quiet=False, output_format="json")
        output.summary(result)
        out_json = capsys.readouterr().out

        output.configure(quiet=False, output_format="text")
        output.summary(result)
        out_text = capsys.readouterr().out

        assert out_json != out_text, "configure must switch summary rendering between formats"
        assert "Success" in out_text
