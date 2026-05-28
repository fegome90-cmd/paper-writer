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
