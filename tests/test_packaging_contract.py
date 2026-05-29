from pathlib import Path

import tomllib


def test_pyproject_includes_runtime_skill_packages() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    include = data["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "skills*" in include
    assert "verification*" in include


def test_pyproject_declares_paper_entrypoint() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["paper"] == "cli.paper.main:main"


def test_pyproject_includes_skill_package_data() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = data["tool"]["setuptools"]["package-data"]
    assert "skills.imported.academic_writer" in package_data
    assert "skills.imported.literature_search.resources" in package_data


def test_pyproject_enables_uv_packaging() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["uv"]["package"] is True
    assert data["build-system"]["build-backend"] == "setuptools.build_meta"
