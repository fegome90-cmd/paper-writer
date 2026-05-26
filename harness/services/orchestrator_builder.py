from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.adapters.filesystem_action_runner import FilesystemActionRunner
from harness.adapters.filesystem_artifact_checker import FilesystemArtifactChecker
from harness.adapters.yaml_repository import YamlFileStateRepository
from harness.ports.action_runner import ActionRunner
from harness.ports.artifact_checker import ArtifactChecker
from harness.ports.skill_adapter import SkillAdapter
from harness.ports.tool_wrapper import ToolWrapper
from harness.services.state_manager import StateManager
from integrations.tools import (
    BibliographyNormalizer,
    PandocRenderer,
    RefsMetadataValidator,
    RefsValidator,
    ReportingAuditor,
    StyleLinter,
    ZoteroImporter,
)
from skills.local.adapters import AcademicWriterAdapter, LiteratureSearchAdapter

__all__ = ["OrchestratorDependencies", "build_orchestrator_dependencies"]


@dataclass(frozen=True)
class OrchestratorDependencies:
    repo_path: Path
    state_manager: StateManager
    checker: ArtifactChecker
    action_runner: ActionRunner
    wrappers: dict[str, ToolWrapper]
    skill_adapters: dict[str, SkillAdapter]


def build_orchestrator_dependencies(
    project_root: Path | None = None,
    skill_adapters: dict[str, SkillAdapter] | None = None,
) -> OrchestratorDependencies:
    # 1. Resolve project_root
    if project_root is None:
        project_root = Path.cwd()

    # 2-4. State infrastructure (internal, not exposed)
    state_file_path = project_root / "outputs" / "state.yaml"
    repository = YamlFileStateRepository(state_file_path)
    state_manager = StateManager(repository)

    # 5. Artifact checker
    checker = FilesystemArtifactChecker(project_root)

    # 6. Skill adapters: use provided dict as-is, or create defaults
    resolved_skill_adapters: dict[str, SkillAdapter]
    if skill_adapters is not None:
        resolved_skill_adapters = skill_adapters
    else:
        resolved_skill_adapters = {
            "literature_search": LiteratureSearchAdapter(),
            "academic_writer": AcademicWriterAdapter(),
        }

    # 7. Action runner
    action_runner = FilesystemActionRunner(project_root, skill_adapters=resolved_skill_adapters)

    # 8. Tool wrappers (fresh instances per call)
    wrappers: dict[str, ToolWrapper] = {
        "lint_bib": BibliographyNormalizer(),
        "check_refs": RefsValidator(),
        "check_refs_metadata": RefsMetadataValidator(),
        "lint_style": StyleLinter(),
        "audit_reporting": ReportingAuditor(),
        "render": PandocRenderer(),
        "import_bib": ZoteroImporter(),
    }

    # 9. Return assembled dependencies
    return OrchestratorDependencies(
        repo_path=project_root,
        state_manager=state_manager,
        checker=checker,
        action_runner=action_runner,
        wrappers=wrappers,
        skill_adapters=resolved_skill_adapters,
    )
