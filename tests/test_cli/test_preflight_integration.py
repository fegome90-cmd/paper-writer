"""End-to-end integration tests for `paper preflight` (Task B6).

Exercises the COMPLETE flow: CLI entry point → parser → handler →
resolve_preflight → output. Uses real filesystem (tmp_path) and the
actual ``main()`` entry point — no handler-level mocking.

State scenarios:
  - ``paper init`` is run live (lightweight, no external services).
  - Post-search / post-render states are created manually in state.yaml
    (running ``paper search`` / ``paper render`` would require external APIs
    and Pandoc, which belong to the ``e2e`` marker, not these tests).
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from cli.paper import output
from cli.paper.main import main
from harness.adapters.yaml_repository import YamlFileStateRepository
from harness.domain.state import ManuscriptState

pytestmark = pytest.mark.integration

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _run_cli(
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    cwd: Path,
) -> tuple[int, str, str]:
    """Invoke the CLI via ``main()``, return (exit_code, stdout, stderr).

    chdir to ``cwd`` so the ascending project-root search resolves locally,
    and captures stdout/stderr via redirect (main() calls sys.exit).
    """
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(sys, "argv", argv)
    out_buf, err_buf = io.StringIO(), io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        try:
            main()
            code = 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out_buf.getvalue(), err_buf.getvalue()


def _write_state(
    project: Path,
    stage: str,
    gates: dict[str, bool] | None = None,
) -> Path:
    """Write a valid state.yaml with cumulative gate progression.

    Mirrors the helper in test_preflight_cmd.py: sets every gate required to
    ENTER ``stage`` (via STAGE_PRECONDITIONS) to True, the rest to False.
    Optional ``gates`` overrides for test-specific scenarios.
    """
    outputs = project / "outputs"
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


def _write_review_config(project: Path, mode: str) -> Path:
    """Write a review_config.yaml with the given mode (rapid/academic)."""
    outputs = project / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    cfg_path = outputs / "review_config.yaml"
    cfg_path.write_text(f"mode: {mode}\n")
    return cfg_path


@pytest.fixture(autouse=True)
def _reset_output_config() -> None:
    """Reset global output config before/after every test (no leak between runs)."""
    output.configure(output_format="text")
    yield
    output.configure(output_format="text")


# ─── General preflight query ─────────────────────────────────────────────────


class TestPreflightGeneralQuery:
    """B6: `paper preflight` with no --command shows overall pipeline status."""

    def test_preflight_general_query(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No --command → status, available commands, next action all present."""
        _write_state(tmp_path, "search")
        code, out, _err = _run_cli(
            ["paper", "--project", str(tmp_path), "preflight"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0  # ready
        assert "Status:" in out
        assert "Available commands:" in out
        assert "Next:" in out

    def test_preflight_command_query(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`--command search` → command-specific status with echo."""
        _write_state(tmp_path, "search")
        code, out, _err = _run_cli(
            ["paper", "--project", str(tmp_path), "preflight", "--command", "search"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0
        assert "Command: search" in out


# ─── After pipeline stages ───────────────────────────────────────────────────


class TestPreflightAfterPipelineStages:
    """B6: preflight reflects stage progression after real init / manual state."""

    def test_preflight_after_init(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Run `paper init` then `paper preflight` → stage=search, next=search."""
        # Run init live (lightweight: scaffolds project, no external services).
        init_code, _out, _err = _run_cli(
            ["paper", "--project", str(tmp_path), "init"],
            monkeypatch,
            tmp_path,
        )
        assert init_code == 0

        # Preflight must reflect the post-init state.
        code, out, _err = _run_cli(
            ["paper", "--output-format", "json", "--project", str(tmp_path), "preflight"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0
        data = json.loads(out)
        assert data["status"] == "ready"
        assert data["current_stage"] == "search"
        assert data["next_action"] == "search"
        assert data["can_proceed"] is False  # no --command given

    def test_preflight_after_search(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Post-search state (stage=screen) → available_commands includes screen."""
        # Create post-search state manually (paper search needs external APIs).
        _write_state(tmp_path, "screen")
        code, out, _err = _run_cli(
            ["paper", "--output-format", "json", "--project", str(tmp_path), "preflight"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0
        data = json.loads(out)
        assert data["current_stage"] == "screen"
        assert "screen" in data["available_commands"]
        assert data["status"] == "ready"
        assert data["next_action"] == "screen"

    def test_preflight_after_render(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rendered stage with render_passed → next_action=verify."""
        _write_state(tmp_path, "rendered")
        code, out, _err = _run_cli(
            ["paper", "--output-format", "json", "--project", str(tmp_path), "preflight"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0
        data = json.loads(out)
        assert data["current_stage"] == "rendered"
        assert data["next_action"] == "verify"


# ─── Missing state scenarios ─────────────────────────────────────────────────


class TestPreflightMissingState:
    """B6: empty project dir behavior for pipeline_governed vs standalone."""

    def test_preflight_with_missing_state_pipeline_governed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty dir + pipeline_governed command (search) → needs_input."""
        code, out, _err = _run_cli(
            [
                "paper",
                "--output-format",
                "json",
                "--project",
                str(tmp_path),
                "preflight",
                "--command",
                "search",
            ],
            monkeypatch,
            tmp_path,
        )
        assert code == 2  # needs_input
        data = json.loads(out)
        assert data["status"] == "needs_input"
        assert data["can_proceed"] is False
        codes = [b["code"] for b in data["blockers"]]
        assert "state_missing" in codes

    def test_preflight_with_missing_state_standalone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty dir + standalone command (audit:prose) → ready + warning."""
        code, out, _err = _run_cli(
            [
                "paper",
                "--output-format",
                "json",
                "--project",
                str(tmp_path),
                "preflight",
                "--command",
                "audit:prose",
            ],
            monkeypatch,
            tmp_path,
        )
        assert code == 0  # ready
        data = json.loads(out)
        assert data["status"] == "ready"
        assert data["can_proceed"] is True
        assert any("state" in w.lower() for w in data["warnings"])


# ─── Output format validation ────────────────────────────────────────────────


class TestPreflightOutputFormats:
    """B6: JSON validates against schema; text contains all sections."""

    def test_preflight_json_output_matches_schema(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JSON output validates against schemas/preflight.schema.json."""
        import jsonschema

        _write_state(tmp_path, "screen")
        code, out, _err = _run_cli(
            ["paper", "--output-format", "json", "--project", str(tmp_path), "preflight"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0
        data = json.loads(out)
        schema_path = (
            Path(__file__).resolve().parents[2] / "schemas" / "preflight.schema.json"
        )
        schema = json.loads(schema_path.read_text())
        jsonschema.validate(data, schema)  # raises on violation

    def test_preflight_text_output_readability(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Text output contains every required section for human readability."""
        _write_state(tmp_path, "drafting")
        code, out, _err = _run_cli(
            ["paper", "--project", str(tmp_path), "preflight"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0
        required_sections = [
            "Status:",
            "Stage:",
            "Command:",
            "Operation:",
            "Mode:",
            "Next:",
            "Gates:",
            "Available commands:",
            "Blocked commands:",
            "Blockers:",
            "Warnings:",
            "Can Proceed:",
        ]
        for section in required_sections:
            assert section in out, f"missing text section: {section!r}"


# ─── Review mode ─────────────────────────────────────────────────────────────


class TestPreflightReviewMode:
    """B6: preflight reflects review_config.yaml mode."""

    def test_preflight_academic_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """review_config.yaml with mode: academic → preflight review_mode=academic."""
        _write_state(tmp_path, "search")
        _write_review_config(tmp_path, "academic")
        code, out, _err = _run_cli(
            ["paper", "--output-format", "json", "--project", str(tmp_path), "preflight"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0
        data = json.loads(out)
        assert data["review_mode"] == "academic"

    def test_preflight_default_rapid_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No review_config.yaml → review_mode defaults to rapid."""
        _write_state(tmp_path, "search")
        code, out, _err = _run_cli(
            ["paper", "--output-format", "json", "--project", str(tmp_path), "preflight"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0
        data = json.loads(out)
        assert data["review_mode"] == "rapid"


# ─── Standalone & regression ─────────────────────────────────────────────────


class TestPreflightStandaloneAndRegression:
    """B6: standalone commands not blocked; existing commands still work."""

    def test_standalone_command_not_blocked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """audit:prose is available even at bootstrap stage (no state.yaml).

        Standalone commands bypass pipeline-gate requirements, so they appear
        in available_commands even when the project is uninitialized.
        """
        code, out, _err = _run_cli(
            ["paper", "--output-format", "json", "--project", str(tmp_path), "preflight"],
            monkeypatch,
            tmp_path,
        )
        # General preflight on empty dir → needs_input, but standalone still available.
        assert code == 2
        data = json.loads(out)
        assert "audit:prose" in data["available_commands"]
        blocked_ids = [b["command"] for b in data["blocked_commands"]]
        assert "audit:prose" not in blocked_ids

    def test_existing_commands_still_work(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`paper init` still exits 0 — no regression from preflight additions."""
        code, _out, _err = _run_cli(
            ["paper", "--project", str(tmp_path), "init"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0


# ─── Slice A JSON completion (regression for OrchestratorResult fields) ───────


class TestSliceAJsonCompletion:
    """B6: orchestrated command JSON includes Slice A fields end-to-end."""

    def test_slice_a_json_completion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`paper --output-format json init` JSON includes gate_changes,
        state_changes, and failure_policy (Slice A contract).
        """
        code, out, _err = _run_cli(
            ["paper", "--output-format", "json", "--project", str(tmp_path), "init"],
            monkeypatch,
            tmp_path,
        )
        assert code == 0
        data = json.loads(out)
        # Slice A added these three keys to _serialize_result.
        assert "gate_changes" in data
        assert "state_changes" in data
        assert "failure_policy" in data
