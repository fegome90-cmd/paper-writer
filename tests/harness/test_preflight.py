"""Tests for PreflightResult dataclasses, ReviewConfigSnapshot, and resolver (B2+B3).

Verifies construction, immutability, defaults, legacy loader parity,
and resolve_preflight behavioral contract.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from harness.adapters.yaml_repository import YamlFileStateRepository
from harness.domain.state import ManuscriptState
from harness.services.preflight import (
    BlockedCommand,
    PreflightBlocker,
    PreflightResult,
    resolve_preflight,
)
from harness.services.review_config import (
    ReviewConfigSnapshot,
    load_review_config,
    load_review_config_snapshot,
)

# ─── PreflightResult / PreflightBlocker / BlockedCommand ────────────────────


class TestPreflightResultConstruction:
    """B2: PreflightResult builds with all required fields."""

    def test_preflight_result_construction(self) -> None:
        result = PreflightResult(
            schema_version="1.0",
            status="ready",
            operation="create",
            review_mode="rapid",
            current_stage="drafting",
            current_gates={"repo_initialized": True},
            available_commands=["draft:section"],
            blocked_commands=[],
            next_action=None,
            blockers=[],
            warnings=[],
            can_proceed=True,
            command="draft:section",
        )
        assert result.schema_version == "1.0"
        assert result.status == "ready"
        assert result.operation == "create"
        assert result.review_mode == "rapid"
        assert result.current_stage == "drafting"
        assert result.can_proceed is True
        assert result.command == "draft:section"
        assert isinstance(result.current_gates, dict)
        assert isinstance(result.available_commands, list)
        assert isinstance(result.blocked_commands, list)
        assert isinstance(result.blockers, list)
        assert isinstance(result.warnings, list)

    def test_preflight_result_defaults(self) -> None:
        """Fields with defaults work when omitted."""
        blocker = PreflightBlocker(
            code="state_missing", scope="pipeline", message="x", resolution="y"
        )
        assert blocker.code == "state_missing"
        assert blocker.scope == "pipeline"


class TestPreflightResultImmutability:
    """B2: all dataclasses are frozen."""

    def test_preflight_result_immutability(self) -> None:
        result = PreflightResult(
            schema_version="1.0",
            status="ready",
            operation="unknown",
            review_mode="rapid",
            current_stage="bootstrap",
            current_gates={},
            available_commands=[],
            blocked_commands=[],
            next_action=None,
            blockers=[],
            warnings=[],
            can_proceed=False,
            command=None,
        )
        with pytest.raises(FrozenInstanceError):
            result.status = "blocked"  # type: ignore[misc]

    def test_preflight_blocker_immutability(self) -> None:
        blocker = PreflightBlocker(
            code="x", scope="pipeline", message="m", resolution="r"
        )
        with pytest.raises(FrozenInstanceError):
            blocker.code = "y"  # type: ignore[misc]


class TestPreflightBlockerConstruction:
    """B2: PreflightBlocker has code, scope, message, resolution."""

    def test_preflight_blocker_construction(self) -> None:
        blocker = PreflightBlocker(
            code="gate_not_passed",
            scope="command",
            message="Command 'verify' requires gate 'render_passed'",
            resolution="Run 'paper render' first",
        )
        assert blocker.code == "gate_not_passed"
        assert blocker.scope == "command"
        assert "render_passed" in blocker.message
        assert blocker.resolution == "Run 'paper render' first"


class TestBlockedCommandConstruction:
    """B2: BlockedCommand has command, reason, required_stage, missing_gates."""

    def test_blocked_command_construction(self) -> None:
        bc = BlockedCommand(
            command="render",
            reason="requires gate 'style_passed'",
            required_stage="rendering",
            missing_gates=("style_passed", "reporting_passed"),
        )
        assert bc.command == "render"
        assert bc.reason == "requires gate 'style_passed'"
        assert bc.required_stage == "rendering"
        assert bc.missing_gates == ("style_passed", "reporting_passed")

    def test_blocked_command_missing_gates_tuple(self) -> None:
        """missing_gates MUST be a tuple, not a list."""
        bc = BlockedCommand(command="x", reason="y", missing_gates=("a", "b"))
        assert isinstance(bc.missing_gates, tuple)
        assert not isinstance(bc.missing_gates, list)

    def test_blocked_command_defaults(self) -> None:
        bc = BlockedCommand(command="x", reason="y")
        assert bc.required_stage is None
        assert bc.missing_gates == ()

    def test_blocked_command_immutability(self) -> None:
        bc = BlockedCommand(command="x", reason="y")
        with pytest.raises(FrozenInstanceError):
            bc.command = "z"  # type: ignore[misc]


# ─── ReviewConfigSnapshot ────────────────────────────────────────────────────


class TestReviewConfigSnapshotConstruction:
    """B2: ReviewConfigSnapshot has values, source, warnings."""

    def test_review_config_snapshot_construction(self) -> None:
        snap = ReviewConfigSnapshot(
            values={"mode": "academic", "search_window": None, "amendments": []},
            source="file",
            warnings=(),
        )
        assert snap.values["mode"] == "academic"
        assert snap.source == "file"
        assert snap.warnings == ()

    def test_review_config_snapshot_immutability(self) -> None:
        snap = ReviewConfigSnapshot(values={"mode": "rapid"}, source="default_missing")
        with pytest.raises(FrozenInstanceError):
            snap.source = "file"  # type: ignore[misc]


class TestReviewConfigSnapshotSourceTracking:
    """B2: source field tracks provenance (file | default_missing | default_invalid)."""

    def test_review_config_snapshot_source_file(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "outputs"
        config_dir.mkdir()
        (config_dir / "review_config.yaml").write_text("mode: academic\n")
        snap = load_review_config_snapshot(tmp_path)
        assert snap.source == "file"
        assert snap.values["mode"] == "academic"

    def test_review_config_snapshot_source_default_missing(self, tmp_path: Path) -> None:
        snap = load_review_config_snapshot(tmp_path)
        assert snap.source == "default_missing"
        assert snap.values["mode"] == "rapid"
        assert any("not found" in w.lower() or "default" in w.lower() for w in snap.warnings)

    def test_review_config_snapshot_source_default_invalid(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "outputs"
        config_dir.mkdir()
        (config_dir / "review_config.yaml").write_text(": : not valid yaml : :\n")
        snap = load_review_config_snapshot(tmp_path)
        assert snap.source == "default_invalid"
        assert snap.values["mode"] == "rapid"


# ─── Legacy Loader Parity ────────────────────────────────────────────────────


class TestLegacyLoaderParity:
    """B2: load_review_config() delegates to load_review_config_snapshot()."""

    def test_legacy_loader_matches_snapshot_values_for_valid_config(
        self, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / "outputs"
        config_dir.mkdir()
        (config_dir / "review_config.yaml").write_text("mode: academic\n")
        legacy = load_review_config(tmp_path)
        snapshot = load_review_config_snapshot(tmp_path)
        assert legacy["mode"] == snapshot.values["mode"] == "academic"

    def test_legacy_loader_matches_snapshot_values_for_invalid_yaml(
        self, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / "outputs"
        config_dir.mkdir()
        (config_dir / "review_config.yaml").write_text(": : broken : :\n")
        legacy = load_review_config(tmp_path)
        snapshot = load_review_config_snapshot(tmp_path)
        assert legacy["mode"] == snapshot.values["mode"] == "rapid"

    def test_legacy_loader_matches_snapshot_values_for_unknown_mode(
        self, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / "outputs"
        config_dir.mkdir()
        (config_dir / "review_config.yaml").write_text("mode: turbo\n")
        legacy = load_review_config(tmp_path)
        snapshot = load_review_config_snapshot(tmp_path)
        # Both should normalize unknown mode → "rapid"
        assert legacy["mode"] == snapshot.values["mode"] == "rapid"

    def test_legacy_loader_matches_snapshot_for_missing_file(
        self, tmp_path: Path
    ) -> None:
        legacy = load_review_config(tmp_path)
        snapshot = load_review_config_snapshot(tmp_path)
        assert legacy["mode"] == snapshot.values["mode"] == "rapid"
        assert legacy["search_window"] == snapshot.values["search_window"] is None

    def test_legacy_loader_matches_snapshot_for_non_dict_yaml(
        self, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / "outputs"
        config_dir.mkdir()
        (config_dir / "review_config.yaml").write_text("- just\n- a\n- list\n")
        legacy = load_review_config(tmp_path)
        snapshot = load_review_config_snapshot(tmp_path)
        assert legacy["mode"] == snapshot.values["mode"] == "rapid"
        assert snapshot.source == "default_invalid"


# ─── Test Helpers ────────────────────────────────────────────────────────────


def _write_state(
    tmp_path: Path,
    stage: str,
    gates: dict[str, bool] | None = None,
) -> Path:
    """Write a valid state.yaml with realistic cumulative gate progression.

    Sets ALL precondition gates from ALL stages up to and including the target
    stage to True (matching what a real pipeline would look like).
    """
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    state_path = outputs / "state.yaml"

    all_gates: dict[str, bool] = dict.fromkeys(ManuscriptState.REQUIRED_GATES, False)
    # Set cumulative preconditions from all stages up to current (realistic state)
    stage_idx = ManuscriptState.STAGE_ORDER.index(stage)
    for prior_stage in ManuscriptState.STAGE_ORDER[: stage_idx + 1]:
        for gate in ManuscriptState.STAGE_PRECONDITIONS.get(
            prior_stage, frozenset()
        ):
            all_gates[gate] = True
    if gates:
        all_gates.update(gates)

    state = ManuscriptState(stage=stage, gates=all_gates)
    state.validate()
    repo = YamlFileStateRepository(state_path)
    repo.save(state)
    return state_path


def _rapid_snapshot() -> ReviewConfigSnapshot:
    """Clean review config snapshot with no warnings."""
    return ReviewConfigSnapshot(
        values={"mode": "rapid", "search_window": None, "amendments": []},
        source="file",
        warnings=(),
    )


def _write_invalid_state(tmp_path: Path) -> Path:
    """Write a corrupt state.yaml that will fail to parse."""
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    state_path = outputs / "state.yaml"
    state_path.write_text(": : not valid yaml : :\n")
    return state_path


# ─── resolve_preflight: Stage Progression (Task B3) ──────────────────────────


class TestResolvePreflightStages:
    """B3: resolve_preflight returns correct results per pipeline stage."""

    def test_resolve_preflight_bootstrap_stage(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "ready"
        assert result.can_proceed is False
        assert result.next_action == "init"
        assert result.current_stage == "bootstrap"
        assert "init" in result.available_commands

    def test_resolve_preflight_search_stage(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "search")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "ready"
        assert result.next_action == "search"
        assert "search" in result.available_commands

    def test_resolve_preflight_screen_stage(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "screen")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "ready"
        assert result.next_action == "screen"

    def test_resolve_preflight_outline_stage(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "outline")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "ready"
        assert result.next_action == "draft:outline"

    def test_resolve_preflight_drafting_stage(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "ready"
        assert result.next_action == "draft:all"

    def test_resolve_preflight_rendered_stage(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "rendered")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "ready"
        assert result.next_action == "verify"


# ─── resolve_preflight: Missing State (Task B3) ─────────────────────────────


class TestResolvePreflightMissingState:
    """B3: missing state.yaml handling."""

    def test_resolve_preflight_missing_state_yaml(self, tmp_path: Path) -> None:
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "needs_input"
        assert any(b.code == "state_missing" for b in result.blockers)
        assert result.can_proceed is False

    def test_resolve_preflight_missing_state_pipeline_governed(
        self, tmp_path: Path
    ) -> None:
        result = resolve_preflight(
            tmp_path, command="search", review_config=_rapid_snapshot()
        )
        assert result.status == "needs_input"
        assert any(b.code == "state_missing" for b in result.blockers)

    def test_resolve_preflight_pipeline_initializer_no_state(
        self, tmp_path: Path
    ) -> None:
        result = resolve_preflight(
            tmp_path, command="init", review_config=_rapid_snapshot()
        )
        assert result.status == "ready"
        assert result.can_proceed is True
        assert not any(b.code == "state_missing" for b in result.blockers)

    def test_resolve_preflight_standalone_no_state(self, tmp_path: Path) -> None:
        result = resolve_preflight(
            tmp_path, command="audit:prose", review_config=_rapid_snapshot()
        )
        assert result.status == "ready"
        assert result.can_proceed is True


# ─── resolve_preflight: Invalid State (Task B3) ──────────────────────────────


class TestResolvePreflightInvalidState:
    """B3: invalid/corrupt state.yaml handling."""

    def test_resolve_preflight_invalid_state_yaml(self, tmp_path: Path) -> None:
        _write_invalid_state(tmp_path)
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "blocked"
        assert any(b.code == "state_invalid" for b in result.blockers)

    def test_resolve_preflight_pipeline_initializer_corrupt_state(
        self, tmp_path: Path
    ) -> None:
        _write_invalid_state(tmp_path)
        result = resolve_preflight(
            tmp_path, command="init", review_config=_rapid_snapshot()
        )
        assert result.status == "blocked"
        assert result.can_proceed is False

    def test_resolve_preflight_standalone_corrupt_state(
        self, tmp_path: Path
    ) -> None:
        _write_invalid_state(tmp_path)
        result = resolve_preflight(
            tmp_path, command="audit:prose", review_config=_rapid_snapshot()
        )
        assert result.status == "ready"
        assert result.can_proceed is True


# ─── resolve_preflight: Review Config (Task B3) ──────────────────────────────


class TestResolvePreflightReviewConfig:
    """B3: review_config handling."""

    def test_resolve_preflight_missing_review_config(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(tmp_path)
        assert result.review_mode == "rapid"
        assert any(
            "default" in w.lower() or "not found" in w.lower()
            for w in result.warnings
        )
        assert result.status == "ready"

    def test_resolve_preflight_invalid_review_config(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        outputs = tmp_path / "outputs"
        (outputs / "review_config.yaml").write_text(": : broken : :\n")
        result = resolve_preflight(tmp_path)
        assert result.review_mode == "rapid"
        assert result.status == "ready"

    def test_resolve_preflight_valid_review_config(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        outputs = tmp_path / "outputs"
        (outputs / "review_config.yaml").write_text("mode: academic\n")
        result = resolve_preflight(tmp_path)
        assert result.review_mode == "academic"

    def test_resolve_preflight_review_mode_academic(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        snap = ReviewConfigSnapshot(
            values={"mode": "academic", "search_window": None, "amendments": []},
            source="file",
            warnings=(),
        )
        result = resolve_preflight(tmp_path, review_config=snap)
        assert result.review_mode == "academic"

    def test_resolve_preflight_review_mode_rapid(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.review_mode == "rapid"

    def test_resolve_preflight_review_mode_invalid_normalized(
        self, tmp_path: Path
    ) -> None:
        """Invalid mode passed directly via snapshot is normalized to 'rapid'."""
        _write_state(tmp_path, "bootstrap")
        snap = ReviewConfigSnapshot(
            values={"mode": "turbo", "search_window": None, "amendments": []},
            source="file",
            warnings=(),
        )
        result = resolve_preflight(tmp_path, review_config=snap)
        assert result.review_mode == "rapid"


class TestReadinessScopeAndMutatingStandalone:
    """P1: readiness_scope field + warning for mutating standalone commands."""

    def test_readiness_scope_always_present(self, tmp_path: Path) -> None:
        """PreflightResult always includes readiness_scope."""
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.readiness_scope == "workflow_preconditions_only"

    def test_mutating_standalone_emits_warning(self, tmp_path: Path) -> None:
        """Mutating standalone command (e.g. thesaurus:rebuild) with
        can_proceed=True must warn about external side effects."""
        result = resolve_preflight(
            tmp_path,
            command="thesaurus:rebuild",
            review_config=_rapid_snapshot(),
        )
        assert result.can_proceed is True
        assert result.status == "ready"
        assert any("side effects" in w for w in result.warnings)

    def test_mutating_standalone_corrupt_state_warning(self, tmp_path: Path) -> None:
        """thesaurus:import with corrupt state → ready + warning about side effects."""
        outputs = tmp_path / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        (outputs / "state.yaml").write_bytes(b"\x80\x81\x82")

        result = resolve_preflight(
            tmp_path,
            command="thesaurus:import",
            review_config=_rapid_snapshot(),
        )
        assert result.status == "ready"
        assert result.can_proceed is True
        assert any("side effects" in w for w in result.warnings)

    def test_non_mutating_standalone_no_side_effects_warning(
        self, tmp_path: Path
    ) -> None:
        """audit:prose (read-only standalone) must NOT get side-effects warning."""
        result = resolve_preflight(
            tmp_path,
            command="audit:prose",
            review_config=_rapid_snapshot(),
        )
        assert result.can_proceed is True
        assert not any("side effects" in w for w in result.warnings)

    def test_zotero_delete_emits_warning(self, tmp_path: Path) -> None:
        """zotero:delete (external mutating) must warn about side effects."""
        result = resolve_preflight(
            tmp_path,
            command="zotero:delete",
            review_config=_rapid_snapshot(),
        )
        assert result.can_proceed is True
        assert result.status == "ready"
        assert any("side effects" in w for w in result.warnings)

    def test_zotero_delete_corrupt_state_warning(self, tmp_path: Path) -> None:
        """zotero:delete with corrupt state → ready + side effects warning."""
        outputs = tmp_path / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        (outputs / "state.yaml").write_bytes(b"\x80\x81\x82")

        result = resolve_preflight(
            tmp_path,
            command="zotero:delete",
            review_config=_rapid_snapshot(),
        )
        assert result.status == "ready"
        assert result.can_proceed is True
        assert any("side effects" in w for w in result.warnings)

    def test_mesh_export_emits_warning(self, tmp_path: Path) -> None:
        """mesh:export (writes files) must warn about side effects."""
        result = resolve_preflight(
            tmp_path,
            command="mesh:export",
            review_config=_rapid_snapshot(),
        )
        assert result.can_proceed is True
        assert any("side effects" in w for w in result.warnings)


# ─── resolve_preflight: Available/Blocked Commands (Task B3) ─────────────────


class TestResolvePreflightCommands:
    """B3: available_commands and blocked_commands computation."""

    def test_resolve_preflight_available_commands_bootstrap(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert "init" in result.available_commands
        assert "import:bib" in result.available_commands
        assert "search" not in result.available_commands
        assert "doctor" in result.available_commands
        assert "audit:prose" in result.available_commands

    def test_resolve_preflight_available_commands_search(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "search")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert "search" in result.available_commands
        assert "screen" not in result.available_commands
        assert "init" in result.available_commands

    def test_resolve_preflight_available_commands_drafting(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert "draft:section" in result.available_commands
        assert "draft:all" in result.available_commands
        assert "audit:prose" in result.available_commands
        assert "render" not in result.available_commands

    def test_resolve_preflight_blocked_commands(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        blocked_ids = {bc.command for bc in result.blocked_commands}
        assert "render" in blocked_ids
        assert "verify" in blocked_ids

    def test_resolve_preflight_blocked_commands_with_reason(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        render_bc = next(
            bc for bc in result.blocked_commands if bc.command == "render"
        )
        assert render_bc.required_stage == "rendering"
        assert len(render_bc.missing_gates) > 0

    def test_resolve_preflight_standalone_not_blocked(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert "audit:prose" in result.available_commands
        blocked_ids = {bc.command for bc in result.blocked_commands}
        assert "audit:prose" not in blocked_ids


# ─── resolve_preflight: can_proceed (Task B3) ────────────────────────────────


class TestResolvePreflightCanProceed:
    """B3: can_proceed invariant tests."""

    def test_resolve_preflight_can_proceed_false_no_command(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.can_proceed is False

    def test_resolve_preflight_can_proceed_true_command_eligible(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(
            tmp_path, command="draft:section", review_config=_rapid_snapshot()
        )
        assert result.can_proceed is True
        assert result.status == "ready"

    def test_resolve_preflight_can_proceed_false_command_blocked(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(
            tmp_path, command="render", review_config=_rapid_snapshot()
        )
        assert result.can_proceed is False
        assert result.status == "blocked"

    def test_can_proceed_implies_ready(self, tmp_path: Path) -> None:
        """can_proceed=True IMPLIES status=ready (key invariant)."""
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(
            tmp_path, command="draft:section", review_config=_rapid_snapshot()
        )
        if result.can_proceed:
            assert result.status == "ready"


# ─── resolve_preflight: next_action (Task B3) ────────────────────────────────


class TestResolvePreflightNextAction:
    """B3: next_action computation."""

    def test_next_action_bootstrap(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.next_action == "init"

    def test_next_action_search(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "search")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.next_action == "search"

    def test_next_action_screen(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "screen")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.next_action == "screen"

    def test_next_action_outline(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "outline")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.next_action == "draft:outline"

    def test_next_action_rendered(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "rendered")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.next_action == "verify"

    def test_next_action_none_when_command_specified(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(
            tmp_path, command="init", review_config=_rapid_snapshot()
        )
        assert result.next_action is None

    def test_next_action_init_when_state_missing(self, tmp_path: Path) -> None:
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.next_action == "init"

    def test_next_action_none_when_state_invalid(self, tmp_path: Path) -> None:
        _write_invalid_state(tmp_path)
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.next_action is None


# ─── resolve_preflight: Blockers (Task B3) ───────────────────────────────────


class TestResolvePreflightBlockers:
    """B3: blocker structure and scoping."""

    def test_resolve_preflight_blocker_structure(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(
            tmp_path, command="render", review_config=_rapid_snapshot()
        )
        assert len(result.blockers) > 0
        for blocker in result.blockers:
            assert hasattr(blocker, "code")
            assert hasattr(blocker, "scope")
            assert hasattr(blocker, "message")
            assert hasattr(blocker, "resolution")

    def test_resolve_preflight_blocker_scope_pipeline(
        self, tmp_path: Path
    ) -> None:
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        state_blockers = [b for b in result.blockers if b.code == "state_missing"]
        assert len(state_blockers) == 1
        assert state_blockers[0].scope == "pipeline"

    def test_resolve_preflight_blocker_scope_command(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(
            tmp_path, command="render", review_config=_rapid_snapshot()
        )
        command_blockers = [b for b in result.blockers if b.scope == "command"]
        assert len(command_blockers) >= 1


# ─── resolve_preflight: Status (Task B3) ─────────────────────────────────────


class TestResolvePreflightStatus:
    """B3: status computation."""

    def test_resolve_preflight_status_ready(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "ready"

    def test_resolve_preflight_status_needs_input(self, tmp_path: Path) -> None:
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "needs_input"

    def test_resolve_preflight_status_blocked_invalid(self, tmp_path: Path) -> None:
        _write_invalid_state(tmp_path)
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.status == "blocked"

    def test_resolve_preflight_status_blocked_command_not_eligible(
        self, tmp_path: Path
    ) -> None:
        _write_state(tmp_path, "drafting")
        result = resolve_preflight(
            tmp_path, command="render", review_config=_rapid_snapshot()
        )
        assert result.status == "blocked"


# ─── resolve_preflight: Unknown Command (Task B3) ────────────────────────────


class TestResolvePreflightUnknownCommand:
    """B3: unknown command handling — no special-case jump, complete result."""

    def test_resolve_preflight_unknown_command(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(
            tmp_path, command="nonexistent", review_config=_rapid_snapshot()
        )
        assert result.status == "blocked"
        assert result.can_proceed is False
        assert any(b.code == "unknown_command" for b in result.blockers)
        assert result.next_action is None

    def test_resolve_preflight_unknown_command_complete_result(
        self, tmp_path: Path
    ) -> None:
        """Unknown command still builds a complete PreflightResult."""
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(
            tmp_path, command="nonexistent", review_config=_rapid_snapshot()
        )
        assert result.schema_version == "1.0"
        assert result.review_mode == "rapid"
        assert result.current_stage == "bootstrap"
        assert len(result.current_gates) > 0
        assert len(result.available_commands) > 0
        assert len(result.blocked_commands) > 0


# ─── resolve_preflight: Schema Version (Task B3) ─────────────────────────────


class TestResolvePreflightSchemaVersion:
    """B3: schema_version is always '1.0'."""

    def test_schema_version(self, tmp_path: Path) -> None:
        _write_state(tmp_path, "bootstrap")
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.schema_version == "1.0"

    def test_schema_version_missing_state(self, tmp_path: Path) -> None:
        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())
        assert result.schema_version == "1.0"


# ─── Bug Hunt Fixes ──────────────────────────────────────────────────────────


class TestBinaryStateYaml:
    """H1: Binary/non-UTF8 state.yaml must produce state_invalid, not crash."""

    def test_binary_state_yaml_produces_blocked_result(self, tmp_path: Path) -> None:
        """Binary garbage in state.yaml → status=blocked, state_invalid blocker."""
        outputs = tmp_path / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        # Write binary data that cannot be decoded as UTF-8
        (outputs / "state.yaml").write_bytes(b"\x80\x81\x82\xff\xfe")

        result = resolve_preflight(tmp_path, review_config=_rapid_snapshot())

        assert result.status == "blocked"
        assert result.can_proceed is False
        codes = [b.code for b in result.blockers]
        assert "state_invalid" in codes

    def test_binary_state_yaml_with_command(self, tmp_path: Path) -> None:
        """Binary state + standalone command → ready (standalone exempt)."""
        outputs = tmp_path / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        (outputs / "state.yaml").write_bytes(b"\x80\x81\x82\xff\xfe")

        result = resolve_preflight(
            tmp_path, command="audit:prose", review_config=_rapid_snapshot()
        )

        assert result.status == "ready"
        assert result.can_proceed is True


class TestReviewConfigNullMode:
    """L2: mode: null must produce a warning, unlike other invalid modes."""

    def test_null_mode_emits_warning(self, tmp_path: Path) -> None:
        """mode: null in review_config.yaml → warning emitted, mode='rapid'."""
        outputs = tmp_path / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        (outputs / "review_config.yaml").write_text("mode: null\n")

        snapshot = load_review_config_snapshot(tmp_path)

        assert snapshot.values["mode"] == "rapid"
        assert len(snapshot.warnings) > 0
        assert any("null" in w.lower() for w in snapshot.warnings)

    def test_null_mode_legacy_loader_matches_snapshot(self, tmp_path: Path) -> None:
        """Both loaders produce identical values for mode: null."""
        outputs = tmp_path / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        (outputs / "review_config.yaml").write_text("mode: null\n")

        legacy = load_review_config(tmp_path)
        snapshot = load_review_config_snapshot(tmp_path)

        assert legacy["mode"] == snapshot.values["mode"] == "rapid"


class TestBinaryReviewConfig:
    """P1: Binary/non-UTF8 review_config.yaml must produce default_invalid, not crash."""

    def test_binary_review_config_returns_default_invalid_snapshot(
        self, tmp_path: Path
    ) -> None:
        """Binary review_config.yaml → source=default_invalid, defaults returned."""
        outputs = tmp_path / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        (outputs / "review_config.yaml").write_bytes(b"\x80\x81\x82\xff\xfe")

        snapshot = load_review_config_snapshot(tmp_path)

        assert snapshot.source == "default_invalid"
        assert snapshot.values["mode"] == "rapid"
        assert len(snapshot.warnings) > 0

    def test_binary_review_config_preflight_emits_valid_json(
        self, tmp_path: Path
    ) -> None:
        """Binary review_config.yaml + preflight → PreflightResult with valid status."""
        outputs = tmp_path / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        (outputs / "review_config.yaml").write_bytes(b"\x80\x81\x82\xff\xfe")

        result = resolve_preflight(tmp_path, review_config=None)

        # Must not crash — must produce a structured result
        assert result.status in ("ready", "needs_input", "blocked")
        assert result.review_mode == "rapid"


class TestUnknownCommandWithMissingState:
    """P2: unknown_command + state_missing must report BOTH blockers."""

    def test_unknown_command_with_missing_state_reports_both_blockers(
        self, tmp_path: Path
    ) -> None:
        """Unknown cmd + missing state → both state_missing and unknown_command."""
        # No state.yaml — state is missing
        result = resolve_preflight(
            tmp_path,
            command="nonexistent:command",
            review_config=_rapid_snapshot(),
        )

        assert result.status == "blocked"
        codes = [b.code for b in result.blockers]
        assert "unknown_command" in codes
        assert "state_missing" in codes
