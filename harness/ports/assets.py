"""Runtime asset resolution for portable CLI installations.

Provides centralized path resolution for packaged assets (templates, styles)
that must work both from the source tree and from an installed package.

Resolution order:
1. Source tree (repo root relative to this package)
2. Package-bundled data via importlib.resources
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 12):
    from importlib.resources import files as _ires_files
else:
    from importlib import resources as _resources

    def _ires_files(package: str) -> object:
        return _resources.files(package)


def _get_package_root() -> Path:
    """Get the project root directory.

    In source tree: this file is at harness/ports/assets.py,
    so root is 3 levels up.
    In installed package: same layout if templates/styles are sibling packages.
    """
    harness_pkg = Path(str(_ires_files("harness"))).resolve()
    # harness/ports/assets.py -> harness/ -> root/
    return harness_pkg.parent


def get_asset_path(*path_parts: str) -> Path:
    """Resolve a packaged asset path.

    Args:
        *path_parts: Path components relative to project root,
                     e.g. ("templates", "journals", "nature", "preset.yaml")

    Returns:
        Resolved Path. Caller should check .exists() before use.
    """
    root = _get_package_root()
    return root.joinpath(*path_parts)


def get_templates_dir() -> Path:
    """Get the templates/ directory path."""
    return get_asset_path("templates")


def get_styles_dir() -> Path:
    """Get the styles/ directory path."""
    return get_asset_path("styles")


def get_preset_dir(preset_name: str) -> Path:
    """Get a journal preset directory path."""
    return get_asset_path("templates", "journals", preset_name)


def get_vale_styles_dir() -> Path:
    """Get the Vale styles directory path."""
    return get_asset_path("styles", "vale")


def get_csl_styles_dir() -> Path:
    """Get the CSL styles directory path."""
    return get_asset_path("styles", "csl")


def get_rules_dir(subdir: str = "") -> Path:
    """Get the rules directory path.

    Args:
        subdir: Optional subdirectory, e.g. "prose", "claims", "method_gate".

    Returns:
        Resolved Path to rules/ or rules/<subdir>.
    """
    if subdir:
        return get_asset_path("rules", subdir)
    return get_asset_path("rules")


def get_schemas_dir() -> Path:
    """Get the schemas directory path."""
    return get_asset_path("schemas")


def get_project_asset(project_root: Path, *path_parts: str) -> Path:
    """Resolve asset with project-local → package waterfall.

    1. project_root / path_parts → if exists, return it
    2. get_asset_path(*path_parts) → fallback to package

    Args:
        project_root: Root directory of the current paper project.
        *path_parts: Path components relative to project root,
                     e.g. ("templates", "journals", "nature", "preset.yaml")

    Returns:
        Resolved Path. Caller should check .exists() before use.
    """
    local_path = project_root.joinpath(*path_parts)
    if local_path.exists():
        return local_path
    return get_asset_path(*path_parts)
