"""Tests for runtime asset resolution and packaging portability.

Verifies that:
- Asset resolver finds bundled templates and styles
- Preset 'nature' resolves from package context
- Vale styles path resolves
- CSL styles path resolves
- Fallback behavior is clear when assets don't exist
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from harness.ports.assets import (
    get_asset_path,
    get_csl_styles_dir,
    get_preset_dir,
    get_styles_dir,
    get_templates_dir,
    get_vale_styles_dir,
)


class TestAssetResolver:
    """Test the centralized asset resolver."""

    def test_get_templates_dir_returns_path(self) -> None:
        result = get_templates_dir()
        assert isinstance(result, Path)
        assert result.name == "templates"

    def test_get_styles_dir_returns_path(self) -> None:
        result = get_styles_dir()
        assert isinstance(result, Path)
        assert result.name == "styles"

    def test_get_asset_path_returns_path_even_if_missing(self) -> None:
        result = get_asset_path("nonexistent", "asset.txt")
        assert isinstance(result, Path)
        assert not result.exists()  # It should NOT crash, just return path

    def test_get_asset_path_with_existing_file(self) -> None:
        result = get_asset_path("templates", "manuscript.qmd")
        assert result.exists()
        assert result.is_file()
        assert result.suffix == ".qmd"

    def test_get_asset_path_with_existing_bib(self) -> None:
        result = get_asset_path("templates", "references.bib")
        assert result.exists()
        assert result.is_file()


class TestPresetResolution:
    """Test journal preset resolution."""

    def test_nature_preset_dir_resolves(self) -> None:
        preset_dir = get_preset_dir("nature")
        assert preset_dir.exists()
        assert preset_dir.is_dir()

    def test_nature_preset_has_required_files(self) -> None:
        preset_dir = get_preset_dir("nature")
        assert (preset_dir / "preset.yaml").exists()
        assert (preset_dir / "references.bib").exists()

    def test_nonexistent_preset_returns_path_that_does_not_exist(self) -> None:
        preset_dir = get_preset_dir("nonexistent-journal")
        assert not preset_dir.exists()


class TestValeStylesResolution:
    """Test Vale style pack resolution."""

    def test_vale_styles_dir_resolves(self) -> None:
        styles_dir = get_vale_styles_dir()
        assert styles_dir.exists()
        assert styles_dir.is_dir()

    def test_vale_ini_exists(self) -> None:
        ini = get_vale_styles_dir() / ".vale.ini"
        assert ini.exists()
        assert ini.is_file()

    def test_vale_rules_dir_exists(self) -> None:
        rules_dir = get_vale_styles_dir() / "paper-writer"
        assert rules_dir.exists()
        yml_files = list(rules_dir.glob("*.yml"))
        assert len(yml_files) >= 4  # At least 4 rule files

    def test_vale_rules_content_not_empty(self) -> None:
        rules_dir = get_vale_styles_dir() / "paper-writer"
        for yml in rules_dir.glob("*.yml"):
            assert yml.stat().st_size > 0, f"Empty rule file: {yml.name}"


class TestCSLStylesResolution:
    """Test CSL citation style resolution."""

    def test_csl_styles_dir_resolves(self) -> None:
        csl_dir = get_csl_styles_dir()
        assert csl_dir.exists()
        assert csl_dir.is_dir()

    def test_vancouver_csl_exists(self) -> None:
        csl = get_csl_styles_dir() / "vancouver.csl"
        assert csl.exists()
        assert csl.stat().st_size > 100  # Non-trivial

    def test_apa_csl_exists(self) -> None:
        csl = get_csl_styles_dir() / "apa.csl"
        assert csl.exists()
        assert csl.stat().st_size > 100


class TestPackagingCompleteness:
    """Verify that all expected runtime assets are present."""

    EXPECTED_ASSETS: ClassVar[list[tuple[str, ...]]] = [
        ("templates", "manuscript.qmd"),
        ("templates", "references.bib"),
        ("templates", "journals", "nature", "preset.yaml"),
        ("templates", "journals", "nature", "references.bib"),
        ("templates", "journals", "nature", "template.qmd"),
        ("styles", "csl", "vancouver.csl"),
        ("styles", "csl", "apa.csl"),
        ("styles", "vale", ".vale.ini"),
        ("styles", "vale", "paper-writer", "ForbiddenPhrases.yml"),
        ("styles", "vale", "paper-writer", "InformalLanguage.yml"),
        ("styles", "vale", "paper-writer", "StrongClaims.yml"),
        ("styles", "vale", "paper-writer", "UnbackedClaims.yml"),
    ]

    @pytest.mark.parametrize(
        "path_parts",
        EXPECTED_ASSETS,
        ids=["/".join(p) for p in EXPECTED_ASSETS],
    )
    def test_asset_exists(self, path_parts: tuple[str, ...]) -> None:
        asset = get_asset_path(*path_parts)
        assert asset.exists(), f"Missing runtime asset: {asset}"
        assert asset.is_file(), f"Expected file, got dir: {asset}"

    def test_total_asset_count(self) -> None:
        """Sanity check: we have at least 12 packaged assets."""
        found = 0
        for parts in self.EXPECTED_ASSETS:
            if get_asset_path(*parts).exists():
                found += 1
        assert found == len(self.EXPECTED_ASSETS)
