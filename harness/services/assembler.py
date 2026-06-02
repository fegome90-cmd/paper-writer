"""Manuscript assembler — combines draft sections into a single renderable file.

Canonical section order: introduction → methods → results → discussion.
Missing sections are skipped with a warning. If no sections are found,
the assembled manuscript is NOT written (to avoid overwriting with empty content).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CANONICAL_ORDER = ("introduction", "methods", "results", "discussion")


def assemble_manuscript(draft_dir: Path) -> Path:
    """Assemble draft sections into a single manuscript file.

    Args:
        draft_dir: Path to the directory containing draft section files
                   (e.g. ``outputs/drafts/``).

    Returns:
        Path to the assembled manuscript (``outputs/drafts/manuscript.md``).

    The file is only written when at least one section is found. If the
    directory is empty or no canonical sections exist the function still
        returns the expected path but does **not** create an empty file.
    """
    manuscript_path = draft_dir / "manuscript.md"

    if not draft_dir.is_dir():
        logger.warning("Draft directory does not exist: %s", draft_dir)
        return manuscript_path

    parts: list[str] = []
    for section_name in CANONICAL_ORDER:
        section_file = draft_dir / f"{section_name}.md"
        if not section_file.is_file():
            logger.warning("Missing section: %s — skipping", section_file.name)
            continue
        try:
            content = section_file.read_text(encoding="utf-8").strip()
        except (UnicodeDecodeError, OSError) as exc:
            logger.warning("Unreadable section: %s — skipping (%s)", section_file.name, exc)
            continue
        if not content:
            logger.warning("Empty section: %s — skipping", section_file.name)
            continue
        parts.append(content)

    if not parts:
        logger.warning("No sections found — manuscript not written")
        return manuscript_path

    assembled = "\n\n".join(parts) + "\n"
    try:
        manuscript_path.write_text(assembled, encoding="utf-8")
        logger.info("Assembled manuscript → %s (%d sections)", manuscript_path, len(parts))
    except OSError as exc:
        logger.error("Cannot write manuscript to %s: %s", manuscript_path, exc)
    return manuscript_path
