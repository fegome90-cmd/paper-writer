from pathlib import Path

import yaml

from harness.adapters.filesystem_action_runner import FilesystemActionRunner


def test_write_command_log_persists_structured_yaml(tmp_path: Path) -> None:
    runner = FilesystemActionRunner(tmp_path)
    payload = {
        "command": "lint_bib",
        "wrapper": "bibtex-tidy",
        "gate": "bib_normalized",
        "status": "pass",
        "summary": "Bibliography normalized successfully.",
        "findings": [],
        "artifacts_checked": [str(tmp_path / "templates" / "references.bib")],
    }

    log_path = Path(runner.write_command_log("lint_bib", payload))

    assert log_path.exists()
    data = yaml.safe_load(log_path.read_text(encoding="utf-8"))
    assert data["command"] == "lint_bib"
    assert data["summary"] == "Bibliography normalized successfully."
