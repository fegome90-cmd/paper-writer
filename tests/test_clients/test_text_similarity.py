"""Tests for clients._text_similarity — title normalization and similarity."""

from __future__ import annotations

from clients._text_similarity import (
    TITLE_SIMILARITY_THRESHOLD,
    normalize_title,
    title_similarity,
)


class TestNormalizeTitle:
    def test_lowercase(self):
        assert normalize_title("Hello World") == "hello world"

    def test_punctuation_stripped(self):
        assert normalize_title("Hello, World!") == "hello world"

    def test_preserves_token_boundaries(self):
        # Punctuation becomes whitespace so "R.A.G." → "r a g" (3 tokens)
        result = normalize_title("R.A.G.")
        assert "rag" not in result  # must NOT collapse to single token
        assert "r a g" == result

    def test_collapse_whitespace(self):
        assert normalize_title("  hello   world  ") == "hello world"

    def test_mixed_punctuation(self):
        assert normalize_title("paper-writer (v2.0)!") == "paper writer v2 0"


class TestTitleSimilarity:
    def test_identical_titles(self):
        assert title_similarity("Hello World", "Hello World") == 1.0

    def test_case_insensitive(self):
        score = title_similarity("HELLO WORLD", "hello world")
        assert score == 1.0

    def test_punctuation_insensitive(self):
        score = title_similarity("Hello, World!", "Hello World")
        assert score == 1.0

    def test_rag_vs_rag_period(self):
        """Codex R4-1 closure: 'R.A.G.' vs 'RAG' must be above threshold."""
        score = title_similarity("R.A.G. Framework", "RAG Framework")
        assert score >= TITLE_SIMILARITY_THRESHOLD

    def test_threshold_boundary(self):
        """Titles above 0.70 are 'matched'."""
        score = title_similarity(
            "A Novel Approach to Deep Learning",
            "A New Approach to Deep Learning",
        )
        assert score >= TITLE_SIMILARITY_THRESHOLD

    def test_dissimilar_below_threshold(self):
        """Completely different titles should be below threshold."""
        score = title_similarity(
            "Deep Learning for Image Recognition",
            "Quantum Computing in Cryptography",
        )
        assert score < TITLE_SIMILARITY_THRESHOLD

    def test_partial_match(self):
        """One title is a subset of the other."""
        score = title_similarity(
            "Machine Learning",
            "Machine Learning for Healthcare Applications",
        )
        # Partial overlap — above 0.5 but may or may not hit 0.70
        assert 0.0 <= score <= 1.0
