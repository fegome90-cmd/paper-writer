import datetime
from pathlib import Path
from typing import Any

import yaml

from harness.ports.action_runner import ActionRunner


class FilesystemActionRunner(ActionRunner):
    """Adapter implementing ActionRunner that executes actions on local filesystem."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    def run_action(self, command: str, args: dict[str, Any]) -> list[str]:
        artifacts: list[str] = []

        if command == "init":
            dirs = [
                "cli",
                "harness",
                "validators",
                "templates",
                "outputs",
                "tests",
                "outputs/search",
                "outputs/drafts",
                "outputs/render",
                "outputs/logs",
            ]
            for d in dirs:
                (self.repo_path / d).mkdir(parents=True, exist_ok=True)

            state_file = self.repo_path / "outputs" / "state.yaml"
            manuscript_qmd = self.repo_path / "templates" / "manuscript.qmd"
            manuscript_qmd.touch(exist_ok=True)

            references_bib = self.repo_path / "templates" / "references.bib"
            references_bib.touch(exist_ok=True)

            artifacts.extend([str(state_file), str(manuscript_qmd), str(references_bib)])

        elif command == "search":
            search_dir = self.repo_path / "outputs" / "search"
            search_dir.mkdir(parents=True, exist_ok=True)

            plan_file = search_dir / "search_plan.json"
            with open(plan_file, "w", encoding="utf-8") as f:
                f.write('{"query": "mock search", "date": "2026-05-24"}')

            results_file = search_dir / "raw_results.json"
            with open(results_file, "w", encoding="utf-8") as f:
                f.write('[{"title": "Mock Paper 1", "doi": "10.1000/xyz123"}]')

            artifacts.extend([str(plan_file), str(results_file)])

        elif command == "screen":
            evidence_file = self.repo_path / "outputs" / "search" / "screened_evidence.json"
            with open(evidence_file, "w", encoding="utf-8") as f:
                f.write('[{"title": "Mock Paper 1", "doi": "10.1000/xyz123", "screened": true}]')
            artifacts.append(str(evidence_file))

        elif command == "draft_outline":
            outline_file = self.repo_path / "outputs" / "drafts" / "outline.md"
            with open(outline_file, "w", encoding="utf-8") as f:
                f.write("# Outline\n\n- Introduction\n- Methods\n- Results\n- Discussion\n")
            artifacts.append(str(outline_file))

        elif command == "draft_section":
            section_name = args.get("name")
            if not section_name:
                raise ValueError("Missing 'name' argument for draft_section.")

            valid_sections = ["introduction", "methods", "results", "discussion"]
            if section_name not in valid_sections:
                raise ValueError(
                    f"Invalid section name '{section_name}'. Must be one of {valid_sections}"
                )

            section_file = self.repo_path / "outputs" / "drafts" / f"{section_name}.md"
            with open(section_file, "w", encoding="utf-8") as f:
                f.write(f"# {section_name.capitalize()}\n\nMock content for {section_name}.\n")
            artifacts.append(str(section_file))

        elif command in ["lint_bib", "check_refs", "lint_style", "audit_reporting"]:
            log_dir = self.repo_path / "outputs" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{command}.log"
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Log for {command} at {datetime.datetime.now().isoformat()}\n")
            artifacts.append(str(log_file))

        elif command == "render":
            render_dir = self.repo_path / "outputs" / "render"
            render_dir.mkdir(parents=True, exist_ok=True)

            docx_file = render_dir / "manuscript.docx"
            docx_file.touch(exist_ok=True)

            pdf_file = render_dir / "manuscript.pdf"
            pdf_file.touch(exist_ok=True)

            artifacts.extend([str(docx_file), str(pdf_file)])

        return artifacts

    def emit_manifest(self, gate_snapshot: dict[str, bool]) -> str:
        manifest_path = self.repo_path / "outputs" / "manifest.yaml"
        manifest_data = {
            "schema_version": "1.0",
            "project": "paper-writer",
            "status": "ready_for_delivery",
            "generated_at": datetime.datetime.now().isoformat(),
            "stage": "verified",
            "gate_snapshot": gate_snapshot,
            "artifacts": {
                "manuscript": ["outputs/render/manuscript.docx", "outputs/render/manuscript.pdf"],
                "bibliography": "templates/references.bib",
            },
            "verdict": "pass",
            "notes": [],
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)

        return str(manifest_path)
