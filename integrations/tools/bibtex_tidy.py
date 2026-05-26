"""Bibliography normalization wrapper.

Runs bibtex-tidy (or falls back to a built-in validator) to normalize
and validate the references.bib file. Returns structured findings
consumed by the gate system.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult
from validators.bibliography import validate_bibliography


class BibliographyNormalizer(ToolWrapper):
    """Normalizes and validates the references.bib file.

    Uses bibtex-tidy if available. Falls back to a built-in syntax
    check that detects unclosed braces and malformed entries.
    """

    @property
    def name(self) -> str:
        return "bibtex-tidy"

    @property
    def gate(self) -> str:
        return "bib_normalized"

    def is_available(self) -> bool:
        """bibtex-tidy is optional — built-in fallback always exists."""
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        bib_path = artifacts.get("bibliography")
        if not bib_path:
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary="No bibliography file specified.",
                findings=[
                    {
                        "code": "missing_artifact",
                        "severity": "error",
                        "message": "Artifacts dict missing 'bibliography' key.",
                    }
                ],
                artifacts_checked=[],
            )

        bib_file = Path(bib_path)
        if not bib_file.is_file():
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary=f"Bibliography file not found: {bib_path}",
                findings=[
                    {
                        "code": "file_not_found",
                        "severity": "error",
                        "message": f"File does not exist: {bib_path}",
                        "artifact": bib_path,
                    }
                ],
                artifacts_checked=[],
            )

        # Resolve path to bibtex-tidy
        executable_info = self._resolve_executable(context)
        if not executable_info:
            # Fall back to built-in validation
            return self._builtin_validate(bib_file, bib_path)

        executable, source = executable_info

        # Verify version
        version_ok, version_msg = self._verify_version(executable, source)
        if not version_ok:
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary=f"bibtex-tidy version verification failed: {version_msg}",
                findings=[
                    {
                        "code": "version_mismatch",
                        "severity": "error",
                        "message": version_msg,
                        "artifact": bib_path,
                    }
                ],
                artifacts_checked=[bib_path],
            )

        # Backup the original bibliography file to protect against corruption during --modify
        # Apply strict collision protection
        backup_path = bib_file.with_suffix(".bib.bak")
        if backup_path.exists():
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary="Backup collision detected: references.bib.bak already exists.",
                findings=[
                    {
                        "code": "backup_collision",
                        "severity": "error",
                        "message": (
                            "A temporary backup file already exists. Aborting to prevent data loss."
                        ),
                        "artifact": bib_path,
                    }
                ],
                artifacts_checked=[bib_path],
            )

        try:
            shutil.copy2(bib_file, backup_path)
        except OSError as e:
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary=f"Failed to create backup of bibliography file: {e}",
                findings=[
                    {
                        "code": "backup_error",
                        "severity": "error",
                        "message": f"Could not copy {bib_path} to backup: {e}",
                        "artifact": bib_path,
                    }
                ],
                artifacts_checked=[bib_path],
            )

        # Execute bibtex-tidy with strict parameters
        try:
            result = subprocess.run(
                [str(executable), str(bib_file), "--modify", "--sort"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                # Restore original file from backup
                if backup_path.exists():
                    shutil.move(str(backup_path), str(bib_file))
                return ValidatorResult(
                    validator="bibliography",
                    status="fail",
                    summary="bibtex-tidy reported errors. Restored bibliography from backup.",
                    findings=self._parse_bibtex_tidy_errors(result.stderr, bib_path),
                    artifacts_checked=[bib_path],
                )

            # Success, remove backup file
            if backup_path.exists():
                backup_path.unlink()
        except (OSError, subprocess.SubprocessError) as e:
            # Restore original file from backup
            if backup_path.exists():
                shutil.move(str(backup_path), str(bib_file))
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary=f"bibtex-tidy execution failed: {e}. Restored backup.",
                findings=[
                    {
                        "code": "tool_error",
                        "severity": "error",
                        "message": str(e),
                        "artifact": bib_path,
                    }
                ],
                artifacts_checked=[bib_path],
            )

        findings: list[dict[str, Any]] = []
        if source == "local" and version_msg == "1.11.0":
            findings.append(
                {
                    "code": "known_version_mismatch",
                    "severity": "warning",
                    "message": (
                        "Known local package version-report mismatch: "
                        "package.json specifies 1.12.0 but CLI reports v1.11.0."
                    ),
                    "artifact": bib_path,
                }
            )
            summary = "Bibliography normalized (with known version mismatch)."
        else:
            summary = "Bibliography normalized successfully."

        return ValidatorResult(
            validator="bibliography",
            status="pass",
            summary=summary,
            findings=findings,
            artifacts_checked=[bib_path],
        )

    def _resolve_executable(self, context: dict[str, Any]) -> tuple[Path, str] | None:
        """Resolve path to bibtex-tidy in order of preference:
        1. Environment override: BIBTEX_TIDY_BIN (wins first, fails fast)
        2. Local toolchain: repo_path/tools/node/node_modules/.bin/bibtex-tidy
        3. Global PATH fallback (only if BIBTEX_TIDY_ALLOW_GLOBAL=true)

        Returns:
            Tuple of (Path to executable, source label) or None.
            source label is one of: "env", "local", "global"
        """

        # 1. Environment override (Wins first)
        env_bin = os.environ.get("BIBTEX_TIDY_BIN")
        if env_bin:
            env_path = Path(env_bin)
            if env_path.exists() and os.access(env_path, os.X_OK):
                return env_path, "env"
            raise FileNotFoundError(
                f"BIBTEX_TIDY_BIN specified but not found or not executable: {env_bin}"
            )

        # 2. Local toolchain (relative to repo root)
        repo_path = Path(context.get("repo_path", Path.cwd()))
        local_path = repo_path / "tools" / "node" / "node_modules" / ".bin" / "bibtex-tidy"
        if local_path.exists() and os.access(local_path, os.X_OK):
            return local_path, "local"

        # 3. Global PATH fallback (only if allowed by config)
        allow_global = os.environ.get("BIBTEX_TIDY_ALLOW_GLOBAL", "").lower() in (
            "true",
            "1",
            "yes",
        )
        if allow_global:
            global_bin = shutil.which("bibtex-tidy")
            if global_bin:
                return Path(global_bin), "global"

        return None

    def _verify_version(self, executable: Path, source: str) -> tuple[bool, str]:
        """Verify bibtex-tidy version based on its resolution source.

        - local toolchain: package/lock expects 1.12.0, CLI may report 1.12.0 or 1.11.0.
        - env/global: expects exactly 1.12.0.
        """
        try:
            result = subprocess.run(
                [str(executable), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False, f"Failed to run version check (exit code {result.returncode})"

            version_str = result.stdout.strip().lstrip("v")

            if source == "local":
                if version_str not in ("1.12.0", "1.11.0"):
                    return (
                        False,
                        f"Invalid local version: expected 1.12.0 or 1.11.0, got {version_str}",
                    )
                return True, version_str
            else:
                # Env override or global PATH: Must be exactly 1.12.0
                if version_str != "1.12.0":
                    return (
                        False,
                        f"Invalid external version: expected exactly 1.12.0, got {version_str}",
                    )
                return True, version_str
        except Exception as e:
            return False, f"Error running version check: {e}"

    def _builtin_validate(self, bib_file: Path, bib_path: str) -> ValidatorResult:
        """Built-in BibTeX validation when bibtex-tidy is not available.

        Parses entries and delegates domain validation to
        validators.bibliography. Emits explicit degraded-mode notice.
        """

        findings: list[dict[str, Any]] = []
        content = bib_file.read_text(encoding="utf-8", errors="replace")

        # Explicit degraded-mode notice
        findings.append(
            {
                "code": "degraded_mode",
                "severity": "warning",
                "message": (
                    "bibtex-tidy not installed. Using built-in validation. "
                    "Install: npm install -g bibtex-tidy"
                ),
                "artifact": bib_path,
            }
        )

        if not content.strip():
            findings.append(
                {
                    "code": "empty_file",
                    "severity": "error",
                    "message": "Bibliography file is empty.",
                    "artifact": bib_path,
                }
            )
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary="Bibliography file is empty.",
                findings=findings,
                artifacts_checked=[bib_path],
            )

        # Basic brace balance check
        open_braces = content.count("{")
        close_braces = content.count("}")
        if open_braces != close_braces:
            findings.append(
                {
                    "code": "unbalanced_braces",
                    "severity": "error",
                    "message": f"Unbalanced braces: {open_braces} open, {close_braces} close.",
                    "artifact": bib_path,
                }
            )

        # Parse entries and entry types for domain validation
        entry_pattern = re.compile(
            r"@(\w+)\s*\{\s*([^,\s]+)\s*,\s*(.*?)\n\s*\}",
            re.DOTALL | re.IGNORECASE,
        )
        entries: dict[str, dict[str, str]] = {}
        entry_types: dict[str, str] = {}

        for match in entry_pattern.finditer(content):
            entry_type = match.group(1)
            key = match.group(2).strip()
            body = match.group(3)
            fields: dict[str, str] = {}
            for field_match in re.finditer(r"(\w+)\s*=\s*\{([^}]*)\}", body, re.IGNORECASE):
                fields[field_match.group(1).lower().strip()] = field_match.group(2).strip()
            entries[key] = fields
            entry_types[key] = entry_type

        if not entries:
            findings.append(
                {
                    "code": "no_entries",
                    "severity": "error",
                    "message": "No BibTeX entries found.",
                    "artifact": bib_path,
                }
            )
        else:
            # Delegate to domain validator
            findings.extend(validate_bibliography(entries, entry_types))

        status = "fail" if any(f["severity"] == "error" for f in findings) else "pass"
        return ValidatorResult(
            validator="bibliography",
            status=status,
            summary="normalization skipped / builtin validation used",
            findings=findings,
            artifacts_checked=[bib_path],
        )

    def _parse_bibtex_tidy_errors(self, stderr: str, bib_path: str) -> list[dict[str, Any]]:
        """Parse bibtex-tidy stderr into structured findings."""
        findings: list[dict[str, Any]] = []
        for line in stderr.strip().splitlines():
            line = line.strip()
            if line:
                findings.append(
                    {
                        "code": "bibtex_tidy_error",
                        "severity": "error",
                        "message": line,
                        "artifact": bib_path,
                    }
                )
        if not findings:
            findings.append(
                {
                    "code": "bibtex_tidy_error",
                    "severity": "error",
                    "message": "bibtex-tidy exited non-zero but produced no error output.",
                    "artifact": bib_path,
                }
            )
        return findings
