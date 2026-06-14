"""Tests for clean_cancel SIGINT wrapping (S16 + P3.3.1 + P3.4.1).

S16: Zotero write operations (create/update/delete/upload) marked
clean_cancel=True are wrapped in temporary_sigint_handler(). Read-only
commands (doctor, zotero collections) are NOT wrapped.
"""

from __future__ import annotations

import pytest

from cli.paper.parser import build_parser


class TestZoteroWriteOpsMarkedCleanCancel:
    """P3.4.1: zotero create/update/delete/upload have clean_cancel=True."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["zotero", "create", "file.json"],
            ["zotero", "update", "KEY", "file.json"],
            ["zotero", "delete", "KEY"],
            ["zotero", "upload", "KEY", "file"],
        ],
    )
    def test_write_op_has_clean_cancel(self, argv: list[str]) -> None:
        """Zotero write operations MUST be marked clean_cancel=True (side effects)."""
        args = build_parser().parse_args(argv)
        assert getattr(args, "clean_cancel", False) is True, (
            f"{' '.join(argv)} has side effects and MUST be clean_cancel=True"
        )


class TestReadOnlyCommandsNotWrapped:
    """S16: read-only commands (doctor, zotero collections) are NOT wrapped."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["doctor"],
            ["zotero", "collections"],
            ["zotero", "search", "q"],
            ["zotero", "get", "KEY"],
            ["zotero", "template", "journalArticle"],
        ],
    )
    def test_read_op_not_clean_cancel(self, argv: list[str]) -> None:
        """Read-only commands MUST NOT be wrapped (no clean_cancel attribute)."""
        args = build_parser().parse_args(argv)
        assert getattr(args, "clean_cancel", False) is False, (
            f"{' '.join(argv)} is read-only and must NOT be clean_cancel"
        )
