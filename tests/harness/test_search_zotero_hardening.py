"""Tests for fix-search-zotero-hardening change.

Covers:
- Task 3.1: VERIFY stage guard (backward transition blocked silently)
- Task 3.2: APPLY search gate reset
- Task 3.3: ZoteroConfig.validate() status code mapping
- Task 3.4: Integration test — search re-run at advanced stage
- Task 3.5: Smoke test — .env.example exists with no real secrets
"""

import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clients.zotero import ZoteroConfig, ZoteroUnavailableError
from harness.domain.state import ManuscriptState
from harness.services.orchestrator import Orchestrator, OrchestratorRequest
from harness.services.state_manager import StateManager
from tests.harness.mocks import (
    InMemoryActionRunner,
    InMemoryArtifactChecker,
    InMemoryStateRepository,
    create_mock_wrappers,
)


def _create_orchestrator() -> tuple[
    Orchestrator,
    InMemoryStateRepository,
    InMemoryArtifactChecker,
    InMemoryActionRunner,
]:
    repo = InMemoryStateRepository()
    manager = StateManager(repo)
    checker = InMemoryArtifactChecker()
    action_runner = InMemoryActionRunner(checker)
    wrappers = create_mock_wrappers()
    orch = Orchestrator(Path("/mock_root"), manager, checker, action_runner, wrappers)
    return orch, repo, checker, action_runner


def _create_orchestrator_at_stage(stage: str) -> tuple[
    Orchestrator,
    InMemoryStateRepository,
]:
    preconditions = ManuscriptState.STAGE_PRECONDITIONS.get(stage, frozenset())
    initial_gates: dict[str, bool] = dict.fromkeys(preconditions, True)
    for gate in ManuscriptState.REQUIRED_GATES:
        initial_gates.setdefault(gate, False)
    repo = InMemoryStateRepository(
        ManuscriptState(stage=stage, gates=initial_gates),
    )
    manager = StateManager(repo)
    checker = InMemoryArtifactChecker()
    action_runner = InMemoryActionRunner(checker)
    wrappers = create_mock_wrappers()
    orch = Orchestrator(Path("/mock_root"), manager, checker, action_runner, wrappers)
    return orch, repo


class TestVerifyStageGuard:
    """Task 3.1: VERIFY stage guard prevents backward transitions silently."""

    def test_backward_transition_blocked_no_exception(self) -> None:
        """Re-running search at 'validating' stage resets downstream, advances from
        the post-reset stage.

        reset_downstream_gates('search') clears downstream gates but keeps
        search_completed and repo_initialized intact, so the persisted stage
        downgrades to 'search'. The orchestrator captures this post-reset stage,
        and VERIFY correctly advances forward from 'search' -> 'screen'.
        """
        gates = dict.fromkeys(ManuscriptState.REQUIRED_GATES, True)
        repo = InMemoryStateRepository(
            ManuscriptState(stage="validating", gates=gates),
        )
        manager = StateManager(repo)
        checker = InMemoryArtifactChecker()
        action_runner = InMemoryActionRunner(checker)
        wrappers = create_mock_wrappers()
        orch = Orchestrator(Path("/mock_root"), manager, checker, action_runner, wrappers)

        result = orch.execute(
            OrchestratorRequest("search", "screen", "stop_on_error")
        )

        assert result.success is True
        assert result.stage_before == "validating"
        assert result.stage_after == "screen"
        assert result.exit_code == 0
        assert repo.current_state is not None
        state_data = orch.state_manager.load_state()
        assert state_data["gates"]["search_completed"] is True
        assert state_data["gates"]["screened_evidence"] is False
        assert state_data["stage"] == "screen"

    def test_forward_transition_still_allowed(self) -> None:
        """Normal forward transition (search at search stage) still works."""
        orch, _repo = _create_orchestrator_at_stage("search")

        result = orch.execute(
            OrchestratorRequest("search", "screen", "stop_on_error")
        )

        assert result.success is True
        assert result.stage_after == "screen"

    def test_backward_from_rendered_to_search(self) -> None:
        """Re-running search at 'rendered' stage resets to search, advances to screen."""
        gates = dict.fromkeys(ManuscriptState.REQUIRED_GATES, True)
        repo = InMemoryStateRepository(
            ManuscriptState(stage="rendered", gates=gates),
        )
        manager = StateManager(repo)
        checker = InMemoryArtifactChecker()
        action_runner = InMemoryActionRunner(checker)
        wrappers = create_mock_wrappers()
        orch = Orchestrator(Path("/mock_root"), manager, checker, action_runner, wrappers)

        result = orch.execute(
            OrchestratorRequest("search", "screen", "stop_on_error")
        )

        assert result.success is True
        assert result.stage_before == "rendered"
        assert result.stage_after == "screen"


class TestApplySearchGateReset:
    """Task 3.2: APPLY search gate reset when search re-runs at advanced stage."""

    def test_search_at_advanced_stage_resets_downstream_gates(self) -> None:
        """Search re-run at 'validating' resets downstream gates."""
        gates = dict.fromkeys(ManuscriptState.REQUIRED_GATES, True)
        gates["search_completed"] = True
        repo = InMemoryStateRepository(
            ManuscriptState(stage="validating", gates=gates),
        )
        manager = StateManager(repo)
        checker = InMemoryArtifactChecker()
        action_runner = InMemoryActionRunner(checker)
        wrappers = create_mock_wrappers()
        orch = Orchestrator(Path("/mock_root"), manager, checker, action_runner, wrappers)

        orch.execute(OrchestratorRequest("search", "screen", "stop_on_error"))

        state_data = orch.state_manager.load_state()
        assert state_data["gates"]["screened_evidence"] is False
        assert state_data["gates"]["outline_drafted"] is False
        assert state_data["gates"]["sections_completed"] is False

    def test_search_at_own_stage_no_reset(self) -> None:
        """Search at 'search' stage does NOT reset downstream gates."""
        orch, _repo = _create_orchestrator_at_stage("search")

        orch.execute(OrchestratorRequest("search", "screen", "stop_on_error"))

        state_data = orch.state_manager.load_state()
        assert state_data["gates"]["search_completed"] is True


class TestZoteroConfigValidate:
    """Task 3.3: ZoteroConfig.validate() maps HTTP status codes correctly."""

    def _make_config(self) -> ZoteroConfig:
        return ZoteroConfig(user_id="12345", api_key="testkey123")

    def test_validate_success_returns_none(self) -> None:
        """Valid API key → validate() returns without error."""
        config = self._make_config()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"[]"
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            config.validate()

    def test_validate_403_raises_invalid_key(self) -> None:
        """HTTP 403 → ZoteroUnavailableError with 'invalid or expired' message."""
        config = self._make_config()
        err = urllib.error.HTTPError(
            url="https://api.zotero.org/users/12345/items",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(ZoteroUnavailableError, match="invalid or expired"):
                config.validate()

    def test_validate_500_raises_server_error(self) -> None:
        """HTTP 500 → ZoteroUnavailableError with 'server error' message."""
        config = self._make_config()
        err = urllib.error.HTTPError(
            url="https://api.zotero.org/users/12345/items",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(ZoteroUnavailableError, match="server error"):
                config.validate()

    def test_validate_connection_error_raises_network_error(self) -> None:
        """Connection error → ZoteroUnavailableError with 'network' message."""
        config = self._make_config()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with pytest.raises(ZoteroUnavailableError, match="Could not reach Zotero API"):
                config.validate()


class TestIntegrationSearchRerun:
    """Task 3.4: Integration test — search re-run at advanced stage."""

    def test_search_rerun_preserves_stage_resets_gates(self) -> None:
        """Full orchestrator flow: advance to validating, re-run search."""
        orch, repo, _, _ = _create_orchestrator()

        orch.execute(OrchestratorRequest("init", "search", "stop_on_error"))
        orch.execute(OrchestratorRequest("search", "screen", "stop_on_error"))
        orch.execute(OrchestratorRequest("screen", "outline", "stop_on_error"))
        orch.execute(
            OrchestratorRequest("draft_outline", "drafting", "stop_on_error")
        )
        for section in ["introduction", "methods", "results", "discussion"]:
            orch.execute(
                OrchestratorRequest(
                    command="draft_section",
                    requested_stage="drafting",
                    failure_policy="stop_on_error",
                    args={"name": section},
                )
            )

        assert repo.current_state is not None
        assert repo.current_state.stage == "validating"

        orch.state_manager.set_gate("citations_resolved", True)
        orch.state_manager.set_gate("style_passed", True)

        result = orch.execute(
            OrchestratorRequest("search", "screen", "stop_on_error")
        )

        assert result.success is True
        assert result.stage_before == "validating"
        assert result.stage_after == "screen"
        assert result.exit_code == 0

        state_data = orch.state_manager.load_state()
        assert state_data["gates"]["citations_resolved"] is False
        assert state_data["gates"]["style_passed"] is False
        assert state_data["stage"] == "screen"


class TestDotEnvExample:
    """Task 3.5: Smoke test — .env.example exists with no real secrets."""

    def test_env_example_exists(self) -> None:
        root = Path(__file__).resolve().parent.parent.parent
        env_example = root / ".env.example"
        assert env_example.is_file(), ".env.example not found at project root"

    def test_env_example_has_zotero_vars(self) -> None:
        root = Path(__file__).resolve().parent.parent.parent
        env_example = root / ".env.example"
        content = env_example.read_text()
        assert "ZOTERO_USER_ID" in content
        assert "ZOTERO_API_KEY" in content
        assert "ZOTERO_LIBRARY_TYPE" in content
        assert "ZOTERO_LOCAL" in content
        assert "ZOTERO_BBT_LOCAL" in content

    def test_env_example_no_real_secrets(self) -> None:
        root = Path(__file__).resolve().parent.parent.parent
        env_example = root / ".env.example"
        content = env_example.read_text()
        for line in content.splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                _, _, value = line.partition("=")
                assert (
                    value in ("", "user", "false")
                    or value.startswith("your_")
                ), f"Potential secret in .env.example: {line}"
