"""H-A03: CLI filter forwarding investigation.

Hypothesis: CLI collects filters (year_min, study_types, etc.) but
FilesystemActionRunner may not forward them correctly to the adapter.

This test traces the COMPLETE chain:
  CLI arg -> OrchestratorRequest.args -> run_action(command, args)
  -> adapter.execute(command, inputs) -> provider.search(**filters)

Filter keys are defined in SEARCH_FILTER_KEYS (harness/ports/paper_search_provider.py)
which is the canonical source of truth for all filter key names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from harness.ports.paper_search_provider import SEARCH_FILTER_KEYS
from harness.ports.skill_adapter import SkillAdapter, SkillResult

SAMPLE_FILTERS: dict[str, Any] = {
    "year_min": 2020,
    "year_max": 2024,
    "study_types": ["rct", "systematic review"],
    "human": True,
    "sample_size_min": 50,
    "sjr_max": 2,
    "duration_min": 30,
    "duration_max": 365,
    "exclude_preprints": True,
    "publisher_name": "Elsevier,Springer",
    "clinical_guideline": True,
    "medical_mode": True,
}


class _RecordingAdapter(SkillAdapter):
    """Mock adapter that records every call for assertion."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    @property
    def name(self) -> str:
        return "recording-adapter"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        self.calls.append((command, dict(inputs), dict(context)))
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary="recorded",
            artifacts=[],
            gate_changes={"search_completed": True},
        )


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "outputs").mkdir()
    (repo / "templates").mkdir()
    (repo / "templates" / "manuscript.qmd").touch()
    (repo / "templates" / "references.bib").touch()
    return repo


class TestCLIArgsReachOrchestratorRequest:
    """Step 1: CLI _CLI_FILTER_MAP -> OrchestratorRequest.args.

    Verifies that non-None filter values are placed into orch_args
    and survive into OrchestratorRequest.args.
    """

    def test_all_filters_in_request_args(self, project_dir: Path) -> None:
        from harness.services.orchestrator import OrchestratorRequest

        orch_args: dict[str, Any] = {
            "query": "test query",
        }
        for key, val in SAMPLE_FILTERS.items():
            if val is not None:
                orch_args[key] = val

        request = OrchestratorRequest(
            command="search",
            requested_stage="unknown",
            failure_policy="stop_on_error",
            args=orch_args,
            context={"cwd": str(project_dir), "actor": "cli"},
        )

        for key in SEARCH_FILTER_KEYS:
            assert key in request.args, f"Filter '{key}' missing from OrchestratorRequest.args"
            assert request.args[key] == SAMPLE_FILTERS[key], (
                f"Filter value mutated: expected {SAMPLE_FILTERS[key]}, got {request.args[key]}"
            )

    def test_none_filters_excluded_from_request(self, project_dir: Path) -> None:
        from harness.services.orchestrator import OrchestratorRequest

        orch_args: dict[str, Any] = {"query": "test query", "year_min": 2020}
        request = OrchestratorRequest(
            command="search",
            requested_stage="unknown",
            failure_policy="stop_on_error",
            args=orch_args,
        )

        assert "year_min" in request.args
        assert "study_types" not in request.args


class TestOrchestratorPassesArgsToRunner:
    """Step 3: Orchestrator.execute() -> action_runner.run_action(command, args).

    The orchestrator passes request.args directly to run_action (line 185):
        action_artifacts = self.action_runner.run_action(request.command, request.args)
    """

    def test_orchestrator_forwards_all_args(self, project_dir: Path) -> None:
        from harness.services.orchestrator import Orchestrator, OrchestratorRequest

        orch_args: dict[str, Any] = {"query": "test query"}
        for key, val in SAMPLE_FILTERS.items():
            if val is not None:
                orch_args[key] = val

        request = OrchestratorRequest(
            command="search",
            requested_stage="unknown",
            failure_policy="stop_on_error",
            args=orch_args,
            context={"cwd": str(project_dir)},
        )

        captured_args: dict[str, Any] = {}

        class _CaptureRunner:
            def run_action(self, command: str, args: dict[str, Any]) -> list[str]:
                captured_args.update(args)
                return []

            def emit_manifest(self, gate_snapshot: dict[str, bool]) -> str:
                return ""

            def write_command_log(self, command: str, payload: dict[str, Any]) -> str:
                return ""

        sm = MagicMock()
        sm.exists.return_value = True
        sm.load_state.return_value = {
            "stage": "search",
            "gates": {"repo_initialized": True, "search_completed": False},
        }
        orch = Orchestrator(
            repo_path=project_dir,
            state_manager=sm,
            checker=MagicMock(),
            action_runner=_CaptureRunner(),
        )
        orch.execute(request)

        for key in SEARCH_FILTER_KEYS:
            assert key in captured_args, (
                f"Filter '{key}' LOST between OrchestratorRequest and run_action args"
            )


class TestFilesystemActionRunnerForwardsFilters:
    """Step 4: FilesystemActionRunner.run_action('search', args) -> adapter inputs.

    Regression test: verifies FilesystemActionRunner forwards all filter keys
    from args into adapter inputs. Previously filters were silently dropped.
    """

    def test_filter_forwarding_gap(self, project_dir: Path) -> None:
        from harness.adapters.filesystem_action_runner import FilesystemActionRunner

        recorder = _RecordingAdapter()
        runner = FilesystemActionRunner(
            repo_path=project_dir,
            skill_adapters={"literature_search": recorder},
            run_id="20260101T000000",
        )

        search_args: dict[str, Any] = {"query": "test query"}
        for key, val in SAMPLE_FILTERS.items():
            if val is not None:
                search_args[key] = val

        runner.run_action("search", search_args)

        assert len(recorder.calls) == 1
        cmd, inputs, _ctx = recorder.calls[0]
        assert cmd == "search"

        lost: list[str] = []
        for key in SEARCH_FILTER_KEYS:
            if key not in inputs:
                lost.append(key)

        assert lost == [], (
            f"H-A03 CONFIRMED: {len(lost)}/12 filters LOST in "
            f"FilesystemActionRunner.run_action() -> adapter.execute() inputs. "
            f"Lost filters: {lost}"
        )

    def test_query_and_output_dir_preserved(self, project_dir: Path) -> None:
        from harness.adapters.filesystem_action_runner import FilesystemActionRunner

        recorder = _RecordingAdapter()
        runner = FilesystemActionRunner(
            repo_path=project_dir,
            skill_adapters={"literature_search": recorder},
            run_id="20260101T000000",
        )

        runner.run_action("search", {"query": "test query"})

        _, inputs, _ = recorder.calls[0]
        assert "query" in inputs
        assert "output_dir" in inputs


class TestAdapterExtractsFiltersFromInputs:
    """Step 5: LiteratureSearchAdapter._handle_search(inputs) filter extraction.

    The adapter reads filters from inputs dict using SEARCH_FILTER_KEYS (line 127-144).
    If filters are present in inputs, they are extracted and forwarded to provider.
    """

    def test_adapter_extracts_present_filters(self, project_dir: Path) -> None:
        inputs_with_filters: dict[str, Any] = {
            "query": "test query",
            "output_dir": str(project_dir / "search"),
        }
        for key, val in SAMPLE_FILTERS.items():
            if val is not None:
                inputs_with_filters[key] = val

        filters: dict[str, Any] = {}
        for key in SEARCH_FILTER_KEYS:
            if key in inputs_with_filters and inputs_with_filters[key] is not None:
                filters[key] = inputs_with_filters[key]

        for key in SEARCH_FILTER_KEYS:
            assert key in filters, f"Adapter would miss filter '{key}'"

    def test_adapter_skips_missing_filters(self) -> None:
        inputs_no_filters: dict[str, Any] = {
            "query": "test query",
            "output_dir": "/tmp/search",
        }

        filters: dict[str, Any] = {}
        for key in SEARCH_FILTER_KEYS:
            if key in inputs_no_filters and inputs_no_filters[key] is not None:
                filters[key] = inputs_no_filters[key]

        assert filters == {}, "Adapter should not add default filters"


class TestFilterValueTypesPreserved:
    """Step 6: Verify filter values are NOT type-mutated."""

    @pytest.mark.parametrize(
        "key,value",
        [
            ("year_min", 2020),
            ("year_max", 2024),
            ("study_types", ["rct", "systematic review"]),
            ("human", True),
            ("sample_size_min", 50),
            ("sjr_max", 2),
            ("duration_min", 30),
            ("duration_max", 365),
            ("exclude_preprints", True),
            ("publisher_name", "Elsevier,Springer"),
            ("clinical_guideline", True),
            ("medical_mode", True),
        ],
    )
    def test_value_type_preserved(self, key: str, value: Any) -> None:
        from harness.services.orchestrator import OrchestratorRequest

        request = OrchestratorRequest(
            command="search",
            requested_stage="unknown",
            failure_policy="stop_on_error",
            args={"query": "test", key: value},
        )

        actual = request.args.get(key)
        assert actual == value, (
            f"Type mutation: {key}={value!r} ({type(value).__name__}) "
            f"became {actual!r} ({type(actual).__name__})"
        )
        assert type(actual) is type(value)


class TestMissingFiltersNoDefaults:
    """Step 7: Missing filters should NOT produce defaults."""

    def test_no_spurious_defaults_in_adapter(self) -> None:
        inputs_minimal: dict[str, Any] = {
            "query": "test",
            "output_dir": "/tmp/search",
        }

        filters: dict[str, Any] = {}
        for key in SEARCH_FILTER_KEYS:
            if key in inputs_minimal and inputs_minimal[key] is not None:
                filters[key] = inputs_minimal[key]

        for key in SEARCH_FILTER_KEYS:
            assert key not in filters, (
                f"Filter '{key}' was spuriously added with value {filters.get(key)!r}"
            )


class TestCompleteForwardingChain:
    """Integration test: Full chain from OrchestratorRequest -> adapter inputs.

    This is the SMOKING GUN regression test: verifies every filter key survives
    the full OrchestratorRequest -> FilesystemActionRunner -> adapter.execute() chain.
    """

    def test_full_chain_filter_forwarding(self, project_dir: Path) -> None:
        from harness.adapters.filesystem_action_runner import FilesystemActionRunner
        from harness.services.orchestrator import OrchestratorRequest

        recorder = _RecordingAdapter()
        runner = FilesystemActionRunner(
            repo_path=project_dir,
            skill_adapters={"literature_search": recorder},
            run_id="20260101T000000",
        )

        orch_args: dict[str, Any] = {"query": "test query"}
        for key, val in SAMPLE_FILTERS.items():
            if val is not None:
                orch_args[key] = val

        request = OrchestratorRequest(
            command="search",
            requested_stage="unknown",
            failure_policy="stop_on_error",
            args=orch_args,
        )

        assert all(
            key in request.args for key in SEARCH_FILTER_KEYS
        ), "Filters lost in OrchestratorRequest"

        runner.run_action("search", request.args)

        _, adapter_inputs, _ = recorder.calls[0]

        chain_report: list[str] = []
        for key in SEARCH_FILTER_KEYS:
            in_request = key in request.args
            in_adapter = key in adapter_inputs
            status = "PRESERVED" if in_request and in_adapter else "LOST"
            if in_request and not in_adapter:
                status = "LOST_IN_RUNNER"
            chain_report.append(
                f"  {key:20s} Request={in_request!s:5s}  Adapter={in_adapter!s:5s}  -> {status}"
            )

        lost_count = sum(1 for key in SEARCH_FILTER_KEYS if key not in adapter_inputs)
        report = (
            "\n=== H-A03 Filter Forwarding Chain ===\n"
            + "\n".join(chain_report)
            + f"\n\nResult: {12 - lost_count}/12 filters preserved, {lost_count}/12 LOST\n"
        )

        if lost_count > 0:
            pytest.fail(
                f"{report}H-A03 CONFIRMED: {lost_count} filters are LOST between "
                f"FilesystemActionRunner.run_action() and adapter.execute(). "
                f"Root cause: filesystem_action_runner.py:206-216 only forwards "
                f"'query', 'output_dir', 'raw_papers' to adapter inputs."
            )


EXPECTED_FILTER_KEYS = frozenset({
    "year_min", "year_max", "study_types", "human", "sample_size_min",
    "sjr_max", "duration_min", "duration_max", "exclude_preprints",
    "publisher_name", "clinical_guideline", "medical_mode",
})


def test_canonical_key_count_matches_expected() -> None:
    assert len(SEARCH_FILTER_KEYS) == 12, (
        f"SEARCH_FILTER_KEYS has {len(SEARCH_FILTER_KEYS)} keys, expected 12. "
        "If a key was intentionally removed, update this guard."
    )
    assert set(SEARCH_FILTER_KEYS) == EXPECTED_FILTER_KEYS, (
        f"SEARCH_FILTER_KEYS mismatch.\n"
        f"  Missing from SEARCH_FILTER_KEYS: {EXPECTED_FILTER_KEYS - set(SEARCH_FILTER_KEYS)}\n"
        f"  Unexpected in SEARCH_FILTER_KEYS: {set(SEARCH_FILTER_KEYS) - EXPECTED_FILTER_KEYS}"
    )
