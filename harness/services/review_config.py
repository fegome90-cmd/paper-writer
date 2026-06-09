"""Review configuration: authoritative review-mode artifact.

Persists review mode (rapid/academic) and search window in
``outputs/review_config.yaml``. This is the single source of truth
for review-mode selection, outside ManuscriptState.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "rapid",
    "search_window": None,
    "amendments": [],
}


def load_review_config(project_root: Path) -> dict[str, Any]:
    """Load review_config.yaml from ``<project_root>/outputs/``.

    Returns the parsed config dict.  If the file does not exist,
    returns the default (rapid mode, no search window).
    """
    config_path = project_root / "outputs" / "review_config.yaml"
    if not config_path.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("review_config.yaml is not a dict; using defaults.")
            return dict(_DEFAULT_CONFIG)
        return {**_DEFAULT_CONFIG, **data}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Failed to load review_config.yaml: %s", exc)
        return dict(_DEFAULT_CONFIG)


def save_review_config(
    project_root: Path,
    mode: str = "rapid",
    search_window: dict[str, int] | None = None,
    amendments: list[dict[str, Any]] | None = None,
) -> Path:
    """Write review_config.yaml to ``<project_root>/outputs/``.

    Returns the path to the written file.
    """
    config_dir = project_root / "outputs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "review_config.yaml"

    data: dict[str, Any] = {"mode": mode}
    if search_window is not None:
        data["search_window"] = search_window
    if amendments:
        data["amendments"] = amendments

    config_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return config_path
