"""End-to-end test for search → chain → screen pipeline.

Validates that the chaining feature integrates with the full pipeline:
  1. paper search --raw-papers seeds.json  → raw_results.json (scored)
  2. paper chain                            → raw_results.json (expanded)
  3. paper screen                           → screened_evidence.json

Uses cached API responses for determinism.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.services.orchestrator import Orchestrator, OrchestratorRequest
from harness.services.orchestrator_builder import build_orchestrator_dependencies


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal project directory with seed papers."""
    (tmp_path / "templates").mkdir()
    (tmp_path / "outputs").mkdir()
    (tmp_path / "templates/references.bib").write_text("% empty bib\n")

    seeds = [
        {
            "title": "EvoR: Evolving Retrieval for Code Generation",
            "doi": "10.18653/v1/2024.findings-emnlp.143",
            "year": 2024,
            "authors": "Su et al.",
            "abstract": "Retrieval-augmented code generation with evolutionary optimization.",
        },
        {
            "title": "RepoCoder: Repository-Level Code Completion",
            "doi": "10.18653/v1/2023.emnlp-main.151",
            "year": 2023,
            "authors": "Zhang et al.",
            "abstract": "Iterative retrieval-augmented code completion at repository level.",
        },
        {
            "title": "CodeRAG-Bench: Can Retrieval Augment Code Generation?",
            "doi": "10.48550/arXiv.2406.14497",
            "year": 2024,
            "authors": "Wang et al.",
            "abstract": "Benchmark for evaluating retrieval-augmented code generation.",
        },
    ]
    seeds_path = tmp_path / "seeds.json"
    seeds_path.write_text(json.dumps(seeds, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def _make_orchestrator(project_dir: Path) -> Orchestrator:
    """Build orchestrator with real adapters for E2E testing."""
    deps = build_orchestrator_dependencies(project_root=project_dir)
    return Orchestrator(
        deps.repo_path,
        deps.state_manager,
        deps.checker,
        deps.action_runner,
        dict(deps.wrappers),
    )


def _request(command: str, args: dict[str, object] | None = None) -> OrchestratorRequest:
    """Create an OrchestratorRequest with sensible defaults."""
    return OrchestratorRequest(
        command=command,
        requested_stage="rendered",
        failure_policy="stop_on_error",
        args=args or {},
    )


def test_search_chain_screen_pipeline(project_dir: Path) -> None:
    """Full pipeline: search → chain → screen produces expanded, scored, screened results."""
    orch = _make_orchestrator(project_dir)

    # Step 0: Init (required for state)
    init_result = orch.execute(_request("init"))
    assert init_result.success, f"Init failed: {init_result.blockers}"

    # Step 1: Search with seed papers
    search_result = orch.execute(
        _request(
            "search",
            {
                "query": "retrieval augmented code generation",
                "raw_papers": str(project_dir / "seeds.json"),
            },
        )
    )
    assert search_result.success, f"Search failed: {search_result.blockers}"

    raw_results_path = project_dir / "outputs/latest/search/raw_results.json"
    assert raw_results_path.exists(), "raw_results.json not created"
    raw_data = json.loads(raw_results_path.read_text(encoding="utf-8"))
    initial_count = len(raw_data.get("papers", []))
    assert initial_count >= 3, f"Expected >=3 papers after search, got {initial_count}"

    # Step 2: Chain — expand corpus (mocked for determinism)
    mock_chain_result = {
        "papers": raw_data["papers"]
        + [
            {
                "title": "Retrieval-Augmented Generation for Code: A Survey",
                "doi": "10.1145/survey2025",
                "year": 2025,
                "authors": "Test Author",
                "abstract": "Survey on retrieval-augmented code generation techniques.",
                "source": "backward_chaining",
                "s2_id": "mock_s2_1",
            },
            {
                "title": "Neural Code Generation with Context Retrieval",
                "doi": "10.1145/code2025",
                "year": 2025,
                "authors": "Test Author 2",
                "abstract": "Neural approaches to code generation using context retrieval.",
                "source": "forward_chaining",
                "s2_id": "mock_s2_2",
            },
        ],
        "provenance": [
            {"paper_id": "mock_s2_1", "round": 1, "source": "backward", "chain_from": "seed"},
            {"paper_id": "mock_s2_2", "round": 1, "source": "forward", "chain_from": "seed"},
        ],
        "stats": {
            "rounds_completed": 1,
            "total_api_calls": 2,
            "papers_by_round": {0: 3, 1: 2},
            "saturation": False,
        },
        "total_unique": 5,
    }

    with patch(
        "skills.imported.literature_search.chaining.iterative_search",
        return_value=mock_chain_result,
    ):
        chain_result = orch.execute(
            _request(
                "chain",
                {
                    "query": "retrieval augmented code generation",
                    "max_rounds": 1,
                    "max_papers": 50,
                    "relevance_threshold": 0.25,
                },
            )
        )
    assert chain_result.success, f"Chain failed: {chain_result.blockers}"

    # Verify expanded raw_results
    raw_data_after = json.loads(raw_results_path.read_text(encoding="utf-8"))
    expanded_count = len(raw_data_after.get("papers", []))
    assert expanded_count >= 5, f"Expected >=5 papers after chain, got {expanded_count}"

    # Verify provenance was written
    provenance_path = project_dir / "outputs/latest/search/chain_provenance.json"
    assert provenance_path.exists(), "chain_provenance.json not created"

    # Step 3: Screen
    screen_result = orch.execute(_request("screen"))
    assert screen_result.success, f"Screen failed: {screen_result.blockers}"

    evidence_path = project_dir / "outputs/latest/search/screened_evidence.json"
    assert evidence_path.exists(), "screened_evidence.json not created"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["total_raw"] >= 5, f"Expected >=5 raw, got {evidence['total_raw']}"
    assert evidence["total_screened"] >= 0


def test_chain_without_search_fails(project_dir: Path) -> None:
    """Chain command should fail if no raw_results.json exists."""
    orch = _make_orchestrator(project_dir)

    # Init first (needed for stage), then try chain without search
    orch.execute(_request("init"))

    result = orch.execute(_request("chain", {"query": "test"}))
    # Should fail: stage check or file missing
    assert not result.success, "Expected chain to fail without search"


def test_cli_chain_command_help() -> None:
    """Verify chain subcommand is registered in CLI."""
    import subprocess

    result = subprocess.run(
        [".venv/bin/python", "-m", "cli.paper.main", "chain", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"chain --help failed: {result.stderr}"
    assert "--max-rounds" in result.stdout
    assert "--max-papers" in result.stdout
    assert "--relevance-threshold" in result.stdout
    assert "--no-cache" in result.stdout
