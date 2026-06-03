from __future__ import annotations

import types
from dataclasses import dataclass
from pathlib import Path

from harness.adapters.filesystem_action_runner import FilesystemActionRunner
from harness.adapters.filesystem_artifact_checker import FilesystemArtifactChecker
from harness.adapters.local_tool_resolver import LocalToolResolver
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
    """Frozen container of assembled dependencies for Orchestrator construction.

    Both `wrappers` and `skill_adapters` are wrapped in MappingProxyType for
    true immutability at the container level. Dicts are copied before wrapping
    so external references cannot mutate the data through the proxy.

    Note on `skill_adapters`: This field is NOT consumed by the Orchestrator
    constructor — the CLI uses default skill_adapters (None) and never reads
    deps.skill_adapters back from the builder result. It exists for testability
    and decoupling: tests can inject fakes and assert on what was wired, and
    FilesystemActionRunner consumes the adapters internally during builder
    assembly (step 7). This is an intentional tradeoff accepted in the design.
    """

    repo_path: Path
    state_manager: StateManager
    checker: ArtifactChecker
    action_runner: ActionRunner
    wrappers: types.MappingProxyType[str, ToolWrapper]
    skill_adapters: types.MappingProxyType[str, SkillAdapter]


def build_orchestrator_dependencies(
    project_root: Path | None = None,
    skill_adapters: dict[str, SkillAdapter] | None = None,
) -> OrchestratorDependencies:
    """Construct all orchestrator dependencies: state, checker, action runner, tool wrappers."""
    # 1. Resolve and validate project_root
    if project_root is None:
        raise ValueError(
            "project_root is required — CLI must always provide it via resolve_project_root()"
        )
    if not project_root.is_dir():
        raise ValueError(f"Project root does not exist or is not a directory: {project_root}")

    # 2-4. State infrastructure (internal, not exposed)
    state_file_path = project_root / "outputs" / "state.yaml"
    repository = YamlFileStateRepository(state_file_path)
    state_manager = StateManager(repository)

    # 5. Artifact checker
    checker = FilesystemArtifactChecker(project_root)

    # 6. Skill adapters: copy once to sever external reference, or create defaults
    resolved_skill_adapters: dict[str, SkillAdapter]
    if skill_adapters is not None:
        resolved_skill_adapters = dict(skill_adapters)
    else:
        resolved_skill_adapters = {
            "literature_search": LiteratureSearchAdapter(),
            "academic_writer": AcademicWriterAdapter(),
        }

    # 7. Action runner
    action_runner = FilesystemActionRunner(project_root, skill_adapters=resolved_skill_adapters)

    # 8. Tool resolver for binary resolution
    tool_resolver = LocalToolResolver(project_root)

    # 9. Tool wrappers (fresh instances per call)
    wrappers: dict[str, ToolWrapper] = {
        "lint_bib": BibliographyNormalizer(resolver=tool_resolver),
        "check_refs": RefsValidator(),
        "check_refs_metadata": RefsMetadataValidator(),
        "lint_style": StyleLinter(resolver=tool_resolver),
        "audit_reporting": ReportingAuditor(),
        "render": PandocRenderer(resolver=tool_resolver),
        "import_bib": ZoteroImporter(),
    }

    # 10. Return assembled dependencies with immutable dict wrappers.
    # Copy dicts before wrapping so external references cannot mutate
    # the data through the proxy.
    return OrchestratorDependencies(
        repo_path=project_root,
        state_manager=state_manager,
        checker=checker,
        action_runner=action_runner,
        wrappers=types.MappingProxyType(dict(wrappers)),
        skill_adapters=types.MappingProxyType(resolved_skill_adapters),
    )
