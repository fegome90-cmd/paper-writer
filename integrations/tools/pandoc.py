"""Pandoc rendering wrapper.

Runs Pandoc to produce .docx and .pdf from manuscript sources.
Supports CSL citation styles and reference doc templates.
Returns structured findings for the render_passed gate.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

from harness.ports.tool_wrapper import ToolNotAvailableError, ToolWrapper, ValidatorResult

# Supported output formats and their extensions
SUPPORTED_FORMATS: dict[str, str] = {
    "docx": ".docx",
    "pdf": ".pdf",
}

# Default formats when output_formats is not specified
DEFAULT_FORMATS: list[str] = ["docx", "pdf"]


class PandocRenderer(ToolWrapper):
    """Renders manuscript to .docx and .pdf via Pandoc.

    Uses Pandoc if installed. Falls back to docx-only output if
    LaTeX (required for PDF) is not available.

    Supports:
    - ``output_formats``: list of formats to render (default: docx, pdf)
    - ``csl``: path to a CSL citation style file
    - ``reference_doc``: path to a reference docx for styling
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
        csl = artifacts.get("csl")
        reference_doc = artifacts.get("reference_doc")
        output_formats = self._resolve_formats(artifacts)

        output_dir.mkdir(parents=True, exist_ok=True)

        artifacts_checked: list[str] = [str(manuscript)]
        findings: list[dict[str, Any]] = []

        # Render each requested format
        results: dict[str, bool] = {}
        for fmt in output_formats:
            ext = SUPPORTED_FORMATS.get(fmt, f".{fmt}")
            output_path = output_dir / f"manuscript{ext}"
            ok = self._render_format(
                manuscript,
                output_path,
                bibliography,
                csl,
                reference_doc,
                artifacts_checked,
                findings,
            )
            results[fmt] = ok

        # Determine status: docx must succeed, pdf is optional
        docx_ok = results.get("docx", False)
        pdf_ok = results.get("pdf", True)  # No pdf requested = not a failure

        if not docx_ok and "docx" in output_formats:
            status = "fail"
        elif not pdf_ok and "pdf" in output_formats:
            status = "warn"
        else:
            status = "pass"

        summary = self._build_summary(results, output_dir, output_formats)
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

    @staticmethod
    def _resolve_formats(artifacts: dict[str, Any]) -> list[str]:
        """Determine which formats to render from artifacts."""
        formats = artifacts.get("output_formats")
        if formats and isinstance(formats, list):
            return [f for f in formats if f in SUPPORTED_FORMATS]
        return DEFAULT_FORMATS

    def _render_format(
        self,
        manuscript: Path,
        output_path: Path,
        bibliography: str | None,
        csl: str | None,
        reference_doc: str | None,
        artifacts_checked: list[str],
        findings: list[dict[str, Any]],
    ) -> bool:
        """Run Pandoc for a single output format. Returns True on success."""
        cmd = self._build_command(manuscript, output_path, bibliography, csl, reference_doc)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
            if result.returncode == 0 and output_path.exists():
                artifacts_checked.append(str(output_path))
                self._verify_render_artifact(output_path, findings)
                return True

            msg = result.stderr.strip() or f"Pandoc exited with code {result.returncode}"
            findings.append(
                {
                    "code": "pandoc_render_error",
                    "severity": "warning" if output_path.suffix == ".pdf" else "error",
                    "message": f"Failed to render {output_path.suffix}: {msg}",
                    "artifact": str(output_path),
                }
            )
            return False

        except subprocess.TimeoutExpired:
            findings.append(
                {
                    "code": "pandoc_timeout",
                    "severity": "error",
                    "message": f"Pandoc timed out rendering {output_path.suffix}.",
                    "artifact": str(output_path),
                }
            )
            return False
        except (OSError, subprocess.SubprocessError) as exc:
            findings.append(
                {
                    "code": "pandoc_error",
                    "severity": "error",
                    "message": (f"Unexpected error rendering {output_path.suffix}: {exc}"),
                    "artifact": str(output_path),
                }
            )
            return False

    @staticmethod
    def _verify_render_artifact(output_path: Path, findings: list[dict[str, Any]]) -> None:
        """Verify rendered artifact integrity after Pandoc completes."""
        size = output_path.stat().st_size
        if size < 500:
            findings.append(
                {
                    "code": "render_artifact_too_small",
                    "severity": "warning",
                    "message": f"Rendered {output_path.name} is only {size}B — likely empty.",
                    "artifact": str(output_path),
                }
            )

        if output_path.suffix == ".docx":
            # DOCX must be a valid ZIP containing word/document.xml
            import zipfile

            try:
                with zipfile.ZipFile(output_path, "r") as zf:
                    names = zf.namelist()
                    if "word/document.xml" not in names:
                        findings.append(
                            {
                                "code": "render_artifact_malformed_docx",
                                "severity": "error",
                                "message": (
                                    "DOCX missing word/document.xml — not a valid Word file."
                                ),
                                "artifact": str(output_path),
                            }
                        )
            except zipfile.BadZipFile:
                findings.append(
                    {
                        "code": "render_artifact_not_zip",
                        "severity": "error",
                        "message": "DOCX is not a valid ZIP file.",
                        "artifact": str(output_path),
                    }
                )

    @staticmethod
    def _build_command(
        manuscript: Path,
        output_path: Path,
        bibliography: str | None,
        csl: str | None = None,
        reference_doc: str | None = None,
    ) -> list[str]:
        """Construct the Pandoc command-line invocation."""
        cmd: list[str] = ["pandoc", str(manuscript)]
        if bibliography:
            cmd.extend(["--bibliography", bibliography])
        if csl:
            csl_path = Path(csl)
            if csl_path.is_file():
                cmd.extend(["--csl", str(csl_path)])
        if reference_doc:
            ref_path = Path(reference_doc)
            if ref_path.is_file() and output_path.suffix == ".docx":
                cmd.extend(["--reference-doc", str(ref_path)])
        cmd.extend(["-o", str(output_path)])
        return cmd

    @staticmethod
    def _build_summary(
        results: dict[str, bool],
        output_dir: Path,
        requested_formats: list[str],
    ) -> str:
        """Produce a human-readable summary of the rendering outcome."""
        parts: list[str] = []
        for fmt in requested_formats:
            ext = SUPPORTED_FORMATS.get(fmt, f".{fmt}")
            if results.get(fmt, False):
                parts.append(f"{fmt.upper()} → {output_dir / f'manuscript{ext}'}")
            else:
                reason = "failed" if fmt == "docx" else "skipped (missing LaTeX or error)"
                parts.append(f"{fmt.upper()}: {reason}")
        return "Pandoc render: " + "; ".join(parts)
