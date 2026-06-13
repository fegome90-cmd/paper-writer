"""Project root resolution (standalone leaf module).

PR2: migrated from SystemExit(1) to UserInputError for bad paths.
"""

from __future__ import annotations

from pathlib import Path

from cli.paper.errors import UserInputError

MAX_ASCENDING_DEPTH = 20


def resolve_project_root(explicit_path: Path | None, cwd: Path) -> Path:
    """Resolve project root. Priority: flag -> ascending search -> CWD."""
    if explicit_path is not None:
        resolved = explicit_path.resolve()
        if not resolved.is_dir():
            raise UserInputError(f"Project path does not exist: {explicit_path}")
        return resolved

    candidate = cwd.resolve()
    for _ in range(MAX_ASCENDING_DEPTH):
        marker = candidate / "outputs" / "state.yaml"
        if marker.is_file():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent

    return cwd.resolve()
