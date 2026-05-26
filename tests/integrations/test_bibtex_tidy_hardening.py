import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from integrations.tools.bibtex_tidy import BibliographyNormalizer


class TestBibtexTidyHardening:
    """Tests covering resolution priority, minimum-version policy, and backups."""

    @pytest.fixture
    def normalizer(self) -> BibliographyNormalizer:
        return BibliographyNormalizer()

    @pytest.fixture
    def bib_file(self, tmp_path: Path) -> Path:
        bib = tmp_path / "references.bib"
        bib.write_text("@article{test,\n  title = {Test}\n}\n", encoding="utf-8")
        return bib

    # --- Resolution priority ---

    def test_env_override_wins_first(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        custom_bin = tmp_path / "custom-bibtex-tidy"
        custom_bin.touch()
        os.chmod(custom_bin, 0o755)

        with patch.dict(os.environ, {"BIBTEX_TIDY_BIN": str(custom_bin)}):
            resolved = normalizer._resolve_executable({"repo_path": str(tmp_path)})
            assert resolved == (custom_bin, "env")

    def test_invalid_env_override_fails_fast(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        with patch.dict(os.environ, {"BIBTEX_TIDY_BIN": str(tmp_path / "nonexistent")}):
            with pytest.raises(FileNotFoundError, match="BIBTEX_TIDY_BIN"):
                normalizer._resolve_executable({"repo_path": str(tmp_path)})

    def test_local_toolchain_fallback(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        local_dir = tmp_path / "tools" / "node" / "node_modules" / ".bin"
        local_dir.mkdir(parents=True)
        local_bin = local_dir / "bibtex-tidy"
        local_bin.touch()
        os.chmod(local_bin, 0o755)

        with patch.dict(os.environ, {}, clear=True):
            resolved = normalizer._resolve_executable({"repo_path": str(tmp_path)})
            assert resolved == (local_bin, "local")

    def test_global_path_requires_flag(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert normalizer._resolve_executable({"repo_path": str(tmp_path)}) is None

        with patch.dict(os.environ, {"BIBTEX_TIDY_ALLOW_GLOBAL": "true"}):
            with patch("shutil.which", return_value="/usr/bin/bibtex-tidy"):
                resolved = normalizer._resolve_executable({"repo_path": str(tmp_path)})
                assert resolved == (Path("/usr/bin/bibtex-tidy"), "global")

    # --- _parse_version ---

    def test_parse_version_valid(self) -> None:
        assert BibliographyNormalizer._parse_version("1.12.0") == (1, 12, 0)
        assert BibliographyNormalizer._parse_version("v1.11.0") == (1, 11, 0)
        assert BibliographyNormalizer._parse_version("2.0.1") == (2, 0, 1)

    def test_parse_version_malformed(self) -> None:
        assert BibliographyNormalizer._parse_version("abc") is None
        assert BibliographyNormalizer._parse_version("") is None
        assert BibliographyNormalizer._parse_version("  ") is None

    def test_parse_version_single_segment(self) -> None:
        assert BibliographyNormalizer._parse_version("1") == (1,)

    # --- Minimum-version policy ---

    def test_version_at_minimum_passes(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        dummy = tmp_path / "dummy"
        dummy.touch()
        mock = MagicMock(returncode=0, stdout="v1.11.0\n")

        with patch("subprocess.run", return_value=mock):
            ok, msg = normalizer._verify_version(dummy, "local")
            assert ok is True
            assert "1.11.0" in msg

    def test_version_above_minimum_passes(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        dummy = tmp_path / "dummy"
        dummy.touch()

        for ver in ("1.12.0", "v1.13.0", "2.0.0", "1.11.1"):
            mock = MagicMock(returncode=0, stdout=ver + "\n")
            with patch("subprocess.run", return_value=mock):
                ok, _msg = normalizer._verify_version(dummy, "env")
                assert ok is True, f"{ver} should pass"

    def test_version_below_minimum_fails(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        dummy = tmp_path / "dummy"
        dummy.touch()

        for ver in ("1.10.0", "v1.9.0", "0.9.9"):
            mock = MagicMock(returncode=0, stdout=ver + "\n")
            with patch("subprocess.run", return_value=mock):
                ok, msg = normalizer._verify_version(dummy, "local")
                assert ok is False, f"{ver} should fail"
                assert "minimum required" in msg or "unsupported" in msg.lower()

    def test_malformed_version_fails(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        dummy = tmp_path / "dummy"
        dummy.touch()

        for bad in ("abc", "", "  "):
            mock = MagicMock(returncode=0, stdout=bad + "\n")
            with patch("subprocess.run", return_value=mock):
                ok, _msg = normalizer._verify_version(dummy, "env")
                assert ok is False
                assert "malformed" in _msg.lower()

    def test_version_timeout_handled(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        dummy = tmp_path / "dummy"
        dummy.touch()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["--version"], 5)):
            ok, msg = normalizer._verify_version(dummy, "local")
            assert ok is False
            assert "timed out" in msg.lower()

    def test_version_policy_same_for_all_sources(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        """Same minimum applies regardless of source."""
        dummy = tmp_path / "dummy"
        dummy.touch()

        for source in ("local", "env", "global"):
            mock = MagicMock(returncode=0, stdout="v1.11.0\n")
            with patch("subprocess.run", return_value=mock):
                ok, _ = normalizer._verify_version(dummy, source)
                assert ok is True, f"1.11.0 should pass for {source}"

        for source in ("local", "env", "global"):
            mock = MagicMock(returncode=0, stdout="v1.10.0\n")
            with patch("subprocess.run", return_value=mock):
                ok, _ = normalizer._verify_version(dummy, source)
                assert ok is False, f"1.10.0 should fail for {source}"

    # --- Integration ---

    def _sequential_mock(self, ver: str, tidy_out: str) -> MagicMock:
        call_count = 0

        def _run(*a: object, **kw: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(returncode=0, stdout=ver + "\n")
            return MagicMock(returncode=0, stdout=tidy_out)

        return MagicMock(side_effect=_run)

    def test_version_mismatch_prevents_modification(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        custom = tmp_path / "bin"
        custom.touch()
        os.chmod(custom, 0o755)

        mock = MagicMock(returncode=0, stdout="v1.10.0\n")
        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom, "local")),
            patch("subprocess.run", return_value=mock),
        ):
            orig = bib_file.read_text()
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "fail"
        assert "version verification failed" in result.summary
        assert bib_file.read_text() == orig

    def test_subprocess_failure_restores_backup(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        custom = tmp_path / "bin"
        custom.touch()
        os.chmod(custom, 0o755)
        orig = bib_file.read_text()

        call_count = 0

        def _run(*a: object, **kw: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(returncode=0, stdout="v1.11.0\n")
            return MagicMock(returncode=1, stderr="Error\n")

        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom, "local")),
            patch("subprocess.run", side_effect=_run),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "fail"
        assert bib_file.read_text() == orig

    def test_backup_collision_fails_fast(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        custom = tmp_path / "bin"
        custom.touch()
        os.chmod(custom, 0o755)
        collision = bib_file.with_suffix(".bib.bak")
        collision.write_text("stale", encoding="utf-8")

        mock = MagicMock(returncode=0, stdout="v1.11.0\n")
        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom, "local")),
            patch("subprocess.run", return_value=mock),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "fail"
        assert "Backup collision" in result.summary

    def test_degraded_builtin_validation(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        bib_file.write_text(
            "@article{test,\n"
            "  author = {Author},\n"
            "  title = {Title},\n"
            "  journal = {Journal},\n"
            "  year = {2024}\n"
            "}\n",
            encoding="utf-8",
        )
        with patch.object(normalizer, "_resolve_executable", return_value=None):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "pass"
        assert "builtin validation used" in result.summary

    def test_env_v111_passes(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """1.11.0 from env source passes (meets minimum)."""
        custom = tmp_path / "bin"
        custom.touch()
        os.chmod(custom, 0o755)

        run_mock = self._sequential_mock("v1.11.0", "")
        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom, "env")),
            patch("subprocess.run", side_effect=run_mock.side_effect),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "pass"

    def test_global_v111_passes(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """1.11.0 from global source passes (meets minimum)."""
        custom = tmp_path / "bin"
        custom.touch()
        os.chmod(custom, 0o755)

        run_mock = self._sequential_mock("v1.11.0", "")
        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom, "global")),
            patch("subprocess.run", side_effect=run_mock.side_effect),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "pass"

    def test_env_v113_passes(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """1.13.0 passes — previously rejected by allowlist."""
        custom = tmp_path / "bin"
        custom.touch()
        os.chmod(custom, 0o755)

        run_mock = self._sequential_mock("v1.13.0", "")
        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom, "env")),
            patch("subprocess.run", side_effect=run_mock.side_effect),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "pass"

    def test_no_version_mismatch_warning(
        self, normalizer: BibliographyNormalizer, bib_file: Path, tmp_path: Path
    ) -> None:
        """No known_version_mismatch warning — minimum policy makes it unnecessary."""
        custom = tmp_path / "bin"
        custom.touch()
        os.chmod(custom, 0o755)

        bib_file.write_text(
            "@article{test,\n"
            "  author = {Author},\n"
            "  title = {Title},\n"
            "  journal = {Journal},\n"
            "  year = {2024}\n"
            "}\n",
            encoding="utf-8",
        )

        run_mock = self._sequential_mock("v1.11.0", "")
        with (
            patch.object(normalizer, "_resolve_executable", return_value=(custom, "local")),
            patch("subprocess.run", side_effect=run_mock.side_effect),
        ):
            result = normalizer.run({"bibliography": str(bib_file)}, {"repo_path": str(tmp_path)})

        assert result.status == "pass"
        assert "normalized successfully" in result.summary
        warnings = [f for f in result.findings if f["code"] == "known_version_mismatch"]
        assert len(warnings) == 0

    def test_real_local_toolchain_resolves(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        local_dir = tmp_path / "tools" / "node" / "node_modules" / ".bin"
        local_dir.mkdir(parents=True)
        local_bin = local_dir / "bibtex-tidy"
        local_bin.write_text("#!/bin/sh\necho v1.12.0\n", encoding="utf-8")
        os.chmod(local_bin, 0o755)

        with patch.dict(os.environ, {}, clear=True):
            resolved = normalizer._resolve_executable({"repo_path": str(tmp_path)})
            assert resolved is not None
            assert resolved[1] == "local"

    def test_no_toolchain_returns_none(
        self, normalizer: BibliographyNormalizer, tmp_path: Path
    ) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert normalizer._resolve_executable({"repo_path": str(tmp_path)}) is None
