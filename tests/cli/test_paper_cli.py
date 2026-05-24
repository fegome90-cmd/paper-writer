import sys
from pathlib import Path

import pytest

from cli.paper.main import main


def test_cli_full_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Set CWD to tmp_path so it runs isolated
    monkeypatch.chdir(tmp_path)

    # 1. Run 'paper init'
    monkeypatch.setattr(sys, "argv", ["paper", "init"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: load_state" in captured.out
    assert "[ok] Step: validate_preconditions" in captured.out
    assert "[ok] Step: run_core_action" in captured.out
    assert "Success: Stage progressed" in captured.out

    # Check created files
    assert (tmp_path / "outputs" / "state.yaml").is_file()
    assert (tmp_path / "templates" / "manuscript.qmd").is_file()

    # 2. Run 'paper search'
    monkeypatch.setattr(sys, "argv", ["paper", "search"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: verify_gate_search_completed" in captured.out

    # 3. Run 'paper screen'
    monkeypatch.setattr(sys, "argv", ["paper", "screen"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: verify_gate_screened_evidence" in captured.out

    # 4. Run 'paper draft outline'
    monkeypatch.setattr(sys, "argv", ["paper", "draft", "outline"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: verify_gate_outline_drafted" in captured.out

    # 5. Run 'paper draft section introduction'
    for sec in ["introduction", "methods", "results", "discussion"]:
        monkeypatch.setattr(sys, "argv", ["paper", "draft", "section", sec])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "verify_gate_sections_completed" in captured.out

    # 6. Run validations
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
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    # Should have transitioned to rendering
    assert "to 'rendering'" in captured.out

    # 7. Run 'paper render'
    monkeypatch.setattr(sys, "argv", ["paper", "render"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "to 'verified'" in captured.out

    # 8. Run 'paper verify'
    monkeypatch.setattr(sys, "argv", ["paper", "verify"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ready_for_delivery" in captured.out

    assert (tmp_path / "outputs" / "manifest.yaml").is_file()
