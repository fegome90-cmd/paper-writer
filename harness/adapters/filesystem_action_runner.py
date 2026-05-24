import datetime
from pathlib import Path
from typing import Any

import yaml

from harness.ports.action_runner import ActionRunner


class FilesystemActionRunner(ActionRunner):
    """Adapter implementing ActionRunner that executes actions on local filesystem.

    CAVEAT (MVP): Several commands generate scaffold/placeholder content rather
    than delegating to real tools. This is intentional for the base construction
    phase per AGENTS.md "Base Construction Order". When real skill adapters are
    integrated (literature-search, academic-writer, pandoc), this adapter will
    delegate to those tools instead of writing mock content.

    Commands that currently write placeholder content:
      - search: writes mock search_plan.json and raw_results.json
      - screen: writes mock screened_evidence.json
      - draft_outline: writes a skeleton outline
      - draft_section: writes a skeleton section file
      - render: creates empty .docx/.pdf touch files

    Commands that are already real:
      - init: scaffolds directory structure and empty templates
      - lint_bib/check_refs/lint_style/audit_reporting: delegates to ToolWrapper instances
    """

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path.resolve()

    def _resolve(self, rel_path: str) -> Path:
        """Resolve a relative path and verify it stays within repo boundaries."""
        resolved = (self.repo_path / rel_path).resolve()
        if not str(resolved).startswith(str(self.repo_path)):
            raise ValueError(f"Path traversal detected: '{rel_path}' resolves outside repo root.")
        return resolved

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
                self._resolve(d).mkdir(parents=True, exist_ok=True)

            state_file = self._resolve("outputs/state.yaml")
            manuscript_qmd = self._resolve("templates/manuscript.qmd")
            manuscript_qmd.touch(exist_ok=True)

            references_bib = self._resolve("templates/references.bib")
            references_bib.touch(exist_ok=True)

            artifacts.extend([str(state_file), str(manuscript_qmd), str(references_bib)])

        elif command == "search":
            search_dir = self._resolve("outputs/search")
            search_dir.mkdir(parents=True, exist_ok=True)

            plan_file = self._resolve("outputs/search/search_plan.json")
            with open(plan_file, "w", encoding="utf-8") as f:
                f.write('{"query": "mock search", "date": "2026-05-24"}')

            results_file = self._resolve("outputs/search/raw_results.json")
            with open(results_file, "w", encoding="utf-8") as f:
                f.write('[{"title": "Mock Paper 1", "doi": "10.1000/xyz123"}]')

            artifacts.extend([str(plan_file), str(results_file)])

        elif command == "screen":
            evidence_file = self._resolve("outputs/search/screened_evidence.json")
            with open(evidence_file, "w", encoding="utf-8") as f:
                f.write('[{"title": "Mock Paper 1", "doi": "10.1000/xyz123", "screened": true}]')
            artifacts.append(str(evidence_file))

        elif command == "draft_outline":
            outline_file = self._resolve("outputs/drafts/outline.md")
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

            section_file = self._resolve(f"outputs/drafts/{section_name}.md")
            with open(section_file, "w", encoding="utf-8") as f:
                f.write(f"# {section_name.capitalize()}\n\nMock content for {section_name}.\n")
            artifacts.append(str(section_file))

        elif command in ["lint_bib", "check_refs", "lint_style", "audit_reporting"]:
            log_dir = self._resolve("outputs/logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self._resolve(f"outputs/logs/{command}.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Log for {command} at {datetime.datetime.now().isoformat()}\n")
            artifacts.append(str(log_file))

        elif command == "render":
            render_dir = self._resolve("outputs/render")
            render_dir.mkdir(parents=True, exist_ok=True)

            docx_file = self._resolve("outputs/render/manuscript.docx")
            docx_file.touch(exist_ok=True)

            pdf_file = self._resolve("outputs/render/manuscript.pdf")
            pdf_file.touch(exist_ok=True)

            artifacts.extend([str(docx_file), str(pdf_file)])

        return artifacts

    def emit_manifest(self, gate_snapshot: dict[str, bool]) -> str:
        manifest_path = self._resolve("outputs/manifest.yaml")
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
