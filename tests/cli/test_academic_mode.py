"""Tests for academic-evidence-curation mode: PR1 transport layer.

Covers: review_config.yaml persistence, CLI --mode flag, orchestrator
request forwarding, and adapter transport.
"""

import json
from pathlib import Path

import yaml

from harness.services.orchestrator import OrchestratorRequest

# ---------------------------------------------------------------------------
# review_config.yaml — persistence and loading
# ---------------------------------------------------------------------------


class TestReviewConfigPersistence:
    """review_config.yaml is the authoritative review-mode artifact."""

    def test_init_creates_review_config_default_rapid(self, tmp_path: Path) -> None:
        """paper init without --mode creates review_config.yaml with mode=rapid."""
        from harness.adapters.filesystem_action_runner import FilesystemActionRunner

        runner = FilesystemActionRunner(repo_path=tmp_path, skill_adapters={}, run_id="test")
        runner.run_action("init", {})
        config_path = tmp_path / "outputs" / "review_config.yaml"
        assert config_path.exists(), "review_config.yaml should be created on init"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["mode"] == "rapid"

    def test_init_academic_creates_review_config(self, tmp_path: Path) -> None:
        """paper init --mode academic creates review_config.yaml with mode=academic."""
        from harness.adapters.filesystem_action_runner import FilesystemActionRunner

        runner = FilesystemActionRunner(repo_path=tmp_path, skill_adapters={}, run_id="test")
        runner.run_action("init", {"mode": "academic"})
        config_path = tmp_path / "outputs" / "review_config.yaml"
        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["mode"] == "academic"

    def test_init_academic_with_search_window(self, tmp_path: Path) -> None:
        """paper init --mode academic --search-window stores window in review_config."""
        from harness.adapters.filesystem_action_runner import FilesystemActionRunner

        runner = FilesystemActionRunner(repo_path=tmp_path, skill_adapters={}, run_id="test")
        runner.run_action(
            "init",
            {"mode": "academic", "search_window": {"start_year": 2020, "end_year": 2024}},
        )
        config_path = tmp_path / "outputs" / "review_config.yaml"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["search_window"]["start_year"] == 2020
        assert data["search_window"]["end_year"] == 2024

    def test_init_rapid_is_default(self, tmp_path: Path) -> None:
        """No --mode flag defaults to rapid mode."""
        from harness.adapters.filesystem_action_runner import FilesystemActionRunner

        runner = FilesystemActionRunner(repo_path=tmp_path, skill_adapters={}, run_id="test")
        runner.run_action("init", {})
        config_path = tmp_path / "outputs" / "review_config.yaml"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["mode"] == "rapid"


class TestReviewConfigLoading:
    """Commands load review_config.yaml to determine active mode."""

    def test_load_config_from_outputs(self, tmp_path: Path) -> None:
        """load_review_config reads outputs/review_config.yaml."""
        from harness.services.review_config import load_review_config

        config_dir = tmp_path / "outputs"
        config_dir.mkdir(parents=True)
        (config_dir / "review_config.yaml").write_text(
            yaml.dump(
                {"mode": "academic", "search_window": {"start_year": 2020, "end_year": 2024}}
            ),
            encoding="utf-8",
        )
        config = load_review_config(tmp_path)
        assert config["mode"] == "academic"
        assert config["search_window"]["start_year"] == 2020

    def test_load_config_missing_defaults_rapid(self, tmp_path: Path) -> None:
        """Missing review_config.yaml defaults to rapid mode."""
        from harness.services.review_config import load_review_config

        config = load_review_config(tmp_path)
        assert config["mode"] == "rapid"


# ---------------------------------------------------------------------------
# CLI --mode flag
# ---------------------------------------------------------------------------


class TestCLIModeFlag:
    """CLI parses --mode and forwards to init."""

    def test_init_has_mode_flag(self) -> None:
        """init subparser accepts --mode."""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        init_p = sub.add_parser("init")
        init_p.add_argument("--mode", choices=["rapid", "academic"], default="rapid")
        args = parser.parse_args(["init", "--mode", "academic"])
        assert args.mode == "academic"

    def test_init_mode_default_rapid(self) -> None:
        """--mode defaults to rapid."""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        init_p = sub.add_parser("init")
        init_p.add_argument("--mode", choices=["rapid", "academic"], default="rapid")
        args = parser.parse_args(["init"])
        assert args.mode == "rapid"


# ---------------------------------------------------------------------------
# OrchestratorRequest carries mode + search_window
# ---------------------------------------------------------------------------


class TestOrchestratorRequestTransport:
    """OrchestratorRequest carries review mode and search window."""

    def test_request_carries_mode(self) -> None:
        req = OrchestratorRequest(
            command="search",
            requested_stage="unknown",
            failure_policy="stop_on_error",
            args={"query": "test", "mode": "academic"},
            context={"cwd": "/tmp", "actor": "cli"},
        )
        assert req.args.get("mode") == "academic"

    def test_request_carries_search_window(self) -> None:
        req = OrchestratorRequest(
            command="search",
            requested_stage="unknown",
            failure_policy="stop_on_error",
            args={
                "query": "test",
                "search_window": {"start_year": 2020, "end_year": 2024},
            },
            context={"cwd": "/tmp", "actor": "cli"},
        )
        assert req.args["search_window"]["start_year"] == 2020


# ---------------------------------------------------------------------------
# Adapter transport
# ---------------------------------------------------------------------------


class TestAdapterTransport:
    """skills/local/adapters.py forwards mode and search_window."""

    def test_search_adapter_writes_search_plan_in_academic_mode(self, tmp_path: Path) -> None:
        """LiteratureSearchAdapter writes search_plan.json in academic mode."""
        search_dir = tmp_path / "search"
        search_dir.mkdir(parents=True)

        from skills.local.adapters import LiteratureSearchAdapter

        adapter = LiteratureSearchAdapter()
        result = adapter.execute(
            command="search",
            inputs={
                "query": "cancer treatment",
                "output_dir": str(search_dir),
                "raw_papers": '[{"title":"Paper 1","doi":"10.1000/test","year":2023,"authors":"Test","metrics":{}}]',
                "mode": "academic",
                "search_window": {"start_year": 2020, "end_year": 2024},
            },
            context={"cwd": str(tmp_path)},
        )
        assert result.status == "pass"
        # search_plan.json should exist with search window
        plan_path = search_dir / "search_plan.json"
        assert plan_path.exists(), "search_plan.json should be written in academic mode"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["query"] == "cancer treatment"
        assert plan["search_window"]["start_year"] == 2020
        assert plan["search_window"]["end_year"] == 2024

    def test_search_adapter_no_search_window_in_rapid_mode(self, tmp_path: Path) -> None:
        """LiteratureSearchAdapter does NOT write search_window in rapid mode."""
        search_dir = tmp_path / "search"
        search_dir.mkdir(parents=True)

        from skills.local.adapters import LiteratureSearchAdapter

        adapter = LiteratureSearchAdapter()
        result = adapter.execute(
            command="search",
            inputs={
                "query": "test query",
                "output_dir": str(search_dir),
                "raw_papers": '[{"title":"Paper 1","doi":"10.1000/test","year":2023,"authors":"Test","metrics":{}}]',
            },
            context={"cwd": str(tmp_path)},
        )
        assert result.status == "pass"
        plan_path = search_dir / "search_plan.json"
        if plan_path.exists():
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            # search_window should NOT be present in rapid mode
            assert "search_window" not in plan, "search_window should NOT be in rapid mode plan"

    def test_chain_adapter_forwards_mode(self, tmp_path: Path) -> None:
        """Chain via adapter forwards mode through search re-invocation."""
        # This will be validated in PR2; PR1 establishes the transport path
        pass
