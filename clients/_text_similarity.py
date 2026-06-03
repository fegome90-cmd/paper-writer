"""Title similarity utility for citation verification clients.

Ported from ARS scripts/_text_similarity.py. Normalizes titles by
lowercasing, stripping punctuation (preserving token boundaries),
and collapsing whitespace, then computes SequenceMatcher ratio.

Threshold 0.70 for "matched" verdict (validated across 150+ citation types).
"""
from __future__ import annotations

import string
from difflib import SequenceMatcher

_PUNCT_TRANSLATION = str.maketrans(dict.fromkeys(string.punctuation, " "))

TITLE_SIMILARITY_THRESHOLD = 0.70


def normalize_title(s: str) -> str:
    """Lowercase, strip punctuation (preserve token boundaries), collapse whitespace."""
    cleaned = s.lower().translate(_PUNCT_TRANSLATION)
    return " ".join(cleaned.split())


def title_similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio on normalized titles.

    Returns a float in [0.0, 1.0] where 1.0 means identical after normalization.
    """
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()
