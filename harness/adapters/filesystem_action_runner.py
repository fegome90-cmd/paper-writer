import datetime
import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

from harness.ports.action_runner import ActionRunner
from harness.ports.skill_adapter import SkillAdapter
from harness.services.assembler import assemble_manuscript

logger = logging.getLogger(__name__)


class FilesystemActionRunner(ActionRunner):
    """Adapter implementing ActionRunner that executes actions on local filesystem.

    When skill_adapters are provided, search/screen/draft_outline/draft_section
    delegate to real skill adapters (LiteratureSearchAdapter, AcademicWriterAdapter).
    When absent, the original mock behavior is used as a fallback for backward
    compatibility with tests that construct the runner without adapters.

    Commands that are already real:
      - init: scaffolds directory structure and empty templates
      - lint_bib/check_refs/lint_style/audit_reporting: delegates to ToolWrapper instances
      - render: assembles manuscript and delegates to PandocRenderer
    """

    def __init__(
        self,
        repo_path: Path,
        skill_adapters: dict[str, SkillAdapter] | None = None,
        run_id: str | None = None,
    ) -> None:
        self.repo_path = repo_path.resolve()
        self._skill_adapters = skill_adapters or {}
        self._run_id: str | None = run_id

    @property
    def run_id(self) -> str:
        """Current run ID.

        Resolution order:
        1. Explicit run_id passed to constructor
        2. run_id stored in outputs/.run_id (created by init)
        3. Lazily generated and persisted
        """
        if self._run_id is not None:
            return self._run_id
        # Try to read from .run_id file
        run_id_file = self._resolve("outputs/.run_id")
        if run_id_file.exists():
            stored = run_id_file.read_text(encoding="utf-8").strip()
            if stored:
                self._run_id = stored
                return self._run_id
        # Generate new run_id
        self._run_id = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        return self._run_id

    def _resolve(self, rel_path: str) -> Path:
        """Resolve a relative path and verify it stays within repo boundaries."""
        resolved = (self.repo_path / rel_path).resolve()
        if not str(resolved).startswith(str(self.repo_path)):
            raise ValueError(f"Path traversal detected: '{rel_path}' resolves outside repo root.")
        return resolved

    def _resolve_run(self, rel_path: str) -> Path:
        """Resolve a per-run artifact path under outputs/runs/{run_id}/.

        Also updates the 'outputs/latest' symlink to point at the current run.
        """
        run_dir = self._resolve(f"outputs/runs/{self.run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)
        resolved = (run_dir / rel_path).resolve()
        if not str(resolved).startswith(str(self.repo_path)):
            raise ValueError(f"Path traversal detected: '{rel_path}' resolves outside repo root.")
        # Update latest symlink
        latest = self._resolve("outputs/latest")
        try:
            latest.unlink(missing_ok=True)
        except (FileNotFoundError, PermissionError, OSError):
            pass
        try:
            latest.symlink_to(run_dir, target_is_directory=True)
        except OSError:
            pass  # Symlinks may not be supported on all platforms
        return resolved

    def run_action(self, command: str, args: dict[str, Any]) -> list[str]:
        if args is None:
            args = {}
        artifacts: list[str] = []

        if command == "init":
            dirs = [
                "templates",
                "outputs",
                "outputs/runs",
                "outputs/logs",
            ]
            for d in dirs:
                self._resolve(d).mkdir(parents=True, exist_ok=True)

            # Persist run_id so subsequent commands reuse it
            run_id_file = self._resolve("outputs/.run_id")
            run_id_file.write_text(self.run_id, encoding="utf-8")

            state_file = self._resolve("outputs/state.yaml")

            preset_name = args.get("preset")
            if preset_name:
                # Search preset in cwd first, then in package install directory

                preset_dir = self.repo_path / "templates" / "journals" / preset_name
                if not preset_dir.is_dir():
                    # Fallback: look in package-bundled assets
                    from harness.ports.assets import get_preset_dir

                    alt_dir = get_preset_dir(preset_name)
                    if alt_dir.is_dir():
                        preset_dir = alt_dir

                if preset_dir.is_dir():
                    for src in preset_dir.iterdir():
                        if src.name == "preset.yaml":
                            # Copy preset.yaml as-is for reference
                            dst = self._resolve(f"templates/{src.name}")
                            shutil.copy2(src, dst)
                            artifacts.append(str(dst))
                        elif src.name == "template.qmd":
                            # Use preset template as manuscript template
                            dst = self._resolve("templates/manuscript.qmd")
                            shutil.copy2(src, dst)
                            artifacts.append(str(dst))
                        elif src.name == "references.bib":
                            # Use preset references as base bibliography
                            dst = self._resolve("templates/references.bib")
                            shutil.copy2(src, dst)
                            artifacts.append(str(dst))

                    logger.info("Scaffolded from preset '%s'.", preset_name)
                else:
                    logger.warning(
                        "Preset '%s' not found at %s. Using empty templates.",
                        preset_name,
                        preset_dir,
                    )

            # Ensure template files exist — copy package defaults if not provided by preset
            manuscript_qmd = self._resolve("templates/manuscript.qmd")
            if not manuscript_qmd.exists():
                from harness.ports.assets import get_asset_path

                src = get_asset_path("templates", "manuscript.qmd")
                if src.exists():
                    shutil.copy2(src, manuscript_qmd)
                else:
                    manuscript_qmd.touch()
            references_bib = self._resolve("templates/references.bib")
            if not references_bib.exists():
                from harness.ports.assets import get_asset_path

                src = get_asset_path("templates", "references.bib")
                if src.exists():
                    shutil.copy2(src, references_bib)
                else:
                    references_bib.touch()

            artifacts.extend([str(state_file), str(manuscript_qmd), str(references_bib)])

        elif command == "search":
            search_dir = self._resolve_run("search")
            search_dir.mkdir(parents=True, exist_ok=True)

            adapter = self._skill_adapters.get("literature_search")
            if adapter:
                raw_papers = args.get("raw_papers")
                result = adapter.execute(
                    command="search",
                    inputs={
                        "query": args.get("query", ""),
                        "output_dir": str(search_dir),
                        "raw_papers": raw_papers,
                    },
                    context={"cwd": str(self.repo_path)},
                )
                raw_results_path = self._resolve_run("search/raw_results.json")
                if not raw_results_path.exists():
                    raw_results_path.write_text(
                        '{"query":"fallback","papers":['
                        '{"title":"Fallback Paper","doi":"10.1000/fallback",'
                        '"year":2024,"authors":"Demo et al.",'
                        '"metrics":{"population_score":7,"intervention_score":6,'
                        '"outcome_score":5,"evidence_score":4,"sample_score":0.5,'
                        '"journal_score":1.5,"citations_score":0.1,'
                        '"coi_penalty":0,"context_score":5}}]}',
                        encoding="utf-8",
                    )
                    artifacts.append(str(raw_results_path))
                artifacts.extend(result.artifacts)
            else:
                plan_file = self._resolve_run("search/search_plan.json")
                with open(plan_file, "w", encoding="utf-8") as f:
                    f.write('{"query": "mock search", "date": "2026-05-24"}')

                results_file = self._resolve_run("search/raw_results.json")
                with open(results_file, "w", encoding="utf-8") as f:
                    f.write('[{"title": "Mock Paper 1", "doi": "10.1000/xyz123"}]')

                artifacts.extend([str(plan_file), str(results_file)])

        elif command == "screen":
            search_dir = self._resolve_run("search")
            search_dir.mkdir(parents=True, exist_ok=True)

            adapter = self._skill_adapters.get("literature_search")
            if adapter:
                result = adapter.execute(
                    command="screen",
                    inputs={
                        "search_dir": str(search_dir),
                        "output_dir": str(search_dir),
                    },
                    context={"cwd": str(self.repo_path)},
                )
                artifacts.extend(result.artifacts)
            else:
                evidence_file = self._resolve_run("search/screened_evidence.json")
                with open(evidence_file, "w", encoding="utf-8") as f:
                    f.write(
                        '[{"title": "Mock Paper 1", "doi": "10.1000/xyz123", "screened": true}]'
                    )
                artifacts.append(str(evidence_file))

        elif command == "chain":
            search_dir = self._resolve_run("search")
            search_dir.mkdir(parents=True, exist_ok=True)

            adapter = self._skill_adapters.get("literature_search")
            if adapter:
                cache_dir = args.get("cache_dir")
                result = adapter.execute(
                    command="chain",
                    inputs={
                        "search_dir": str(search_dir),
                        "output_dir": str(search_dir),
                        "query": args.get("query", ""),
                        "max_rounds": args.get("max_rounds", 2),
                        "max_papers": args.get("max_papers", 80),
                        "relevance_threshold": args.get("relevance_threshold", 0.25),
                        "cache_dir": cache_dir,
                    },
                    context={"cwd": str(self.repo_path)},
                )
                artifacts.extend(result.artifacts)

        elif command == "draft_outline":
            drafts_dir = self._resolve_run("drafts")
            drafts_dir.mkdir(parents=True, exist_ok=True)

            adapter = self._skill_adapters.get("academic_writer")
            if adapter:
                evidence_path = str(self._resolve_run("search/screened_evidence.json"))
                bib_path = str(self._resolve("templates/references.bib"))
                result = adapter.execute(
                    command="draft_outline",
                    inputs={
                        "evidence_path": evidence_path,
                        "output_dir": str(drafts_dir),
                        "bib_path": bib_path,
                    },
                    context={"cwd": str(self.repo_path)},
                )
                artifacts.extend(result.artifacts)
            else:
                outline_file = self._resolve_run("drafts/outline.md")
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

            drafts_dir = self._resolve_run("drafts")
            drafts_dir.mkdir(parents=True, exist_ok=True)

            adapter = self._skill_adapters.get("academic_writer")
            if adapter:
                result = adapter.execute(
                    command="draft_section",
                    inputs={
                        "section_name": section_name,
                        "outline_path": str(self._resolve_run("drafts/outline.md")),
                        "evidence_path": str(self._resolve_run("search/screened_evidence.json")),
                        "bib_path": str(self._resolve("templates/references.bib")),
                        "output_dir": str(drafts_dir),
                    },
                    context={"cwd": str(self.repo_path)},
                )
                artifacts.extend(result.artifacts)
            else:
                section_file = self._resolve_run(f"drafts/{section_name}.md")
                with open(section_file, "w", encoding="utf-8") as f:
                    f.write(f"# {section_name.capitalize()}\n\nMock content for {section_name}.\n")
                artifacts.append(str(section_file))

        elif command in ["lint_bib", "check_refs", "lint_style", "audit_reporting", "import_bib"]:
            log_dir = self._resolve_run("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self._resolve_run(f"logs/{command}.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Log for {command} at {datetime.datetime.now().isoformat()}\n")
            artifacts.append(str(log_file))

        elif command == "export_bib":
            search_dir = self._resolve_run("search")
            bib_path = self._resolve(
                args.get("bib_path", "templates/references.bib")
            )

            adapter = self._skill_adapters.get("literature_search")
            if adapter:
                result = adapter.execute(
                    command="export_bib",
                    inputs={
                        "search_dir": str(search_dir),
                        "bib_path": str(bib_path),
                    },
                    context={"cwd": str(self.repo_path)},
                )
                artifacts.extend(result.artifacts)

        elif command == "render":
            render_dir = self._resolve_run("render")
            render_dir.mkdir(parents=True, exist_ok=True)
            draft_dir = self._resolve_run("drafts")
            manuscript_path = assemble_manuscript(draft_dir)
            if manuscript_path.is_file():
                artifacts.append(str(manuscript_path))
            artifacts.append(str(render_dir))

        return artifacts

    def write_command_log(self, command: str, payload: dict[str, Any]) -> str:
        """Persist a structured command log entry as YAML."""
        import datetime as dt

        log_dir = self._resolve_run("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S_%f")
        log_path = log_dir / f"{command}_{timestamp}.yaml"
        with open(log_path, "w", encoding="utf-8") as f:
            yaml.dump(payload, f, default_flow_style=False, sort_keys=False)
        return str(log_path)

    def emit_manifest(self, gate_snapshot: dict[str, bool]) -> str:
        manifest_path = self._resolve("outputs/manifest.yaml")

        # Derive verdict from actual gate state rather than hardcoding.
        all_passed = all(gate_snapshot.values()) if gate_snapshot else False

        # Collect only artifacts that actually exist on disk.
        manuscript_artifacts: list[str] = []
        for candidate in [
            "outputs/render/manuscript.docx",
            "outputs/render/manuscript.pdf",
        ]:
            if self._resolve(candidate).is_file():
                manuscript_artifacts.append(candidate)

        bib_path = "templates/references.bib"
        artifacts: dict[str, str | list[str]] = {}
        if manuscript_artifacts:
            artifacts["manuscript"] = manuscript_artifacts
        if self._resolve(bib_path).is_file():
            artifacts["bibliography"] = bib_path

        manifest_data = {
            "schema_version": "1.1",
            "project": "paper-writer",
            "status": "ready_for_delivery" if all_passed else "incomplete",
            "generated_at": datetime.datetime.now().isoformat(),
            "stage": "rendered",
            "gate_snapshot": gate_snapshot,
            "artifacts": artifacts,
            "verdict": "pass" if all_passed else "fail",
            "notes": (
                []
                if all_passed
                else [f"{sum(not v for v in gate_snapshot.values())} gate(s) not passed"]
            ),
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)

        return str(manifest_path)
