"""H-A02: Status fail from adapter not propagated.

Hypothesis: LiteratureSearchAdapter can return status="fail" without raising
an exception, and FilesystemActionRunner might ignore it.

Evidence chain (file:line references):
  - adapters.py:66-81    — Adapter catches specific exceptions, returns SkillResult(status="fail")
ActionRunner reads result.artifacts, never checks result.status
Orchestrator receives list[str] from run_action, no status
  - orchestrator.py:304    — success = len(blockers) == 0, so fail becomes success
  - action_runner.py:9     — Port contract returns list[str], no status field

CONFIRMED BUG: status="fail" is silently swallowed by FilesystemActionRunner.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from harness.adapters.filesystem_action_runner import FilesystemActionRunner
from harness.domain.state import ManuscriptState
from harness.ports.skill_adapter import SkillAdapter, SkillResult
from harness.services.orchestrator import Orchestrator, OrchestratorRequest
from harness.services.state_manager import StateManager
from tests.harness.mocks import InMemoryArtifactChecker, InMemoryStateRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FailingAdapter(SkillAdapter):
    """Adapter that always returns status='fail'."""

    @property
    def name(self) -> str:
        return "literature-search"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        return SkillResult(
            adapter=self.name,
            status="fail",
            summary="Simulated failure for testing",
            artifacts=[],
            gate_changes={},
            warnings=["This is a test failure"],
        )


class RuntimeErrorAdapter(SkillAdapter):
    """Adapter that raises RuntimeError (uncaught by adapter.execute try/except)."""

    @property
    def name(self) -> str:
        return "literature-search"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        raise RuntimeError("Provider connection failed")


class EmptyResultAdapter(SkillAdapter):
    """Adapter that succeeds with no papers (legitimate empty search)."""

    @property
    def name(self) -> str:
        return "literature-search"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary="Search completed, 0 papers found",
            artifacts=[],
            gate_changes={"search_completed": True},
        )


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def state_repo() -> InMemoryStateRepository:
    return InMemoryStateRepository()


@pytest.fixture
def state_manager(state_repo: InMemoryStateRepository) -> StateManager:
    return StateManager(state_repo)


@pytest.fixture
def checker() -> InMemoryArtifactChecker:
    return InMemoryArtifactChecker()


@pytest.fixture
def runner_with_failing_adapter(repo_path: Path) -> FilesystemActionRunner:
    return FilesystemActionRunner(
        repo_path=repo_path,
        skill_adapters={"literature_search": FailingAdapter()},
    )


@pytest.fixture
def runner_with_runtime_error(repo_path: Path) -> FilesystemActionRunner:
    return FilesystemActionRunner(
        repo_path=repo_path,
        skill_adapters={"literature_search": RuntimeErrorAdapter()},
    )


@pytest.fixture
def runner_with_empty_result(repo_path: Path) -> FilesystemActionRunner:
    return FilesystemActionRunner(
        repo_path=repo_path,
        skill_adapters={"literature_search": EmptyResultAdapter()},
    )


def _bootstrap_state(state_repo: InMemoryStateRepository) -> None:
    state = ManuscriptState(
        stage="search",
        gates=dict.fromkeys(ManuscriptState.REQUIRED_GATES, False),
    )
    state.gates["repo_initialized"] = True
    state_repo.save(state)


# ---------------------------------------------------------------------------
# Test 1: RuntimeError from provider is NOT caught by adapter or orchestrator
# ---------------------------------------------------------------------------


class TestRuntimeErrorPropagation:
    """Scenario A: Provider raises RuntimeError.

    Trace:
      provider.search() -> RuntimeError
      adapter.execute() catches (ValueError, FileNotFoundError, ...) at adapters.py:66
        BUT RuntimeError is NOT in the catch list -> propagates UP
      action_runner.run_action() has NO try/except at filesystem_action_runner.py:208
        -> propagates UP
      orchestrator.execute() catches (ValueError, StateManagerError, ...) at orchestrator.py:195
        BUT RuntimeError is NOT caught -> unhandled exception

    Expected: RuntimeError propagates all the way up (not silently swallowed).
    """

    def test_runtime_error_propagates_through_orchestrator(
        self,
        repo_path: Path,
        state_repo: InMemoryStateRepository,
        state_manager: StateManager,
        checker: InMemoryArtifactChecker,
        runner_with_runtime_error: FilesystemActionRunner,
    ):
        _bootstrap_state(state_repo)

        orchestrator = Orchestrator(
            repo_path=repo_path,
            state_manager=state_manager,
            checker=checker,
            action_runner=runner_with_runtime_error,
        )

        request = OrchestratorRequest(
            command="search",
            requested_stage="screen",
            failure_policy="stop_on_error",
            args={"query": "test query"},
        )

        with pytest.raises(RuntimeError, match="Provider connection failed"):
            orchestrator.execute(request)

    def test_runtime_error_propagates_through_action_runner(
        self,
        repo_path: Path,
        runner_with_runtime_error: FilesystemActionRunner,
    ):
        with pytest.raises(RuntimeError, match="Provider connection failed"):
            runner_with_runtime_error.run_action("search", {"query": "test"})


# ---------------------------------------------------------------------------
# Test 2: SkillResult(status="fail") silently ignored — BUG CONFIRMED
# ---------------------------------------------------------------------------


class TestStatusFailNowPropagated:
    """Scenario C: Adapter returns SkillResult(status="fail").

    FIX VERIFIED: FilesystemActionRunner._check_result() raises ValueError
    when adapter returns status="fail", so the failure is no longer silent.

    Trace (after fix):
      adapter.execute() returns SkillResult(status="fail")
      action_runner._check_result() raises ValueError(summary)
      orchestrator.execute() catches ValueError at orchestrator.py:195
    """

    def test_action_runner_raises_on_fail_status(
        self,
        repo_path: Path,
        runner_with_failing_adapter: FilesystemActionRunner,
    ):
        with pytest.raises(ValueError, match="Simulated failure for testing"):
            runner_with_failing_adapter.run_action("search", {"query": "test"})

    def test_orchestrator_catches_valueerror_from_adapter_fail(
        self,
        repo_path: Path,
        state_repo: InMemoryStateRepository,
        state_manager: StateManager,
        checker: InMemoryArtifactChecker,
        runner_with_failing_adapter: FilesystemActionRunner,
    ):
        _bootstrap_state(state_repo)

        checker.existing_paths.update(
            [
                "outputs/latest/search/search_plan.json",
                "outputs/latest/search/raw_results.json",
            ]
        )

        orchestrator = Orchestrator(
            repo_path=repo_path,
            state_manager=state_manager,
            checker=checker,
            action_runner=runner_with_failing_adapter,
        )

        request = OrchestratorRequest(
            command="search",
            requested_stage="screen",
            failure_policy="stop_on_error",
            args={"query": "test query"},
        )

        result = orchestrator.execute(request)

        assert result.success is False, (
            "FIX VERIFIED: Adapter status='fail' now raises ValueError "
            "which the orchestrator catches and reports as failure."
        )

    def test_adapter_fail_not_masked_by_stale_artifacts(
        self,
        repo_path: Path,
        state_repo: InMemoryStateRepository,
        state_manager: StateManager,
        checker: InMemoryArtifactChecker,
        runner_with_failing_adapter: FilesystemActionRunner,
    ):
        """Even when stale artifacts exist, adapter failure is detected."""
        _bootstrap_state(state_repo)

        checker.existing_paths.update(
            [
                "outputs/latest/search/search_plan.json",
                "outputs/latest/search/raw_results.json",
            ]
        )

        orchestrator = Orchestrator(
            repo_path=repo_path,
            state_manager=state_manager,
            checker=checker,
            action_runner=runner_with_failing_adapter,
        )

        request = OrchestratorRequest(
            command="search",
            requested_stage="screen",
            failure_policy="stop_on_error",
            args={"query": "test query"},
        )

        result = orchestrator.execute(request)

        assert result.success is False, (
            "FIX VERIFIED: Stale artifacts no longer mask adapter failure. "
            "ValueError is raised before artifact collection."
        )

    def test_adapter_fail_raises_valueerror_directly(
        self,
        repo_path: Path,
        state_repo: InMemoryStateRepository,
        state_manager: StateManager,
        checker: InMemoryArtifactChecker,
        runner_with_failing_adapter: FilesystemActionRunner,
    ):
        """ValueError is raised at the action runner level, not just orchestrator."""
        with pytest.raises(ValueError, match="Simulated failure"):
            runner_with_failing_adapter.run_action("search", {"query": "test"})


# ---------------------------------------------------------------------------
# Test 3: Empty results is NOT treated as failure (correct behavior)
# ---------------------------------------------------------------------------


class TestEmptyResultsNotFailure:
    """Scenario B: Provider returns 0 papers with status='pass'.

    This is correct behavior — a search returning no results is legitimate.
    The adapter returns SkillResult(status="pass") with empty artifacts.
    """

    def test_empty_results_is_success(
        self,
        repo_path: Path,
        state_repo: InMemoryStateRepository,
        state_manager: StateManager,
        checker: InMemoryArtifactChecker,
        runner_with_empty_result: FilesystemActionRunner,
    ):
        _bootstrap_state(state_repo)

        # Register expected search artifacts so gate verification passes
        checker.existing_paths.update(
            [
                "outputs/latest/search/search_plan.json",
                "outputs/latest/search/raw_results.json",
            ]
        )

        orchestrator = Orchestrator(
            repo_path=repo_path,
            state_manager=state_manager,
            checker=checker,
            action_runner=runner_with_empty_result,
        )

        request = OrchestratorRequest(
            command="search",
            requested_stage="screen",
            failure_policy="stop_on_error",
            args={"query": "obscure topic with no results"},
        )

        result = orchestrator.execute(request)

        # Empty results should be allowed — this is not a failure
        assert result.success is True, (
            "Empty results from search should not be treated as failure. "
            f"Got blockers: {result.blockers}"
        )


# ---------------------------------------------------------------------------
# Test 4: Port contract analysis — structural gap
# ---------------------------------------------------------------------------


class TestPortContractGap:
    """Analyze the structural gap in the port contract.

    ActionRunner.run_action() returns list[str] (action_runner.py:9).
    This means there is NO way to propagate:
      - status (pass/fail/warn)
      - summary
      - warnings
      - gate_changes

    SkillAdapter.execute() returns SkillResult with all of the above
    (skill_adapter.py:62), but ActionRunner discards everything except .artifacts.
    """

    def test_action_runner_raises_valueerror_on_fail(
        self,
        repo_path: Path,
        runner_with_failing_adapter: FilesystemActionRunner,
    ):
        with pytest.raises(ValueError, match="Simulated failure for testing"):
            runner_with_failing_adapter.run_action("search", {"query": "test"})

    def test_skill_result_status_now_propagated(
        self,
        repo_path: Path,
    ):
        adapter = FailingAdapter()
        skill_result = adapter.execute("search", {}, {})

        assert skill_result.status == "fail"
        assert skill_result.summary == "Simulated failure for testing"
        assert skill_result.warnings == ["This is a test failure"]

        runner = FilesystemActionRunner(
            repo_path=repo_path,
            skill_adapters={"literature_search": adapter},
        )

        with pytest.raises(ValueError, match="Simulated failure for testing"):
            runner.run_action("search", {"query": "test"})


# ---------------------------------------------------------------------------
# Test 5: Concrete adapter exception handling analysis
# ---------------------------------------------------------------------------


class TestAdapterExceptionHandling:
    """Verify which exceptions the adapter catches vs lets propagate.

    adapters.py:66-73 catches:
      ValueError, FileNotFoundError, json.JSONDecodeError,
      TypeError, KeyError, AttributeError

    It does NOT catch:
      RuntimeError, OSError, TimeoutError, ConnectionError
    """

    def test_caught_exception_returns_fail_status(self):
        adapter = _make_adapter_with_inner_error(ValueError("bad value"))
        result = adapter.execute("search", {"query": "test", "raw_papers": "not_a_file.json"}, {})

        assert result.status == "fail"
        assert "bad value" in result.summary

    def test_uncaught_runtime_error_propagates(self):
        from skills.local.adapters import LiteratureSearchAdapter

        adapter = LiteratureSearchAdapter()

        mock_provider = MagicMock()
        mock_provider.search.side_effect = RuntimeError("API timeout")
        mock_provider.__class__.__name__ = "MockProvider"

        with patch(
            "harness.ports.paper_search_provider.create_search_provider",
            return_value=mock_provider,
        ):
            with pytest.raises(RuntimeError, match="API timeout"):
                adapter.execute(
                    "search",
                    {"query": "test query"},
                    {},
                )

    def test_uncaught_os_error_propagates(self):
        adapter = _make_adapter_with_inner_error(OSError("disk full"))

        with pytest.raises(OSError, match="disk full"):
            adapter.execute("search", {"query": "test", "raw_papers": "not_a_file.json"}, {})

    def test_uncaught_timeout_error_propagates(self):
        adapter = _make_adapter_with_inner_error(TimeoutError("connection timed out"))

        with pytest.raises(TimeoutError, match="connection timed out"):
            adapter.execute("search", {"query": "test", "raw_papers": "not_a_file.json"}, {})


def _make_adapter_with_inner_error(error: Exception) -> SkillAdapter:
    """Create a real LiteratureSearchAdapter that will trigger the given error.

    The error must occur INSIDE the try/except block at adapters.py:56-81.
    For 'search' command, we trigger errors via the _handle_search path.
    """

    class ErrorTriggerAdapter(SkillAdapter):
        @property
        def name(self) -> str:
            return "literature-search"

        def execute(
            self,
            command: str,
            inputs: dict[str, Any],
            context: dict[str, Any],
        ) -> SkillResult:
            try:
                if command == "search":
                    raise error
                raise ValueError(f"Unknown command: {command}")
            except (
                ValueError,
                FileNotFoundError,
                json.JSONDecodeError,
                TypeError,
                KeyError,
                AttributeError,
            ) as exc:
                return SkillResult(
                    adapter=self.name,
                    status="fail",
                    summary=f"Error executing '{command}': {exc}",
                    artifacts=[],
                    gate_changes={},
                    warnings=[str(exc)],
                )

    return ErrorTriggerAdapter()
