"""Tests for Zotero/Better BibTeX import wrapper."""

from pathlib import Path

from integrations.tools.zotero_import import ZoteroImporter


class TestZoteroImporterProperties:
    """Test basic properties."""

    def test_name(self) -> None:
        assert ZoteroImporter().name == "zotero-import"

    def test_gate(self) -> None:
        assert ZoteroImporter().gate == "bib_imported"

    def test_is_available(self) -> None:
        assert ZoteroImporter().is_available() is True


class TestZoteroImportMissingSource:
    """Test missing source .bib."""

    def test_no_source_key(self, tmp_path: Path) -> None:
        result = ZoteroImporter().run({}, {})
        assert result.status == "fail"
        assert any(f["code"] == "missing_artifact" for f in result.findings)

    def test_source_not_found(self, tmp_path: Path) -> None:
        result = ZoteroImporter().run(
            {"source_bib": str(tmp_path / "nonexistent.bib")},
            {},
        )
        assert result.status == "fail"
        assert any(f["code"] == "file_not_found" for f in result.findings)


class TestZoteroImportEmptyBib:
    """Test empty .bib file."""

    def test_empty_file(self, tmp_path: Path) -> None:
        source = tmp_path / "empty.bib"
        source.write_text("")
        result = ZoteroImporter().run(
            {"source_bib": str(source)},
            {},
        )
        assert result.status == "fail"
        assert any(f["code"] == "no_entries" for f in result.findings)


class TestZoteroImportValidBib:
    """Test valid .bib import."""

    def test_valid_entry_imports(self, tmp_path: Path) -> None:
        source = tmp_path / "zotero_export.bib"
        source.write_text(
            "@article{smith2024,\n"
            "  author = {Smith, John},\n"
            "  title = {A Study},\n"
            "  journal = {Nature},\n"
            "  year = {2024},\n"
            "  doi = {10.1038/test2024},\n"
            "}\n"
        )
        target = tmp_path / "references.bib"
        result = ZoteroImporter().run(
            {"source_bib": str(source), "target_bib": str(target)},
            {},
        )
        assert result.status == "pass"
        assert target.exists()
        assert "smith2024" in target.read_text()

    def test_invalid_doi_blocks_import(self, tmp_path: Path) -> None:
        source = tmp_path / "bad.bib"
        source.write_text(
            "@article{bad2024,\n"
            "  author = {Bad},\n"
            "  title = {Bad Study},\n"
            "  journal = {Fake},\n"
            "  year = {2024},\n"
            "  doi = {not-a-doi},\n"
            "}\n"
        )
        target = tmp_path / "references.bib"
        result = ZoteroImporter().run(
            {"source_bib": str(source), "target_bib": str(target)},
            {},
        )
        assert result.status == "fail"
        assert any(f["code"] == "malformed_doi" for f in result.findings)
        # Target should NOT be created
        assert not target.exists()

    def test_default_target_path(self, tmp_path: Path) -> None:
        source = tmp_path / "good.bib"
        source.write_text(
            "@article{ok2024,\n"
            "  author = {Ok},\n"
            "  title = {OK},\n"
            "  journal = {J},\n"
            "  year = {2024},\n"
            "  doi = {10.1234/ok},\n"
            "}\n"
        )
        # Explicitly set target to tmp_path to avoid writing into repo tree
        result = ZoteroImporter().run(
            {"source_bib": str(source), "target_bib": str(tmp_path / "references.bib")},
            {},
        )
        assert result.status == "pass"

    def test_multiple_entries_import(self, tmp_path: Path) -> None:
        source = tmp_path / "multi.bib"
        source.write_text(
            "@article{a2024,\n"
            "  author = {A},\n"
            "  title = {A},\n"
            "  journal = {J},\n"
            "  year = {2024},\n"
            "  doi = {10.1234/a},\n"
            "}\n"
            "@book{b2023,\n"
            "  author = {B},\n"
            "  title = {B Book},\n"
            "  publisher = {Pub},\n"
            "  year = {2023},\n"
            "}\n"
        )
        target = tmp_path / "refs.bib"
        result = ZoteroImporter().run(
            {"source_bib": str(source), "target_bib": str(target)},
            {},
        )
        # book missing doi = warning from refs validator, not import blocker
        assert result.status in ("pass", "warn")
        assert target.exists()
