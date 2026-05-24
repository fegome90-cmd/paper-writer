import sys
from pathlib import Path
from typing import Any

import pytest

from cli.paper.main import main

# Minimal valid BibTeX entry for testing
MINIMAL_BIB = """@article{smith2024voice,
  title = {Voice Disorders in Adolescent Singers},
  author = {Smith, Jane and Doe, John},
  year = {2024},
  journal = {Journal of Voice},
  doi = {10.1000/example2024}
}
"""

MINIMAL_SECTION = """# {section}

See @smith2024voice for background.

## Key findings

The prevalence was 42.3% in the study cohort.
"""


def _write_test_content(tmp_path: Path) -> None:
    """Populate test fixtures with content that passes real validators."""
    # Write a valid bib file
    bib_file = tmp_path / "templates" / "references.bib"
    bib_file.write_text(MINIMAL_BIB, encoding="utf-8")


def _write_section(tmp_path: Path, section: str) -> None:
    """Write a section file with content that references the bib key."""
    section_file = tmp_path / "outputs" / "drafts" / f"{section}.md"
    content = MINIMAL_SECTION.replace("{section}", section.capitalize())
    section_file.write_text(content, encoding="utf-8")


def test_cli_full_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    # 1. Init
    monkeypatch.setattr(sys, "argv", ["paper", "init"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: load_state" in captured.out
    assert "Success: Stage progressed" in captured.out
    assert (tmp_path / "outputs" / "state.yaml").is_file()
    assert (tmp_path / "templates" / "manuscript.qmd").is_file()

    # Populate bib with valid content (init creates empty, tests need real data)
    _write_test_content(tmp_path)

    # 2. Search
    monkeypatch.setattr(sys, "argv", ["paper", "search"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: verify_gate_search_completed" in captured.out

    # 3. Screen
    monkeypatch.setattr(sys, "argv", ["paper", "screen"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: verify_gate_screened_evidence" in captured.out

    # 4. Draft outline
    monkeypatch.setattr(sys, "argv", ["paper", "draft", "outline"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: verify_gate_outline_drafted" in captured.out

    # 5. Draft sections — rewrite with real content after mock creation
    for sec in ["introduction", "methods", "results", "discussion"]:
        monkeypatch.setattr(sys, "argv", ["paper", "draft", "section", sec])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        # Overwrite mock content with real content referencing bib keys
        _write_section(tmp_path, sec)

    captured = capsys.readouterr()

    # 6. Run validations with real wrappers
    monkeypatch.setattr(sys, "argv", ["paper", "lint", "bib"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    monkeypatch.setattr(sys, "argv", ["paper", "check", "refs"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    monkeypatch.setattr(sys, "argv", ["paper", "lint", "style"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    monkeypatch.setattr(sys, "argv", ["paper", "audit", "reporting"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    # Should have transitioned to rendering
    assert "to 'rendering'" in captured.out

    # 7. Render
    monkeypatch.setattr(sys, "argv", ["paper", "render"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "to 'verified'" in captured.out

    # 8. Verify
    monkeypatch.setattr(sys, "argv", ["paper", "verify"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ready_for_delivery" in captured.out
    assert (tmp_path / "outputs" / "manifest.yaml").is_file()


def test_cli_init_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Init must not set any gate True if the scaffold action fails.

    Uses a deterministic mock: patches FilesystemActionRunner.run_action to raise,
    then verifies that the persisted state still has all gates False.
    """
    monkeypatch.chdir(tmp_path)

    from harness.adapters.filesystem_action_runner import FilesystemActionRunner

    original_run = FilesystemActionRunner.run_action

    def _failing_run(self: FilesystemActionRunner, command: str, args: dict[str, Any]) -> list[str]:
        if command == "init":
            raise OSError("Simulated scaffold failure: disk full")
        return original_run(self, command, args)

    monkeypatch.setattr(FilesystemActionRunner, "run_action", _failing_run)

    monkeypatch.setattr(sys, "argv", ["paper", "init"])
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Init must fail
    assert exc_info.value.code != 0, "Init must report failure when scaffold fails"

    # State file may or may not exist (bootstrap happens before action).
    # The KEY invariant: if state file exists, NO gate may be True.
    state_file = tmp_path / "outputs" / "state.yaml"
    if state_file.exists():
        import yaml

        state = yaml.safe_load(state_file.read_text())
        gates = state.get("gates", {})
        true_gates = [k for k, v in gates.items() if v is True]
        assert true_gates == [], (
            f"No gate should be True after failed init, but found: {true_gates}"
        )
