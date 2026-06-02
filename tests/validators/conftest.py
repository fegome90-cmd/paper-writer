"""Shared fixtures for validator tests.

Centralizes the _make_man helper that was duplicated across
test_prose_validator.py, test_claims_validator.py, and test_method_gate.py.

See: O-10 (conftest centralization) — graph audit showed _make_man as
hub #1 with 30 callers, all boilerplate.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from parsers.manuscript import ManuscriptParser


@pytest.fixture
def make_manuscript() -> Callable[[str], object]:
    """Parse text into a Manuscript structure for validator tests.

    Replaces the _make_man() helper that was copy-pasted across 3 test files.
    """

    def _make(text: str) -> object:
        return ManuscriptParser().parse_text(text, "test.md", "markdown")

    return _make
