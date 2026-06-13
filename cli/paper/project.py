"""Project root resolution (standalone leaf module — no CLI/domain imports).

Extracted from main.py in PR1 of cli-structural-refactoring to break the
import cycle: dispatch.py needs resolve_project_root(), and main.py imports
dispatch.execute(). Moving the implementation here lets both import from this
leaf module without a cycle.

PR1 preserves the current SystemExit(1) behavior for invalid paths.
PR2 will migrate this to UserInputError once errors.py exists.
"""

from __future__ import annotations

from pathlib import Path

MAX_ASCENDING_DEPTH = 20


def resolve_project_root(explicit_path: Path | None, cwd: Path) -> Path:
    """Resolve project root. Priority: flag → ascending search → CWD.

    Ascending search resolves symlinks via Path.resolve() before
    checking for outputs/state.yaml to prevent symlink injection.
    """
    if explicit_path is not None:
        resolved = explicit_path.resolve()
        if not resolved.is_dir():
            import sys

            print(
                f"Error: Project path does not exist: {explicit_path}",
                file=sys.stderr,
            )
            raise SystemExit(1) from None
        return resolved

    # Ascending search for outputs/state.yaml (innermost match)
    candidate = cwd.resolve()
    for _ in range(MAX_ASCENDING_DEPTH):
        marker = candidate / "outputs" / "state.yaml"
        if marker.is_file():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break  # filesystem root
        candidate = parent

    # Fallback: CWD
    return cwd.resolve()
