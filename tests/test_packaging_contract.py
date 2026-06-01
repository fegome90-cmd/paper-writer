"""Packaging contract tests — verify pyproject.toml declares all runtime assets.

These tests prevent regressions of the packaging gap where rules/ and schemas/
were missing from the wheel (20 runtime assets lost). If any assertion fails,
the wheel will be broken for installed-package usage.
"""

from pathlib import Path
from typing import Any

import tomllib

PYPROJECT = Path("pyproject.toml")


def _load_config() -> dict[str, Any]:

    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


class TestPackageDiscovery:
    """Verify all packages with runtime data are discovered by setuptools."""

    def test_includes_cli(self) -> None:
        include = _load_config()["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "cli*" in include

    def test_includes_harness(self) -> None:
        include = _load_config()["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "harness*" in include

    def test_includes_validators(self) -> None:
        include = _load_config()["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "validators*" in include

    def test_includes_skills(self) -> None:
        include = _load_config()["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "skills*" in include

    def test_includes_templates(self) -> None:
        include = _load_config()["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "templates*" in include

    def test_includes_styles(self) -> None:
        include = _load_config()["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "styles*" in include

    def test_includes_verification(self) -> None:
        include = _load_config()["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "verification*" in include

    def test_includes_rules(self) -> None:
        """Regression: rules/ must be discoverable (16 YAML files for validators)."""
        include = _load_config()["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "rules*" in include

    def test_includes_schemas(self) -> None:
        """Regression: schemas/ must be discoverable (4 JSON schema files)."""
        include = _load_config()["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "schemas*" in include


class TestPackageData:
    """Verify all non-Python data is declared in package-data."""

    def test_rules_data(self) -> None:
        """Regression: rules YAML must be in package-data for validators."""
        package_data = _load_config()["tool"]["setuptools"]["package-data"]
        assert "rules" in package_data
        assert "**/*.*" in package_data["rules"]

    def test_schemas_data(self) -> None:
        """Regression: schemas JSON must be in package-data."""
        package_data = _load_config()["tool"]["setuptools"]["package-data"]
        assert "schemas" in package_data
        assert "**/*.*" in package_data["schemas"]

    def test_templates_data(self) -> None:
        package_data = _load_config()["tool"]["setuptools"]["package-data"]
        assert "templates" in package_data

    def test_styles_data(self) -> None:
        package_data = _load_config()["tool"]["setuptools"]["package-data"]
        assert "styles" in package_data

    def test_skills_data(self) -> None:
        package_data = _load_config()["tool"]["setuptools"]["package-data"]
        assert "skills" in package_data

    def test_verification_data(self) -> None:
        package_data = _load_config()["tool"]["setuptools"]["package-data"]
        assert "verification" in package_data


class TestRuntimeAssetResolution:
    """Verify asset resolver can find packaged files at runtime."""

    def test_rules_dir_resolves(self) -> None:
        from harness.ports.assets import get_rules_dir

        d = get_rules_dir("method_gate")
        assert d.exists(), f"rules/method_gate not found at {d}"
        yml_files = list(d.glob("*.yml"))
        assert len(yml_files) >= 4, f"Expected >=4 method_gate rules, got {len(yml_files)}"

    def test_schemas_dir_resolves(self) -> None:
        from harness.ports.assets import get_schemas_dir

        d = get_schemas_dir()
        assert d.exists(), f"schemas not found at {d}"
        json_files = list(d.glob("*.json"))
        assert len(json_files) >= 4, f"Expected >=4 schemas, got {len(json_files)}"

    def test_method_gate_loads_consort(self) -> None:
        """Regression: CONSORT checklist must load (broke when rules/ missing)."""
        from harness.ports.assets import get_asset_path

        consort = get_asset_path("rules", "method_gate", "consort.yml")
        assert consort.exists(), f"consort.yml not found at {consort}"

    def test_templates_resolve(self) -> None:
        from harness.ports.assets import get_asset_path

        qmd = get_asset_path("templates", "manuscript.qmd")
        assert qmd.exists(), f"manuscript.qmd not found at {qmd}"


class TestEntrypointAndBuild:
    """Verify entrypoint and build configuration."""

    def test_declares_paper_entrypoint(self) -> None:
        data = _load_config()
        assert data["project"]["scripts"]["paper"] == "cli.paper.main:main"

    def test_enables_uv_packaging(self) -> None:
        data = _load_config()
        assert data["tool"]["uv"]["package"] is True
        assert data["build-system"]["build-backend"] == "setuptools.build_meta"
