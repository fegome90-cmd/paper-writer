"""Tests for paper doctor and degraded mode behavior."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from harness.services.doctor import (
    ToolStatus,
    check_all_tools,
    check_internal_capabilities,
    format_doctor_report,
)


class TestDoctorCheckTool:
    """Tests for individual tool checking."""

    @patch("harness.services.doctor.shutil.which", return_value="/usr/bin/pandoc")
    def test_installed_tool(self, mock_which: MagicMock) -> None:
        from harness.services.doctor import check_tool

        status = check_tool("pandoc")
        assert status.installed is True

    @patch("harness.services.doctor.shutil.which", return_value=None)
    def test_missing_tool(self, mock_which: MagicMock) -> None:
        from harness.services.doctor import check_tool

        status = check_tool("vale")
        assert status.installed is False
        assert "brew install vale" in status.install_hint


class TestDoctorCheckAll:
    """Tests for check_all_tools."""

    @patch("harness.services.doctor.shutil.which", return_value=None)
    def test_all_missing(self, mock_which: MagicMock) -> None:
        tools = check_all_tools()
        assert len(tools) == 4
        assert all(not t.installed for t in tools)
        assert all(t.degraded_message for t in tools)


class TestDoctorInternalCaps:
    """Tests for internal capability checks."""

    def test_with_styles_and_presets(self, tmp_path: Path) -> None:
        # Create fake structure
        styles_dir = tmp_path / "styles" / "vale" / "paper-writer"
        styles_dir.mkdir(parents=True)
        (styles_dir / "Test.yml").write_text("test: true")

        csl_dir = tmp_path / "styles" / "csl"
        csl_dir.mkdir(parents=True)
        (csl_dir / "test.csl").write_text("<style/>")

        journals_dir = tmp_path / "templates" / "journals" / "nature"
        journals_dir.mkdir(parents=True)
        (journals_dir / "preset.yaml").write_text("name: nature")

        caps = check_internal_capabilities(tmp_path)
        assert all(c.installed for c in caps)

    def test_empty_repo(self, tmp_path: Path) -> None:
        caps = check_internal_capabilities(tmp_path)
        assert all(not c.installed for c in caps)


class TestDoctorReport:
    """Tests for report formatting."""

    def test_report_with_degraded(self) -> None:
        tools = [
            ToolStatus(
                name="pandoc",
                installed=True,
                version="3.9",
                required_for=["render"],
            ),
            ToolStatus(
                name="vale",
                installed=False,
                install_hint="brew install vale",
                required_for=["style linting"],
                degraded_message="DEGRADED: vale not found.",
            ),
        ]
        caps = [
            ToolStatus(
                name="csl-styles",
                installed=True,
                version="2 styles",
            ),
        ]
        report = format_doctor_report(tools, caps)
        assert "DEGRADED MODE ACTIVE" in report
        assert "vale" in report

    def test_report_all_ok(self) -> None:
        tools = [
            ToolStatus(name="pandoc", installed=True, version="3.9"),
        ]
        caps = [
            ToolStatus(name="csl-styles", installed=True, version="2 styles"),
        ]
        report = format_doctor_report(tools, caps)
        assert "ALL TOOLS AVAILABLE" in report


class TestDegradedModeInWrappers:
    """Tests that wrappers emit degraded_mode warnings."""

    def test_style_linter_emits_degraded_warning(self, tmp_path: Path) -> None:
        from integrations.tools.vale import StyleLinter

        mf = tmp_path / "test.md"
        mf.write_text("The data was collected. This proves that X is true.")

        linter = StyleLinter()
        with patch.object(linter, "_vale_available", return_value=False):
            result = linter.run(
                {"manuscript_files": [str(mf)]},
                {},
            )

        degraded = [f for f in result.findings if f["code"] == "degraded_mode"]
        assert len(degraded) == 1
        assert "Vale not installed" in degraded[0]["message"]
        assert "brew install vale" in degraded[0]["message"]

    def test_bibtex_tidy_emits_degraded_warning(self, tmp_path: Path) -> None:
        from integrations.tools.bibtex_tidy import BibliographyNormalizer

        bib = tmp_path / "refs.bib"
        bib.write_text(
            "@article{a2024,\n"
            "  author = {A},\n"
            "  title = {T},\n"
            "  journal = {J},\n"
            "  year = {2024},\n"
            "  doi = {10.1234/a},\n"
            "}\n"
        )

        normalizer = BibliographyNormalizer()
        with patch.object(normalizer, "_resolve_executable", return_value=None):
            result = normalizer.run(
                {"bibliography": str(bib)},
                {},
            )

        degraded = [f for f in result.findings if f["code"] == "degraded_mode"]
        assert len(degraded) == 1
        assert "bibtex-tidy not installed" in degraded[0]["message"]
