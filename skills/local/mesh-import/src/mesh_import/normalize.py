"""Text normalization for FTS5 search — NFC + casefold + diacritic stripping."""

from __future__ import annotations

import unicodedata


def normalize_text(text: str) -> str:
    """NFC normalize, casefold, strip diacritics.

    Produces a normalized form suitable for FTS5 matching:
    1. NFC canonical composition
    2. Unicode casefold (aggressive lowercasing)
    3. Strip combining marks (diacritics) via NFD decomposition
    """
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.casefold()
    decomposed = unicodedata.normalize("NFD", normalized)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped
