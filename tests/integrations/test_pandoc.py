"""Tests for the Pandoc rendering wrapper.

Uses mocks for shutil.which and subprocess.run to avoid requiring
a real Pandoc/LaTeX installation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.ports.tool_wrapper import ToolNotAvailableError
from integrations.tools.pandoc import PandocRenderer


@pytest.fixture
def renderer() -> PandocRenderer:
    return PandocRenderer()


class TestPandocProperties:
    """Test basic properties of the PandocRenderer."""

    def test_name_property(self, renderer: PandocRenderer) -> None:
        assert renderer.name == "pandoc-renderer"

    def test_gate_property(self, renderer: PandocRenderer) -> None:
        assert renderer.gate == "render_passed"

    def test_is_available_returns_bool(self, renderer: PandocRenderer) -> None:
        result = renderer.is_available()
        assert isinstance(result, bool)


class TestPandocNotAvailable:
    """Test behaviour when Pandoc is not installed."""

    @patch("integrations.tools.pandoc.shutil.which", return_value=None)
    def test_run_raises_tool_not_available(
        self, mock_which: MagicMock, renderer: PandocRenderer, tmp_path: Path
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")
        with pytest.raises(ToolNotAvailableError, match="pandoc"):
            renderer.run({"manuscript": str(manuscript)}, {})

    @patch("integrations.tools.pandoc.shutil.which", return_value=None)
    def test_is_available_false(self, mock_which: MagicMock) -> None:
        assert PandocRenderer().is_available() is False


class TestPandocMissingArtifact:
    """Test behaviour when manuscript artifact is missing."""

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_no_manuscript_key_raises(self, mock_which: MagicMock) -> None:
        renderer = PandocRenderer()
        with pytest.raises(ValueError, match="Missing 'manuscript'"):
            renderer.run({}, {})

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    def test_missing_manuscript_file_raises(self, mock_which: MagicMock, tmp_path: Path) -> None:
        renderer = PandocRenderer()
        with pytest.raises(ValueError, match="not found"):
            renderer.run({"manuscript": str(tmp_path / "nonexistent.md")}, {})


class TestPandocSuccess:
    """Test successful Pandoc rendering."""

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_run_both_formats_succeeds(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title\n\nContent.")

        # Simulate that output files exist after subprocess.run
        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            # Find the -o argument to determine output path
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("rendered")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_run.side_effect = fake_run
        result = renderer.run({"manuscript": str(manuscript)}, {})
        assert result.status == "pass"
        assert result.validator == "pandoc-renderer"
        # Verification warnings for tiny test artifacts are expected
        verify_warnings = [f for f in result.findings if f["code"].startswith("render_artifact_")]
        assert len(verify_warnings) > 0  # Small test files trigger verification

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_run_with_bibliography(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")
        bib = tmp_path / "references.bib"
        bib.write_text("@article{a, year={2024}}")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("rendered")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_run.side_effect = fake_run
        result = renderer.run(
            {"manuscript": str(manuscript), "bibliography": str(bib)},
            {},
        )
        assert result.status == "pass"
        # Verify bibliography is passed to command
        for call_args in mock_run.call_args_list:
            cmd = call_args[0][0]
            assert "--bibliography" in cmd


class TestPandocFailure:
    """Test Pandoc rendering failures."""

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_docx_failure_overall_fail(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 1
            result.stderr = "pandoc error"
            return result

        mock_run.side_effect = fake_run
        result = renderer.run({"manuscript": str(manuscript)}, {})
        assert result.status == "fail"

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_subprocess_exception_fails(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")
        mock_run.side_effect = OSError("subprocess crashed")
        result = renderer.run({"manuscript": str(manuscript)}, {})
        assert result.status == "fail"

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_docx_succeeds_pdf_fails_warns(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")

        call_count = 0

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            output_path = Path(cmd[cmd.index("-o") + 1])

            if call_count == 1:
                # First call: DOCX succeeds
                result.returncode = 0
                result.stderr = ""
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("rendered")
            else:
                # Second call: PDF fails (no LaTeX)
                result.returncode = 1
                result.stderr = "pdf engine not found"
            return result

        mock_run.side_effect = fake_run
        result = renderer.run({"manuscript": str(manuscript)}, {})
        assert result.status == "warn"
        assert any("pdf" in f["message"].lower() for f in result.findings)


class TestPandocMultiOutput:
    """Tests for multi-output rendering with format selection."""

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_single_format_docx_only(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("rendered")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_run.side_effect = fake_run
        result = renderer.run(
            {"manuscript": str(manuscript), "output_formats": ["docx"]},
            {},
        )
        assert result.status == "pass"
        assert mock_run.call_count == 1

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_csl_flag_passed_to_command(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")
        csl = tmp_path / "vancouver.csl"
        csl.write_text('<style xmlns="http://purl.org/net/xbiblio/csl"></style>')

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("rendered")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_run.side_effect = fake_run
        result = renderer.run(
            {"manuscript": str(manuscript), "csl": str(csl), "output_formats": ["docx"]},
            {},
        )
        assert result.status == "pass"
        # Verify CSL is in the command
        cmd = mock_run.call_args[0][0]
        assert "--csl" in cmd

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_reference_doc_passed_for_docx(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")
        ref_doc = tmp_path / "template.docx"
        ref_doc.write_bytes(b"PK fake docx")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("rendered")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_run.side_effect = fake_run
        result = renderer.run(
            {
                "manuscript": str(manuscript),
                "reference_doc": str(ref_doc),
                "output_formats": ["docx"],
            },
            {},
        )
        assert result.status == "pass"
        cmd = mock_run.call_args[0][0]
        assert "--reference-doc" in cmd

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_reference_doc_not_passed_for_pdf(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")
        ref_doc = tmp_path / "template.docx"
        ref_doc.write_bytes(b"PK fake docx")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("rendered")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_run.side_effect = fake_run
        result = renderer.run(
            {
                "manuscript": str(manuscript),
                "reference_doc": str(ref_doc),
                "output_formats": ["pdf"],
            },
            {},
        )
        assert result.status == "pass"
        cmd = mock_run.call_args[0][0]
        assert "--reference-doc" not in cmd

    @patch("integrations.tools.pandoc.shutil.which", return_value="/usr/bin/pandoc")
    @patch("integrations.tools.pandoc.subprocess.run")
    def test_unknown_format_filtered_out(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        renderer: PandocRenderer,
        tmp_path: Path,
    ) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Title")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("rendered")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_run.side_effect = fake_run
        renderer = renderer
        renderer.run(
            {
                "manuscript": str(manuscript),
                "output_formats": ["docx", "epub"],
            },
            {},
        )
        # epub should be filtered out, only docx rendered
        assert mock_run.call_count == 1
