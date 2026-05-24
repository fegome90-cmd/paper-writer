from typing import Any

from harness.domain.state import ManuscriptState
from harness.ports.action_runner import ActionRunner
from harness.ports.artifact_checker import ArtifactChecker
from harness.ports.state_repository import StateRepository, StateRepositoryError
from integrations.tools.base import ToolWrapper, ValidatorResult


class InMemoryStateRepository(StateRepository):
    """Mock repository implementing StateRepository for pure in-memory test scenarios."""

    def __init__(self, initial_state: ManuscriptState | None = None) -> None:
        self.current_state = initial_state
        self.exists_flag = initial_state is not None

    def exists(self) -> bool:
        return self.exists_flag

    def load(self) -> ManuscriptState:
        if not self.exists_flag or self.current_state is None:
            raise StateRepositoryError("State file does not exist (mock).")
        # Return a copy to mimic actual serialization/persistence boundaries
        return ManuscriptState(stage=self.current_state.stage, gates=dict(self.current_state.gates))

    def save(self, state: ManuscriptState) -> None:
        self.current_state = ManuscriptState(stage=state.stage, gates=dict(state.gates))
        self.exists_flag = True


class InMemoryArtifactChecker(ArtifactChecker):
    """Mock checker implementing ArtifactChecker for pure in-memory test scenarios."""

    def __init__(self, existing_paths: set[str] | None = None) -> None:
        self.existing_paths = existing_paths if existing_paths is not None else set()

    def check_dir_exists(self, rel_path: str) -> None:
        if rel_path not in self.existing_paths:
            raise FileNotFoundError(f"Directory {rel_path} does not exist (mock).")

    def check_file_exists(self, rel_path: str) -> None:
        if rel_path not in self.existing_paths:
            raise FileNotFoundError(f"File {rel_path} does not exist (mock).")

    def check_any_file_exists(self, rel_paths: list[str]) -> None:
        if not any(p in self.existing_paths for p in rel_paths):
            raise FileNotFoundError(f"None of the files {rel_paths} exist (mock).")

    def get_full_path_str(self, rel_path: str) -> str:
        return f"/mock_root/{rel_path}"


class InMemoryActionRunner(ActionRunner):
    """Mock action runner implementing ActionRunner for pure in-memory test scenarios."""

    def __init__(self, checker: InMemoryArtifactChecker) -> None:
        self.checker = checker
        self.actions_run: list[tuple[str, dict[str, Any]]] = []
        self.manifest_emitted: dict[str, bool] | None = None

    def run_action(self, command: str, args: dict[str, Any]) -> list[str]:
        self.actions_run.append((command, args))

        # Simulate file generation based on command
        if command == "init":
            dirs = ["cli", "harness", "validators", "templates", "outputs"]
            self.checker.existing_paths.update(dirs)
            new_files = [
                "outputs/state.yaml",
                "templates/manuscript.qmd",
                "templates/references.bib",
            ]
            self.checker.existing_paths.update(new_files)
            return new_files
        elif command == "search":
            new_files = ["outputs/search/search_plan.json", "outputs/search/raw_results.json"]
            self.checker.existing_paths.update(new_files)
            return new_files
        elif command == "screen":
            new_files = ["outputs/search/screened_evidence.json"]
            self.checker.existing_paths.update(new_files)
            return new_files
        elif command == "draft_outline":
            new_files = ["outputs/drafts/outline.md"]
            self.checker.existing_paths.update(new_files)
            return new_files
        elif command == "draft_section":
            name = args.get("name", "unknown")
            new_files = [f"outputs/drafts/{name}.md"]
            self.checker.existing_paths.update(new_files)
            return new_files
        elif command in ["lint_bib", "check_refs", "lint_style", "audit_reporting"]:
            new_files = [f"outputs/logs/{command}.log"]
            self.checker.existing_paths.update(new_files)
            return new_files
        elif command == "render":
            new_files = ["outputs/render/manuscript.docx", "outputs/render/manuscript.pdf"]
            self.checker.existing_paths.update(new_files)
            return new_files
        return []

    def emit_manifest(self, gate_snapshot: dict[str, bool]) -> str:
        self.manifest_emitted = gate_snapshot
        manifest_path = "outputs/manifest.yaml"
        self.checker.existing_paths.add(manifest_path)
        return manifest_path


class InMemoryToolWrapper(ToolWrapper):
    """Mock tool wrapper for in-memory orchestrator tests.

    Returns pass results for all validation commands.
    Records calls for assertion in tests.
    """

    def __init__(self, gate: str, return_status: str = "pass") -> None:
        self._gate = gate
        self._return_status = return_status
        self.calls: list[tuple[dict[str, Any], dict[str, Any]]] = []

    @property
    def name(self) -> str:
        return f"mock-{self._gate}"

    @property
    def gate(self) -> str:
        return self._gate

    def is_available(self) -> bool:
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> "ValidatorResult":
        from integrations.tools.base import ValidatorResult

        self.calls.append((artifacts, context))
        return ValidatorResult(
            validator=self._gate,
            status=self._return_status,
            summary=f"Mock wrapper for {self._gate}: {self._return_status}",
            findings=[],
            artifacts_checked=artifacts.get("manuscript_files", []),
        )


def create_mock_wrappers() -> dict[str, ToolWrapper]:
    """Create mock wrappers for all validation commands."""
    return {
        "lint_bib": InMemoryToolWrapper("bib_normalized"),
        "check_refs": InMemoryToolWrapper("citations_resolved"),
        "check_refs_metadata": InMemoryToolWrapper("refs_validated"),
        "lint_style": InMemoryToolWrapper("style_passed"),
        "audit_reporting": InMemoryToolWrapper("reporting_passed"),
    }
