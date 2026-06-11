"""H-A01: Fallback synthetic contamination hypothesis test.

Hypothesis: FilesystemActionRunner can generate a fictitious paper when the
adapter fails or produces no artifact. Mock data exists at lines 225-233
("Mock Paper 1", "10.1000/xyz123"). Mitigated by builder wiring but needs
verification.

This test verifies three code paths:
1. When the search provider fails with a RuntimeError, NO mock data is written
2. The mock path only triggers when runner is explicitly constructed without adapters
3. OrchestratorBuilder ALWAYS wires "literature_search" adapter
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from harness.adapters.filesystem_action_runner import FilesystemActionRunner
from harness.ports.skill_adapter import SkillAdapter, SkillResult
from harness.services.orchestrator_builder import build_orchestrator_dependencies


class _FailingSearchAdapter(SkillAdapter):
    """Adapter whose search() always raises RuntimeError (uncaught by execute)."""

    @property
    def name(self) -> str:
        return "literature-search"

    def execute(self, command, inputs, context):
        if command == "search":
            raise RuntimeError("Provider exploded — simulated MCP crash")
        return SkillResult(
            adapter=self.name,
            status="fail",
            summary="not tested",
            artifacts=[],
            gate_changes={},
        )


class _CaughtFailAdapter(SkillAdapter):
    """Adapter that returns status=fail (simulating a caught exception)."""

    @property
    def name(self) -> str:
        return "literature-search"

    def execute(self, command, inputs, context):
        return SkillResult(
            adapter=self.name,
            status="fail",
            summary="Simulated provider failure",
            artifacts=[],
            gate_changes={},
        )


MOCK_PAPER_TITLE = "Mock Paper 1"
MOCK_PAPER_DOI = "10.1000/xyz123"


class TestProviderFailureNoMockData:
    """When the search provider fails, NO mock/fabricated data is written."""

    def test_runtime_error_propagates_no_mock_written(self, tmp_path):
        """RuntimeError from provider is NOT caught by adapter.execute(), so it
        propagates through run_action(). No files written at all."""
        adapter = _FailingSearchAdapter()
        runner = FilesystemActionRunner(
            repo_path=tmp_path,
            skill_adapters={"literature_search": adapter},
            run_id="test-run",
        )
        runner.run_action("init", {})

        with pytest.raises(RuntimeError, match="Provider exploded"):
            runner.run_action("search", {"query": "cancer immunotherapy"})

        # Search generated a fresh run_id before the error
        outputs_dir = tmp_path / "outputs" / "runs" / runner.run_id
        assert outputs_dir.exists()

        search_dir = outputs_dir / "search"
        if search_dir.exists():
            for f in search_dir.rglob("*"):
                if f.is_file():
                    content = f.read_text(encoding="utf-8")
                    assert MOCK_PAPER_TITLE not in content, f"Mock paper title found in {f}"
                    assert MOCK_PAPER_DOI not in content, f"Mock paper DOI found in {f}"

    def test_fail_status_no_mock_written(self, tmp_path):
        """When adapter returns status=fail (caught exception), run_action
        raises ValueError — no mock data is written."""
        adapter = _CaughtFailAdapter()
        runner = FilesystemActionRunner(
            repo_path=tmp_path,
            skill_adapters={"literature_search": adapter},
            run_id="test-run",
        )
        runner.run_action("init", {})

        with pytest.raises(ValueError, match="Simulated provider failure"):
            runner.run_action("search", {"query": "cancer immunotherapy"})

        outputs_dir = tmp_path / "outputs" / "runs" / "test-run"
        search_dir = outputs_dir / "search"

        raw_results = search_dir / "raw_results.json"
        assert not raw_results.exists(), (
            "raw_results.json must NOT exist when adapter returns fail status"
        )

    def test_real_adapter_provider_runtime_error(self, tmp_path):
        """Test with the REAL LiteratureSearchAdapter but a provider that
        raises RuntimeError. Verifies the exception propagates all the way
        through — no silent mock fallback."""
        from skills.local.adapters import LiteratureSearchAdapter

        real_adapter = LiteratureSearchAdapter()
        runner = FilesystemActionRunner(
            repo_path=tmp_path,
            skill_adapters={"literature_search": real_adapter},
            run_id="test-run",
        )
        runner.run_action("init", {})

        with patch("harness.ports.paper_search_provider.create_search_provider") as mock_create:
            mock_provider = MagicMock()
            mock_provider.search.side_effect = RuntimeError(
                "MCP server unreachable — simulated crash"
            )
            mock_create.return_value = mock_provider

            with pytest.raises(RuntimeError, match="MCP server unreachable"):
                runner.run_action("search", {"query": "cancer immunotherapy"})

        search_dir = tmp_path / "outputs" / "runs" / "test-run" / "search"
        if search_dir.exists():
            for f in search_dir.rglob("*"):
                if f.is_file():
                    content = f.read_text(encoding="utf-8")
                    assert MOCK_PAPER_TITLE not in content
                    assert MOCK_PAPER_DOI not in content


class TestMockPathOnlyWithoutAdapters:
    """Mock data IS written when runner has no adapters — but only then."""

    def test_no_adapters_writes_mock_data(self, tmp_path):
        """When FilesystemActionRunner is built without skill_adapters,
        the mock fallback path at lines 225-234 executes."""
        runner = FilesystemActionRunner(
            repo_path=tmp_path,
            skill_adapters=None,
            run_id="test-run",
        )
        runner.run_action("init", {})

        _artifacts = runner.run_action("search", {"query": "test query"})

        # Search generates a fresh run_id, use runner.run_id
        outputs_dir = tmp_path / "outputs" / "runs" / runner.run_id
        raw_results = outputs_dir / "search" / "raw_results.json"
        assert raw_results.exists(), "Mock raw_results.json must be written"

        content = json.loads(raw_results.read_text(encoding="utf-8"))
        assert len(content) == 1
        assert content[0]["title"] == MOCK_PAPER_TITLE
        assert content[0]["doi"] == MOCK_PAPER_DOI

        assert any("raw_results.json" in a for a in _artifacts)

    def test_empty_dict_writes_mock_data(self, tmp_path):
        """Even with an empty dict (not None), no adapter is found."""
        runner = FilesystemActionRunner(
            repo_path=tmp_path,
            skill_adapters={},
            run_id="test-run",
        )
        runner.run_action("init", {})

        runner.run_action("search", {"query": "test"})

        raw_results = tmp_path / "outputs" / "runs" / runner.run_id / "search" / "raw_results.json"
        assert raw_results.exists()
        content = json.loads(raw_results.read_text(encoding="utf-8"))
        assert content[0]["title"] == MOCK_PAPER_TITLE

    def test_mock_data_only_in_run_dir_not_root(self, tmp_path):
        """Mock data is written under outputs/runs/{run_id}/, NOT directly
        under outputs/ or the repo root."""
        runner = FilesystemActionRunner(
            repo_path=tmp_path,
            skill_adapters=None,
            run_id="test-run",
        )
        runner.run_action("init", {})
        runner.run_action("search", {"query": "test"})

        assert not (tmp_path / "raw_results.json").exists()
        assert not (tmp_path / "outputs" / "raw_results.json").exists()
        # Search generates a fresh run_id
        assert (tmp_path / "outputs" / "runs" / runner.run_id / "search" / "raw_results.json").exists()


class TestOrchestratorBuilderAlwaysWiresAdapters:
    """build_orchestrator_dependencies() must always provide adapters."""

    def test_default_build_has_literature_search(self, tmp_path):
        """When called without explicit skill_adapters, builder creates
        LiteratureSearchAdapter + AcademicWriterAdapter by default."""
        deps = build_orchestrator_dependencies(project_root=tmp_path)
        assert "literature_search" in deps.skill_adapters
        assert "academic_writer" in deps.skill_adapters

    def test_action_runner_has_adapters(self, tmp_path):
        """The action_runner produced by the builder has adapters wired."""
        deps = build_orchestrator_dependencies(project_root=tmp_path)
        runner = deps.action_runner
        assert isinstance(runner, FilesystemActionRunner)
        assert "literature_search" in runner._skill_adapters

    def test_explicit_adapters_preserved(self, tmp_path):
        """When explicit skill_adapters are provided, they are used."""
        custom = _CaughtFailAdapter()
        deps = build_orchestrator_dependencies(
            project_root=tmp_path,
            skill_adapters={"literature_search": custom},
        )
        assert deps.skill_adapters["literature_search"] is custom

    def test_explicit_empty_dict_no_adapter(self, tmp_path):
        """Edge case: caller CAN pass empty dict, which means no adapters.
        This is the ONLY way production code would hit the mock path."""
        deps = build_orchestrator_dependencies(
            project_root=tmp_path,
            skill_adapters={},
        )
        assert "literature_search" not in deps.skill_adapters
        runner = deps.action_runner
        assert "literature_search" not in runner._skill_adapters
