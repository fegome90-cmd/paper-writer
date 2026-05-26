import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from integrations.tools.bibtex_tidy import BibliographyNormalizer


class TestBibtexTidyHardening:
    """Rigorous tests covering resolution priority, version checks, and backups."""

    @pytest.fixture
    def normalizer(self) -> BibliographyNormalizer:
        return BibliographyNormalizer()

    @pytest.fixture
    def bib_file(self, tmp_path: Path) -> Path:
        bib = tmp_path / "references.bib"
        bib.write_text("@article{test,\n  title = {Test}\n}\n", encoding="utf-8")
        return bib

    def test_env_override_wins_first(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        """BIBTEX_TIDY_BIN override must bypass local toolchain and return if valid."""
        custom_bin = tmp_path / "custom-bibtex-tidy"
        custom_bin.touch()
        os.chmod(custom_bin, 0o755)

        with patch.dict(os.environ, {"BIBTEX_TIDY_BIN": str(custom_bin)}):
            resolved = normalizer._resolve_executable({"repo_path": str(tmp_path)})
            assert resolved == (custom_bin, "env")

    def test_invalid_env_override_fails_fast(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        """If BIBTEX_TIDY_BIN is invalid, it must fail fast and NOT fall back."""
        invalid_bin = tmp_path / "nonexistent-bin"

        with patch.dict(os.environ, {"BIBTEX_TIDY_BIN": str(invalid_bin)}):
            with pytest.raises(FileNotFoundError, match="BIBTEX_TIDY_BIN specified but not found"):
                normalizer._resolve_executable({"repo_path": str(tmp_path)})

    def test_local_toolchain_fallback_when_env_absent(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        """If BIBTEX_TIDY_BIN is absent, the wrapper resolves the local toolchain binary."""
        local_dir = tmp_path / "tools" / "node" / "node_modules" / ".bin"
        local_dir.mkdir(parents=True)
        local_bin = local_dir / "bibtex-tidy"
        local_bin.touch()
        os.chmod(local_bin, 0o755)

        with patch.dict(os.environ, {}, clear=True):
            resolved = normalizer._resolve_executable({"repo_path": str(tmp_path)})
            assert resolved == (local_bin, "local")

    def test_global_path_ignored_unless_explicitly_allowed(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        """If no override or local exists, global PATH is ignored unless ALLOW_GLOBAL is true."""
        with patch.dict(os.environ, {}, clear=True):
            resolved = normalizer._resolve_executable({"repo_path": str(tmp_path)})
            assert resolved is None

        # Check that it resolves via PATH when allowed
        with patch.dict(os.environ, {"BIBTEX_TIDY_ALLOW_GLOBAL": "true"}):
            with patch("shutil.which", return_value="/usr/bin/bibtex-tidy"):
                resolved = normalizer._resolve_executable({"repo_path": str(tmp_path)})
                assert resolved == (Path("/usr/bin/bibtex-tidy"), "global")

    def test_version_match_succeeds(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        """Version check succeeds when output matches 1.11.0."""
        dummy_bin = tmp_path / "dummy-tidy"
        dummy_bin.touch()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "v1.11.0\n"

        with patch("subprocess.run", return_value=mock_process) as mock_run:
            ok, msg = normalizer._verify_version(dummy_bin, "local")
            assert ok is True
            assert msg == "1.11.0"
            mock_run.assert_called_once_with(
                [str(dummy_bin), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )

    def test_version_mismatch_prevents_file_modification(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """If version does not match, run() fails without modifying the bib file."""
        custom_bin = tmp_path / "custom-bin"
        custom_bin.touch()
        os.chmod(custom_bin, 0o755)

        # Mock resolve and verify_version to mismatch
        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom_bin, "local")),
            patch.object(
                normalizer,
                "_verify_version",
                return_value=(False, "Version mismatch: expected 1.11.0, got 1.10.0"),
            ),
        ):
            orig_content = bib_file.read_text(encoding="utf-8")
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

            assert result.status == "fail"
            assert "version verification failed" in result.summary
            assert any("Version mismatch" in f["message"] for f in result.findings)
            assert bib_file.read_text(encoding="utf-8") == orig_content

    def test_version_command_failure_handled(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        """If the version check process fails or timeouts, it is reported as a failure."""
        dummy_bin = tmp_path / "dummy-tidy"
        dummy_bin.touch()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["--version"], 5)):
            ok, msg = normalizer._verify_version(dummy_bin, "local")
            assert ok is False
            assert "version check" in msg.lower()

    def test_subprocess_failure_restores_original_from_backup(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """If bibtex-tidy returns non-zero exit code, the original bib is restored from backup."""
        custom_bin = tmp_path / "custom-bin"
        custom_bin.touch()
        os.chmod(custom_bin, 0o755)

        orig_content = bib_file.read_text(encoding="utf-8")

        # Mock subprocess run to fail
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = "Syntax Error on line 2\n"

        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom_bin, "local")),
            patch.object(normalizer, "_verify_version", return_value=(True, "1.11.0")),
            patch("subprocess.run", return_value=mock_process),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "fail"
        assert "restored bibliography from backup" in result.summary.lower()
        # Verify content was restored (original file unchanged)
        assert bib_file.read_text(encoding="utf-8") == orig_content
        # Backup should be deleted
        assert not bib_file.with_suffix(".bib.bak").exists()

    def test_backup_collision_fails_fast(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """If references.bib.bak already exists, run() must fail fast before write new backup."""
        custom_bin = tmp_path / "custom-bin"
        custom_bin.touch()
        os.chmod(custom_bin, 0o755)

        # Pre-create backup collision file
        collision_file = bib_file.with_suffix(".bib.bak")
        collision_file.write_text("Stale backup content", encoding="utf-8")

        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom_bin, "local")),
            patch.object(normalizer, "_verify_version", return_value=(True, "1.11.0")),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "fail"
        assert "Backup collision detected" in result.summary
        assert collision_file.read_text(encoding="utf-8") == "Stale backup content"

    def test_unresolved_binary_produces_degraded_builtin_result(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """If no binary resolves, falls back to built-in validation reporting degraded status."""
        bib_file.write_text(
            "@article{test,\n"
            "  author = {John Doe},\n"
            "  title = {Test},\n"
            "  journal = {Journal of Tests},\n"
            "  year = {2024}\n"
            "}\n",
            encoding="utf-8",
        )
        with patch.object(normalizer, "_resolve_executable", return_value=None):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "pass"  # valid file contents
        assert "normalization skipped / builtin validation used" in result.summary

    def test_local_toolchain_emits_known_version_mismatch_warning(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """If local toolchain resolves and CLI reports 1.11.0, run succeeds with a warning."""
        custom_bin = tmp_path / "custom-bin"
        custom_bin.touch()
        os.chmod(custom_bin, 0o755)

        # Write a fully valid bib entry
        bib_file.write_text(
            "@article{test,\n"
            "  author = {John Doe},\n"
            "  title = {Test},\n"
            "  journal = {Journal of Tests},\n"
            "  year = {2024}\n"
            "}\n",
            encoding="utf-8",
        )

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""

        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom_bin, "local")),
            patch.object(normalizer, "_verify_version", return_value=(True, "1.11.0")),
            patch("subprocess.run", return_value=mock_process),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "pass"
        assert "known version mismatch" in result.summary.lower()
        warnings = [f for f in result.findings if f["code"] == "known_version_mismatch"]
        assert len(warnings) == 1

    def test_env_override_v111_fails(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """If env override is used but reports 1.11.0, validation must fail."""
        custom_bin = tmp_path / "custom-bin"
        custom_bin.touch()
        os.chmod(custom_bin, 0o755)

        # Mock resolve to be env source
        mock_run = MagicMock()
        mock_run.returncode = 0
        mock_run.stdout = "v1.11.0\n"

        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom_bin, "env")),
            patch("subprocess.run", return_value=mock_run),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "fail"
        assert "version verification failed" in result.summary
        assert any("expected exactly 1.12.0" in f["message"] for f in result.findings)

    def test_global_path_v111_fails(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """If global path is allowed but reports 1.11.0, validation must fail."""
        custom_bin = tmp_path / "custom-bin"
        custom_bin.touch()
        os.chmod(custom_bin, 0o755)

        # Mock resolve to be global source
        mock_run = MagicMock()
        mock_run.returncode = 0
        mock_run.stdout = "v1.11.0\n"

        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom_bin, "global")),
            patch("subprocess.run", return_value=mock_run),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "fail"
        assert "version verification failed" in result.summary
        assert any("expected exactly 1.12.0" in f["message"] for f in result.findings)
