"""Tests for run lineage metadata (run.yaml, parent_run_id, status)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from harness.adapters.filesystem_action_runner import FilesystemActionRunner
from harness.ports.skill_adapter import SkillAdapter, SkillResult


class _MinimalSearchAdapter(SkillAdapter):
    """Writes minimal files so search/screen succeed in lineage tests."""

    @property
    def name(self) -> str:
        return "literature-search"

    def execute(
        self, command: str, inputs: dict, context: dict
    ) -> SkillResult:
        output_dir = inputs.get("output_dir", "")
        if command == "search":
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / "raw_results.json").write_text(
                json.dumps([{"title": "Test", "doi": "10.1/test"}])
            )
            (out / "search_plan.json").write_text(
                json.dumps({"query": inputs.get("query", "")})
            )
            return SkillResult(
                adapter=self.name, status="pass", summary="ok",
                artifacts=[str(out / "raw_results.json")], gate_changes={},
            )
        if command == "screen":
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / "screened_evidence.json").write_text(
                json.dumps({"evidence": [], "total_raw": 0, "total_screened": 0})
            )
            return SkillResult(
                adapter=self.name, status="pass", summary="ok",
                artifacts=[str(out / "screened_evidence.json")], gate_changes={},
            )
        return SkillResult(
            adapter=self.name, status="pass", summary="ok",
            artifacts=[], gate_changes={},
        )


def _runner_with_adapter(tmp_path: Path) -> FilesystemActionRunner:
    """Build runner with minimal search adapter for lineage tests."""
    return FilesystemActionRunner(
        tmp_path,
        skill_adapters={"literature_search": _MinimalSearchAdapter()},
    )


def _run_yaml(tmp_path: Path, run_id: str) -> dict:
    """Read run.yaml for a given run_id."""
    p = tmp_path / "outputs" / "runs" / run_id / "run.yaml"
    assert p.exists(), f"run.yaml missing for {run_id}"
    return yaml.safe_load(p.read_text())


def _complete(runner: FilesystemActionRunner, artifacts: list[str] | None = None) -> None:
    """Simulate orchestrator calling _mark_run_completed after run_action."""
    runner._mark_run_completed(artifacts or [])


class TestRunMetadata:
    """Every command produces run.yaml with metadata."""

    def test_init_creates_run_yaml(self, tmp_path: Path) -> None:
        runner = FilesystemActionRunner(tmp_path)
        runner.run_action("init", {})
        _complete(runner)

        meta = _run_yaml(tmp_path, runner.run_id)
        assert meta["command"] == "init"
        assert meta["status"] == "completed"
        assert "created_at" in meta
        assert "completed_at" in meta
        assert "parent_run_id" not in meta  # Init has no parent

    def test_init_records_artifacts(self, tmp_path: Path) -> None:
        runner = FilesystemActionRunner(tmp_path)
        artifacts = runner.run_action("init", {})
        _complete(runner, artifacts)

        meta = _run_yaml(tmp_path, runner.run_id)
        assert len(meta["artifacts"]) >= 3  # state.yaml, manuscript.qmd, references.bib

    def test_search_creates_run_yaml(self, tmp_path: Path) -> None:
        runner = FilesystemActionRunner(tmp_path)
        runner.run_action("init", {})
        _complete(runner)
        init_id = runner.run_id

        runner2 = _runner_with_adapter(tmp_path)
        runner2.run_action("search", {"query": "test"})
        _complete(runner2)

        meta = _run_yaml(tmp_path, runner2.run_id)
        assert meta["command"] == "search"
        assert meta["status"] == "completed"
        assert meta["parent_run_id"] == init_id

    def test_search_creates_new_run_not_overwrite(self, tmp_path: Path) -> None:
        runner = FilesystemActionRunner(tmp_path)
        runner.run_action("init", {})
        _complete(runner)
        init_id = runner.run_id

        runner2 = _runner_with_adapter(tmp_path)
        runner2.run_action("search", {"query": "first"})
        _complete(runner2)
        search1_id = runner2.run_id

        runner3 = _runner_with_adapter(tmp_path)
        runner3.run_action("search", {"query": "second"})
        _complete(runner3)
        search2_id = runner3.run_id

        # Both runs exist and are distinct
        assert search1_id != search2_id
        assert (tmp_path / "outputs" / "runs" / search1_id).exists()
        assert (tmp_path / "outputs" / "runs" / search2_id).exists()

        # First search is child of init, second search is child of first search
        # (because .run_id was updated to search1 after the first search)
        meta1 = _run_yaml(tmp_path, search1_id)
        meta2 = _run_yaml(tmp_path, search2_id)
        assert meta1["parent_run_id"] == init_id
        assert meta2["parent_run_id"] == search1_id  # Follows the active run

    def test_screen_does_not_overwrite_search_metadata(self, tmp_path: Path) -> None:
        runner = FilesystemActionRunner(tmp_path)
        runner.run_action("init", {})
        _complete(runner)

        runner2 = _runner_with_adapter(tmp_path)
        runner2.run_action("search", {"query": "test"})
        _complete(runner2)
        search_id = runner2.run_id

        runner3 = _runner_with_adapter(tmp_path)
        runner3.run_action("screen", {})
        _complete(runner3)

        # Screen reuses search run but doesn't overwrite command
        meta = _run_yaml(tmp_path, runner3.run_id)
        assert meta["command"] == "search"  # Not "screen"
        assert meta["status"] == "completed"

    def test_screen_appends_artifacts_to_search_run(self, tmp_path: Path) -> None:
        runner = FilesystemActionRunner(tmp_path)
        runner.run_action("init", {})
        _complete(runner)

        runner2 = _runner_with_adapter(tmp_path)
        runner2.run_action("search", {"query": "test"})
        _complete(runner2)
        search_id = runner2.run_id

        # Read artifacts after search
        meta_after_search = _run_yaml(tmp_path, search_id)
        search_artifact_count = len(meta_after_search["artifacts"])

        runner3 = _runner_with_adapter(tmp_path)
        screen_artifacts = runner3.run_action("screen", {})
        _complete(runner3, screen_artifacts)
        _complete(runner3)

        # Artifacts accumulated, not replaced
        meta_after_screen = _run_yaml(tmp_path, runner3.run_id)
        assert len(meta_after_screen["artifacts"]) > search_artifact_count

    def test_chain_has_parent_run_id(self, tmp_path: Path) -> None:
        runner = FilesystemActionRunner(tmp_path)
        runner.run_action("init", {})
        _complete(runner)
        init_id = runner.run_id

        runner2 = _runner_with_adapter(tmp_path)
        runner2.run_action("search", {"query": "test"})
        _complete(runner2)
        search_id = runner2.run_id

        runner3 = _runner_with_adapter(tmp_path)
        runner3.run_action("chain", {})
        _complete(runner3)

        meta = _run_yaml(tmp_path, runner3.run_id)
        assert meta["command"] == "chain"
        assert meta["parent_run_id"] == search_id


class TestRunImmutability:
    """Previous runs are never modified by subsequent commands."""

    def test_second_search_preserves_first(self, tmp_path: Path) -> None:
        runner = FilesystemActionRunner(tmp_path)
        runner.run_action("init", {})
        _complete(runner)

        runner2 = _runner_with_adapter(tmp_path)
        runner2.run_action("search", {"query": "first"})
        _complete(runner2)

        # Snapshot first search metadata
        meta1_before = _run_yaml(tmp_path, runner2.run_id)
        ts1 = meta1_before["completed_at"]

        runner3 = _runner_with_adapter(tmp_path)
        runner3.run_action("search", {"query": "second"})
        _complete(runner3)

        # First search metadata unchanged
        meta1_after = _run_yaml(tmp_path, meta1_before["run_id"])
        assert meta1_after["completed_at"] == ts1
        assert meta1_after["command"] == "search"
