"""Tests for contamination signal detection."""
from __future__ import annotations

import pytest

from validators.contamination_signals import (
    ContaminationSignal,
    compute_contamination_signal,
)


class TestComputeContaminationSignal:
    """Test compute_contamination_signal pure logic."""

    def test_clean_journal(self) -> None:
        result = compute_contamination_signal("Nature", 2023)
        assert result.is_preprint is False
        assert result.preprint_venue is None
        assert result.is_recent_preprint is False
        assert result.contamination_score == 0.0
        assert result.flags == ()

    def test_arxiv_preprint(self) -> None:
        result = compute_contamination_signal("arXiv", 2023)
        assert result.is_preprint is True
        assert result.preprint_venue == "arxiv"
        assert result.is_recent_preprint is False
        assert result.contamination_score == 0.4

    def test_recent_arxiv_preprint(self) -> None:
        result = compute_contamination_signal("arXiv", 2025)
        assert result.is_preprint is True
        assert result.is_recent_preprint is True
        assert result.contamination_score == 0.7  # 0.4 + 0.3

    def test_recent_biorxiv_preprint(self) -> None:
        result = compute_contamination_signal("bioRxiv", 2024)
        assert result.is_preprint is True
        assert result.is_recent_preprint is True
        assert result.contamination_score == 0.7

    def test_old_preprint(self) -> None:
        result = compute_contamination_signal("arXiv", 2020)
        assert result.is_preprint is True
        assert result.is_recent_preprint is False
        assert result.contamination_score == 0.4

    def test_no_venue(self) -> None:
        result = compute_contamination_signal(None, 2024)
        assert result.is_preprint is False
        assert result.contamination_score == 0.0

    def test_no_year_with_preprint(self) -> None:
        result = compute_contamination_signal("medRxiv", None)
        assert result.is_preprint is True
        assert result.is_recent_preprint is False
        assert result.contamination_score == 0.4

    def test_custom_recent_threshold(self) -> None:
        result = compute_contamination_signal("arXiv", 2023, recent_threshold=2022)
        assert result.is_recent_preprint is True
        assert result.contamination_score == 0.7

    def test_ssrn_detected(self) -> None:
        result = compute_contamination_signal("SSRN Electronic Journal", 2024)
        assert result.is_preprint is True
        assert "ssrn" in result.preprint_venue
        assert result.is_recent_preprint is True

    def test_score_clamped_at_1(self) -> None:
        # Even with all flags, score should not exceed 1.0
        result = compute_contamination_signal("arXiv", 2025)
        assert result.contamination_score <= 1.0

    def test_to_dict(self) -> None:
        result = compute_contamination_signal("arXiv", 2024)
        d = result.to_dict()
        assert d["is_preprint"] is True
        assert d["contamination_score"] == 0.7
        assert isinstance(d["flags"], list)


class TestContaminationSignalDataclass:
    """Test ContaminationSignal dataclass."""

    def test_frozen(self) -> None:
        sig = ContaminationSignal(
            is_preprint=False,
            preprint_venue=None,
            is_recent_preprint=False,
            year=2023,
            contamination_score=0.0,
            flags=(),
        )
        with pytest.raises(AttributeError):
            sig.is_preprint = True  # type: ignore[misc]

    def test_all_preprint_venues_detected(self) -> None:
        """All venues in PREPRINT_VENUES should be detected."""
        from validators.citation_verify import PREPRINT_VENUES

        for venue in PREPRINT_VENUES:
            result = compute_contamination_signal(venue, 2024)
            assert result.is_preprint is True, f"Failed to detect {venue}"
