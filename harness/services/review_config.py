"""Review configuration: authoritative review-mode artifact.

Persists review mode (rapid/academic) and search window in
``outputs/review_config.yaml``. This is the single source of truth
for review-mode selection, outside ManuscriptState.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "rapid",
    "search_window": None,
    "amendments": [],
}


@dataclass(frozen=True)
class ReviewConfigSnapshot:
    """Snapshot of review_config.yaml with source tracking.

    Distinguishes between:
    - File loaded successfully (source="file")
    - File missing (source="default_missing")
    - File invalid/corrupt (source="default_invalid")
    """

    values: dict[str, Any]
    source: str
    warnings: tuple[str, ...] = ()


def load_review_config_snapshot(project_root: Path) -> ReviewConfigSnapshot:
    """Load review_config.yaml with source tracking.

    Parses YAML directly to detect invalid files (the legacy loader
    swallows exceptions and returns defaults).

    Returns:
        ReviewConfigSnapshot with values, source, and warnings.
    """
    config_path = project_root / "outputs" / "review_config.yaml"

    if not config_path.exists():
        return ReviewConfigSnapshot(
            values=dict(_DEFAULT_CONFIG),
            source="default_missing",
            warnings=("review_config.yaml not found, using defaults",),
        )

    try:
        raw = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            return ReviewConfigSnapshot(
                values=dict(_DEFAULT_CONFIG),
                source="default_invalid",
                warnings=("review_config.yaml is not a dict, using defaults",),
            )
        merged = dict(_DEFAULT_CONFIG)
        for key in _DEFAULT_CONFIG:
            if key in data and data[key] is not None:
                merged[key] = data[key]
        warnings_list: list[str] = []
        if merged["mode"] not in ("rapid", "academic"):
            warnings_list.append(
                f"Unknown review mode '{merged['mode']}', defaulting to 'rapid'"
            )
            merged["mode"] = "rapid"
        return ReviewConfigSnapshot(
            values=merged,
            source="file",
            warnings=tuple(warnings_list),
        )
    except (yaml.YAMLError, OSError) as exc:
        return ReviewConfigSnapshot(
            values=dict(_DEFAULT_CONFIG),
            source="default_invalid",
            warnings=(f"review_config.yaml is invalid ({exc}), using defaults",),
        )


def load_review_config(project_root: Path) -> dict[str, Any]:
    """Load review_config.yaml from ``<project_root>/outputs/``.

    Delegates to :func:`load_review_config_snapshot` to ensure both Preflight
    and Dispatch see identical values.

    Returns the parsed config dict.  If the file does not exist,
    returns the default (rapid mode, no search window).
    """
    snapshot = load_review_config_snapshot(project_root)
    for warning in snapshot.warnings:
        logger.warning(warning)
    return dict(snapshot.values)


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


__all__ = [
    "ReviewConfigSnapshot",
    "load_review_config",
    "load_review_config_snapshot",
    "save_review_config",
]
