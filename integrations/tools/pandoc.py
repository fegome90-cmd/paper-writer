"""Pandoc rendering wrapper.

Runs Pandoc to produce .docx and .pdf from manuscript sources.
Returns structured findings for the render_passed gate.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

from harness.ports.tool_wrapper import ToolNotAvailableError, ToolWrapper, ValidatorResult


class PandocRenderer(ToolWrapper):
    """Renders manuscript to .docx and .pdf via Pandoc.

    Uses Pandoc if installed. Falls back to docx-only output if
    LaTeX (required for PDF) is not available.
    """

    @property
    def name(self) -> str:
        return "pandoc-renderer"

    @property
    def gate(self) -> str:
        return "render_passed"

    def is_available(self) -> bool:
        """Check if ``pandoc`` is discoverable on PATH."""
        return shutil.which("pandoc") is not None

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        """Render manuscript via Pandoc and return a structured result.

        Raises:
            ToolNotAvailableError: If ``pandoc`` is not on PATH.
        """
        if not self.is_available():
            raise ToolNotAvailableError("pandoc", "brew install pandoc")

        manuscript = self._resolve_manuscript(artifacts)
        output_dir = self._resolve_output_dir(artifacts, manuscript)
        bibliography = artifacts.get("bibliography")
        output_dir.mkdir(parents=True, exist_ok=True)

        artifacts_checked: list[str] = [str(manuscript)]
        findings: list[dict[str, Any]] = []

        # --- Render DOCX ---
        docx_path = output_dir / "manuscript.docx"
        docx_ok = self._render_format(
            manuscript, docx_path, bibliography, artifacts_checked, findings
        )

        # --- Render PDF ---
        pdf_path = output_dir / "manuscript.pdf"
        pdf_ok = self._render_format(
            manuscript, pdf_path, bibliography, artifacts_checked, findings
        )

        # Determine status
        if not docx_ok:
            status = "fail"
        elif not pdf_ok:
            status = "warn"
        else:
            status = "pass"

        summary = self._build_summary(docx_ok, pdf_ok, output_dir)
        return ValidatorResult(
            validator="pandoc-renderer",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_manuscript(artifacts: dict[str, Any]) -> Path:
        """Extract and validate the manuscript path from artifacts."""
        manuscript = artifacts.get("manuscript")
        if not manuscript:
            raise ValueError("Missing 'manuscript' in artifacts.")
        manuscript_path = Path(manuscript)
        if not manuscript_path.is_file():
            raise ValueError(f"Manuscript file not found: {manuscript}")
        return manuscript_path

    @staticmethod
    def _resolve_output_dir(artifacts: dict[str, Any], manuscript: Path) -> Path:
        """Determine the output directory from artifacts or manuscript location."""
        output_dir = artifacts.get("output_dir")
        if output_dir:
            return Path(output_dir)
        return manuscript.parent.parent / "render"

    def _render_format(
        self,
        manuscript: Path,
        output_path: Path,
        bibliography: str | None,
        artifacts_checked: list[str],
        findings: list[dict[str, Any]],
    ) -> bool:
        """Run Pandoc for a single output format. Returns True on success."""
        cmd = self._build_command(manuscript, output_path, bibliography)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120, check=False
            )
            if result.returncode == 0 and output_path.exists():
                artifacts_checked.append(str(output_path))
                return True

            msg = result.stderr.strip() or f"Pandoc exited with code {result.returncode}"
            findings.append({
                "code": "pandoc_render_error",
                "severity": "warning" if output_path.suffix == ".pdf" else "error",
                "message": f"Failed to render {output_path.suffix}: {msg}",
                "artifact": str(output_path),
            })
            return False

        except subprocess.TimeoutExpired:
            findings.append({
                "code": "pandoc_timeout",
                "severity": "error",
                "message": f"Pandoc timed out rendering {output_path.suffix}.",
                "artifact": str(output_path),
            })
            return False
        except Exception as exc:
            findings.append({
                "code": "pandoc_error",
                "severity": "error",
                "message": f"Unexpected error rendering {output_path.suffix}: {exc}",
                "artifact": str(output_path),
            })
            return False

    @staticmethod
    def _build_command(
        manuscript: Path, output_path: Path, bibliography: str | None
    ) -> list[str]:
        """Construct the Pandoc command-line invocation."""
        cmd: list[str] = ["pandoc", str(manuscript)]
        if bibliography:
            cmd.extend(["--bibliography", bibliography])
        cmd.extend(["-o", str(output_path)])
        return cmd

    @staticmethod
    def _build_summary(docx_ok: bool, pdf_ok: bool, output_dir: Path) -> str:
        """Produce a human-readable summary of the rendering outcome."""
        parts: list[str] = []
        if docx_ok:
            parts.append(f"DOCX → {output_dir / 'manuscript.docx'}")
        else:
            parts.append("DOCX: failed")
        if pdf_ok:
            parts.append(f"PDF → {output_dir / 'manuscript.pdf'}")
        else:
            parts.append("PDF: skipped (missing LaTeX or pandoc error)")
        return "Pandoc render: " + "; ".join(parts)
