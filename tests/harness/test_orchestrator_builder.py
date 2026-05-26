from __future__ import annotations

import dataclasses
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harness.ports.action_runner import ActionRunner
from harness.ports.artifact_checker import ArtifactChecker
from harness.ports.skill_adapter import SkillAdapter
from harness.ports.tool_wrapper import ToolWrapper
from harness.services.orchestrator import Orchestrator, OrchestratorRequest
from harness.services.orchestrator_builder import (
    OrchestratorDependencies,
    build_orchestrator_dependencies,
)
from harness.services.state_manager import StateManager


class TestBuilderContract:
    """Contract tests for build_orchestrator_dependencies."""

    def test_builder_returns_correct_types(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        deps = build_orchestrator_dependencies()

        assert isinstance(deps, OrchestratorDependencies)
        assert isinstance(deps.repo_path, Path)
        assert isinstance(deps.state_manager, StateManager)
        assert isinstance(deps.checker, ArtifactChecker)
        assert isinstance(deps.action_runner, ActionRunner)
        assert isinstance(deps.wrappers, types.MappingProxyType)
        for w in deps.wrappers.values():
            assert isinstance(w, ToolWrapper)
        assert isinstance(deps.skill_adapters, types.MappingProxyType)

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
            wrappers=types.MappingProxyType({}),
            skill_adapters=types.MappingProxyType({}),
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
            dict(deps.wrappers),
        )
        assert orchestrator is not None

    def test_builder_rejects_nonexistent_project_root(self, tmp_path: Path) -> None:
        """build_orchestrator_dependencies raises ValueError for missing path."""
        missing = tmp_path / "no_such_dir"
        with pytest.raises(ValueError, match="Project root does not exist"):
            build_orchestrator_dependencies(project_root=missing)

    def test_builder_dicts_are_immutable_through_proxy(self, tmp_path: Path) -> None:
        """MappingProxyType fields reject mutation even though they wrap dicts."""
        deps = build_orchestrator_dependencies(project_root=tmp_path)
        with pytest.raises(TypeError):
            deps.wrappers["new_key"] = MagicMock()  # type: ignore[index,misc]
        with pytest.raises(TypeError):
            deps.skill_adapters["new_key"] = MagicMock()  # type: ignore[index,misc]

    def test_builder_copies_dicts_before_wrapping(self, tmp_path: Path) -> None:
        """External dict reference cannot mutate the returned data."""
        original_dict: dict[str, SkillAdapter] = {"test": MagicMock(spec=SkillAdapter)}
        deps = build_orchestrator_dependencies(
            project_root=tmp_path, skill_adapters=original_dict
        )
        # Mutating the original should NOT affect the deps
        original_dict["injected"] = MagicMock(spec=SkillAdapter)
        assert "injected" not in deps.skill_adapters
        # Also verify action_runner holds an independent copy, not the original reference
        assert "injected" not in getattr(deps.action_runner, "_skill_adapters")

    def test_builder_returns_concrete_wrapper_types(self, tmp_path: Path) -> None:
        """Verify each wrapper key maps to the expected concrete type."""
        from integrations.tools import (
            BibliographyNormalizer,
            PandocRenderer,
            RefsMetadataValidator,
            RefsValidator,
            ReportingAuditor,
            StyleLinter,
            ZoteroImporter,
        )

        deps = build_orchestrator_dependencies(project_root=tmp_path)
        assert isinstance(deps.wrappers["lint_bib"], BibliographyNormalizer)
        assert isinstance(deps.wrappers["check_refs"], RefsValidator)
        assert isinstance(deps.wrappers["check_refs_metadata"], RefsMetadataValidator)
        assert isinstance(deps.wrappers["lint_style"], StyleLinter)
        assert isinstance(deps.wrappers["audit_reporting"], ReportingAuditor)
        assert isinstance(deps.wrappers["render"], PandocRenderer)
        assert isinstance(deps.wrappers["import_bib"], ZoteroImporter)

    @pytest.mark.integration
    def test_builder_and_orchestrator_end_to_end_integration(self, tmp_path: Path) -> None:
        deps = build_orchestrator_dependencies(project_root=tmp_path)
        orchestrator = Orchestrator(
            deps.repo_path,
            deps.state_manager,
            deps.checker,
            deps.action_runner,
            dict(deps.wrappers),
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
