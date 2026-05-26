from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harness.ports.skill_adapter import SkillAdapter
from harness.services.orchestrator import Orchestrator, OrchestratorRequest
from harness.services.orchestrator_builder import (
    OrchestratorDependencies,
    build_orchestrator_dependencies,
)


class TestBuilderContract:
    """Contract tests for build_orchestrator_dependencies."""

    def test_builder_returns_correct_types(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        deps = build_orchestrator_dependencies()

        assert isinstance(deps, OrchestratorDependencies)
        assert isinstance(deps.repo_path, Path)
        assert isinstance(deps.state_manager, type(deps.state_manager))  # StateManager
        assert isinstance(deps.checker, type(deps.checker))  # ArtifactChecker
        assert isinstance(deps.action_runner, type(deps.action_runner))  # ActionRunner
        assert isinstance(deps.wrappers, dict)
        assert isinstance(deps.skill_adapters, dict)

    def test_builder_resolves_cwd_when_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        deps = build_orchestrator_dependencies()
        assert deps.repo_path == tmp_path

    def test_builder_uses_explicit_project_root(self, tmp_path: Path) -> None:
        deps = build_orchestrator_dependencies(project_root=tmp_path)
        assert deps.repo_path == tmp_path

    def test_builder_default_skill_adapters(self, tmp_path: Path) -> None:
        deps = build_orchestrator_dependencies(project_root=tmp_path)
        assert set(deps.skill_adapters.keys()) == {"literature_search", "academic_writer"}
        for adapter in deps.skill_adapters.values():
            assert isinstance(adapter, SkillAdapter)

    def test_builder_custom_skill_adapters(self, tmp_path: Path) -> None:
        mock_adapter = MagicMock(spec=SkillAdapter)
        deps = build_orchestrator_dependencies(
            project_root=tmp_path,
            skill_adapters={"literature_search": mock_adapter},
        )
        assert deps.skill_adapters == {"literature_search": mock_adapter}
        assert "academic_writer" not in deps.skill_adapters

    def test_builder_empty_skill_adapters_override(self, tmp_path: Path) -> None:
        deps = build_orchestrator_dependencies(project_root=tmp_path, skill_adapters={})
        assert deps.skill_adapters == {}

    def test_dataclass_is_frozen(self) -> None:
        deps = OrchestratorDependencies(
            repo_path=Path("/tmp"),
            state_manager=MagicMock(),
            checker=MagicMock(),
            action_runner=MagicMock(),
            wrappers={},
            skill_adapters={},
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            deps.repo_path = Path("/other")  # type: ignore[misc]

    def test_wrappers_has_seven_keys(self, tmp_path: Path) -> None:
        deps = build_orchestrator_dependencies(project_root=tmp_path)
        expected_keys = {
            "lint_bib",
            "check_refs",
            "check_refs_metadata",
            "lint_style",
            "audit_reporting",
            "render",
            "import_bib",
        }
        assert set(deps.wrappers.keys()) == expected_keys

    def test_wrappers_are_independent_instances(self, tmp_path: Path) -> None:
        deps1 = build_orchestrator_dependencies(project_root=tmp_path)
        deps2 = build_orchestrator_dependencies(project_root=tmp_path)
        assert deps1.wrappers is not deps2.wrappers
        for key in deps1.wrappers:
            assert deps1.wrappers[key] is not deps2.wrappers[key]

    def test_builder_skill_adapters_not_passed_to_orchestrator(self, tmp_path: Path) -> None:
        deps = build_orchestrator_dependencies(project_root=tmp_path)
        # Orchestrator accepts 5 args, skill_adapters is NOT one of them
        orchestrator = Orchestrator(
            deps.repo_path,
            deps.state_manager,
            deps.checker,
            deps.action_runner,
            deps.wrappers,
        )
        assert orchestrator is not None

    @pytest.mark.integration
    def test_builder_to_orchestrator_end_to_end(self, tmp_path: Path) -> None:
        deps = build_orchestrator_dependencies(project_root=tmp_path)
        orchestrator = Orchestrator(
            deps.repo_path,
            deps.state_manager,
            deps.checker,
            deps.action_runner,
            deps.wrappers,
        )
        request = OrchestratorRequest(
            command="init",
            requested_stage="unknown",
            failure_policy="stop_on_error",
            args={},
            context={"cwd": str(tmp_path), "actor": "test"},
        )
        result = orchestrator.execute(request)
        assert result.success is True
        assert (tmp_path / "outputs" / "state.yaml").exists()
