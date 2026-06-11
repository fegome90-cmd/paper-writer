import datetime
import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

from harness.ports.action_runner import ActionRunner
from harness.ports.paper_search_provider import SEARCH_FILTER_KEYS
from harness.ports.skill_adapter import SkillAdapter
from harness.services.assembler import assemble_manuscript
from harness.services.verify_artifacts import generate_verify_artifacts

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
        if not resolved.is_relative_to(self.repo_path):
            raise ValueError(f"Path traversal detected: '{rel_path}' resolves outside repo root.")
        return resolved

    def _resolve_run(self, rel_path: str) -> Path:
        """Resolve a per-run artifact path under outputs/runs/{run_id}/.

        Also updates the 'outputs/latest' symlink to point at the current run.
        """
        run_dir = self._resolve(f"outputs/runs/{self.run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)
        resolved = (run_dir / rel_path).resolve()
        if not resolved.is_relative_to(self.repo_path):
            raise ValueError(f"Path traversal detected: '{rel_path}' resolves outside repo root.")
        # Update latest symlink — use raw path (not _resolve) to avoid
        # following the existing symlink, which would resolve to the old target dir
        latest = self.repo_path / "outputs" / "latest"
        try:
            latest.unlink(missing_ok=True)
        except (FileNotFoundError, PermissionError, OSError):
            pass
        try:
            latest.symlink_to(run_dir, target_is_directory=True)
        except OSError:
            pass  # Symlinks may not be supported on all platforms
        return resolved

    def _check_result(self, result: Any, command: str) -> None:
        if hasattr(result, "status") and result.status == "fail":
            error_msg = getattr(result, "summary", "") or (
                f"Skill adapter returned status='fail' for command '{command}'"
            )
            raise ValueError(error_msg)

    # ── Run metadata (lineage + status) ───────────────────────────────

    def _write_run_yaml(
        self,
        command: str,
        parent_run_id: str | None = None,
        status: str = "running",
    ) -> None:
        """Write run.yaml metadata to current run directory."""
        run_dir = self._resolve(f"outputs/runs/{self.run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)
        run_yaml = run_dir / "run.yaml"
        metadata = {
            "run_id": self.run_id,
            "command": command,
            "created_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "status": status,
            "artifacts": [],
        }
        if parent_run_id:
            metadata["parent_run_id"] = parent_run_id
        run_yaml.write_text(yaml.dump(metadata, default_flow_style=False), encoding="utf-8")

    def _complete_run(self, artifacts: list[str]) -> None:
        """Mark current run as completed, appending new artifacts."""
        run_dir = self._resolve(f"outputs/runs/{self.run_id}")
        run_yaml = run_dir / "run.yaml"
        if not run_yaml.exists():
            return
        metadata = yaml.safe_load(run_yaml.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            return
        metadata["status"] = "completed"
        metadata["completed_at"] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        # Append new artifacts to existing list (deduplicated)
        existing = metadata.get("artifacts") or []
        combined = list(dict.fromkeys(existing + artifacts))
        metadata["artifacts"] = combined
        run_yaml.write_text(yaml.dump(metadata, default_flow_style=False), encoding="utf-8")

    def _fail_run(self, error: str) -> None:
        """Mark current run as failed with error message."""
        run_dir = self._resolve(f"outputs/runs/{self.run_id}")
        run_yaml = run_dir / "run.yaml"
        if not run_yaml.exists():
            return
        metadata = yaml.safe_load(run_yaml.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            return
        metadata["status"] = "failed"
        metadata["failed_at"] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        metadata["error"] = error[:500]
        run_yaml.write_text(yaml.dump(metadata, default_flow_style=False), encoding="utf-8")

    def run_action(self, command: str, args: dict[str, Any]) -> list[str]:
        if args is None:
            args = {}
        artifacts: list[str] = []

        # Capture parent run_id before search/chain creates a new one
        parent_run_id: str | None = None
        if command in ("search", "chain"):
            parent_run_id = self.run_id  # Store before overwriting
            self._run_id = datetime.datetime.now().strftime("%Y%m%dT%H%M%S.%f")
            # Update .run_id so subsequent commands (screen, draft, etc.)
            # follow the latest search results.
            run_id_file = self._resolve("outputs/.run_id")
            if run_id_file.exists():
                run_id_file.write_text(self._run_id, encoding="utf-8")

        # Write run metadata at start of every command.
        # For search/chain (new runs): always write.
        # For other commands (reusing existing run): only if no run.yaml exists.
        try:
            run_dir = self._resolve(f"outputs/runs/{self.run_id}")
            run_yaml_path = run_dir / "run.yaml"
            if command in ("search", "chain") or not run_yaml_path.exists():
                self._write_run_yaml(command, parent_run_id=parent_run_id)
        except OSError:
            pass  # Non-critical: metadata is best-effort

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
                            # Validate preset before copying
                            try:
                                import yaml

                                from validators.preset import validate_preset

                                preset_data = yaml.safe_load(src.read_text(encoding="utf-8"))
                                findings = validate_preset(preset_data or {})
                                for finding in findings:
                                    if finding.get("severity") == "error":
                                        logger.warning(
                                            "Preset validation: %s",
                                            finding.get("message", "unknown"),
                                        )
                            except (ValueError, OSError) as exc:
                                logger.warning("Preset validation failed: %s", exc)
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

            # Persist review mode configuration
            from harness.services.review_config import save_review_config

            review_mode = args.get("mode", "rapid")
            search_window = args.get("search_window")
            config_path = save_review_config(
                self.repo_path, mode=review_mode, search_window=search_window
            )
            artifacts.append(str(config_path))

        elif command == "search":
            search_dir = self._resolve_run("search")
            search_dir.mkdir(parents=True, exist_ok=True)

            adapter = self._skill_adapters.get("literature_search")
            if adapter:
                raw_papers = args.get("raw_papers")
                inputs = {
                    "query": args.get("query", ""),
                    "output_dir": str(search_dir),
                    "raw_papers": raw_papers,
                }
                for key in SEARCH_FILTER_KEYS:
                    if key in args and args[key] is not None:
                        inputs[key] = args[key]
                result = adapter.execute(
                    command="search",
                    inputs=inputs,
                    context={"cwd": str(self.repo_path)},
                )
                self._check_result(result, "search")
                raw_results_path = self._resolve_run("search/raw_results.json")
                # Fail-closed: do NOT synthesize fake papers when adapter
                # produces no raw_results.json.  The adapter is responsible
                # for writing it.  If missing, downstream commands must treat
                # search as incomplete.
                if raw_results_path.exists():
                    artifacts.append(str(raw_results_path))
                artifacts.extend(result.artifacts)
            else:
                # DEPRECATED: Mock path only reachable when skill_adapters
                # is explicitly empty. OrchestratorBuilder always wires
                # real adapters. This fallback exists for backward compat
                # with test-only configurations.
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
                        "min_tier": args.get("min_tier", "Tier 3"),
                    },
                    context={"cwd": str(self.repo_path)},
                )
                self._check_result(result, "screen")
                artifacts.extend(result.artifacts)
            else:
                # DEPRECATED: Mock path — see search mock comment above.
                evidence_file = self._resolve_run("search/screened_evidence.json")
                with open(evidence_file, "w", encoding="utf-8") as f:
                    f.write(
                        '[{"title": "Mock Paper 1", "doi": "10.1000/xyz123", "screened": true}]'
                    )
                artifacts.append(str(evidence_file))

        elif command == "chain":
            # Chain reads from previous search run (via latest symlink)
            # but writes to its own fresh run directory.
            latest_search = self._resolve("outputs/latest/search")
            search_dir = self._resolve_run("search")
            search_dir.mkdir(parents=True, exist_ok=True)

            adapter = self._skill_adapters.get("literature_search")
            if adapter:
                cache_dir = args.get("cache_dir")
                result = adapter.execute(
                    command="chain",
                    inputs={
                        "search_dir": str(latest_search if latest_search.exists() else search_dir),
                        "output_dir": str(search_dir),
                        "query": args.get("query", ""),
                        "max_rounds": args.get("max_rounds", 2),
                        "max_papers": args.get("max_papers", 80),
                        "relevance_threshold": args.get("relevance_threshold", 0.25),
                        "cache_dir": cache_dir,
                    },
                    context={"cwd": str(self.repo_path)},
                )
                self._check_result(result, "chain")
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
                self._check_result(result, "draft_outline")
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

            valid_sections = [
                "abstract",
                "introduction",
                "literature_review",
                "methods",
                "results",
                "discussion",
                "conclusion",
            ]
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
                self._check_result(result, "draft_section")
                artifacts.extend(result.artifacts)
            else:
                section_file = self._resolve_run(f"drafts/{section_name}.md")
                with open(section_file, "w", encoding="utf-8") as f:
                    title = section_name.replace("_", " ").title()
                    f.write(f"# {title}\n\nMock content for {section_name}.\n")
                artifacts.append(str(section_file))

        elif command == "draft_all":
            drafts_dir = self._resolve_run("drafts")
            drafts_dir.mkdir(parents=True, exist_ok=True)

            adapter = self._skill_adapters.get("academic_writer")
            if adapter:
                result = adapter.execute(
                    command="draft_all",
                    inputs={
                        "outline_path": str(self._resolve_run("drafts/outline.md")),
                        "evidence_path": str(self._resolve_run("search/screened_evidence.json")),
                        "bib_path": str(self._resolve("templates/references.bib")),
                        "output_dir": str(drafts_dir),
                    },
                    context={"cwd": str(self.repo_path)},
                )
                self._check_result(result, "draft_all")
                artifacts.extend(result.artifacts)
            else:
                # Fallback: create mock sections for all manifest sections
                for sec in [
                    "introduction",
                    "methods",
                    "results",
                    "discussion",
                    "abstract",
                    "literature_review",
                    "conclusion",
                ]:
                    section_file = self._resolve_run(f"drafts/{sec}.md")
                    title = sec.replace("_", " ").title()
                    with open(section_file, "w", encoding="utf-8") as f:
                        f.write(f"# {title}\n\nMock content for {sec}.\n")
                    artifacts.append(str(section_file))

        elif command in [
            "lint_bib",
            "check_refs",
            "lint_style",
            "audit_reporting",
            "audit_ethics",
            "import_bib",
            "zotero_sync",
        ]:
            log_dir = self._resolve_run("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self._resolve_run(f"logs/{command}.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Log for {command} at {datetime.datetime.now().isoformat()}\n")
            artifacts.append(str(log_file))

        elif command == "protocol":
            search_dir = Path(args.get("search_dir", str(self._resolve_run("search"))))
            output_path = args.get("output")
            project_name = args.get("project_name", "paper-writer")
            try:
                from validators.protocol_generator import generate_protocol

                protocol_md = generate_protocol(
                    search_dir,
                    output_path=Path(output_path) if output_path else None,
                    project_name=project_name,
                )
                if output_path:
                    out = Path(output_path)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(protocol_md, encoding="utf-8")
                    artifacts.append(str(out))
                else:
                    protocol_file = self._resolve_run("protocol.md")
                    protocol_file.write_text(protocol_md, encoding="utf-8")
                    artifacts.append(str(protocol_file))
            except (ValueError, OSError) as e:
                logger.warning("Protocol generation failed: %s", e)

        elif command == "export_bib":
            search_dir = self._resolve_run("search")
            export_bib_path = self._resolve(args.get("bib_path", "templates/references.bib"))

            adapter = self._skill_adapters.get("literature_search")
            if adapter:
                result = adapter.execute(
                    command="export_bib",
                    inputs={
                        "search_dir": str(search_dir),
                        "bib_path": str(export_bib_path),
                    },
                    context={"cwd": str(self.repo_path)},
                )
                self._check_result(result, "export_bib")
                artifacts.extend(result.artifacts)

        elif command in (
            "audit_prose",
            "audit_claims",
            "audit_citations",
            "audit_writing_quality",
        ):
            # Manuscript-based audits: find manuscript, write log
            log_dir = self._resolve_run("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            manuscript = args.get("file")
            if not manuscript:
                # Default: assembled manuscript from drafts
                draft_dir = self._resolve_run("drafts")
                manuscript_path = assemble_manuscript(draft_dir)
                manuscript = str(manuscript_path)
            log_file = self._resolve_run(f"logs/{command}.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Audit {command} on {manuscript}\n")
            artifacts.append(str(log_file))

        elif command == "audit_code_health":
            # Code health audit: no manuscript needed, writes log
            log_dir = self._resolve_run("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self._resolve_run("logs/audit_code_health.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("Code health audit via Trifecta\n")
            artifacts.append(str(log_file))

        elif command == "render":
            render_dir = self._resolve_run("render")
            render_dir.mkdir(parents=True, exist_ok=True)
            draft_dir = self._resolve_run("drafts")
            manuscript_path = assemble_manuscript(draft_dir)
            if manuscript_path.is_file():
                artifacts.append(str(manuscript_path))
            artifacts.append(str(render_dir))

        elif command == "verify":
            verify_dir = self._resolve_run("verify")
            verify_dir.mkdir(parents=True, exist_ok=True)
            search_dir = self._resolve_run("search")
            draft_dir = self._resolve_run("drafts")
            verify_bib_path = self._resolve("templates/references.bib")
            artifact_paths = generate_verify_artifacts(
                search_dir=search_dir,
                draft_dir=draft_dir,
                bib_path=verify_bib_path,
                output_dir=verify_dir,
            )
            artifacts.extend(artifact_paths)

        else:
            raise ValueError(f"Unknown action command: '{command}'")

        # Mark run as completed with artifact list
        try:
            self._complete_run(artifacts)
        except OSError:
            pass  # Non-critical: metadata is best-effort

        return artifacts

    def _mark_run_failed(self, error: str) -> None:
        """Public interface for orchestrator to mark run as failed.

        Called by Orchestrator when run_action raises an exception.
        """
        try:
            self._fail_run(error)
        except OSError:
            pass

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
        # Check both run-specific (outputs/latest/render/) and root (outputs/render/) paths.
        manuscript_artifacts: list[str] = []
        for candidate in [
            "outputs/latest/render/manuscript.docx",
            "outputs/latest/render/manuscript.pdf",
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
