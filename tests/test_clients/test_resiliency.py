"""Tests for clients semantic_scholar — resiliency features.

Outage latch, DI, and year tiebreaker ported from ARS.
"""
from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

from clients.crossref import CrossrefClient
from clients.semantic_scholar import SemanticScholarClient


class TestSemanticScholarLatch:
    def test_latch_field_exists(self):
        client = SemanticScholarClient()
        assert hasattr(client, "_latched_unavailable")
        assert client._latched_unavailable is False

    def test_latch_sets_on_url_error(self):
        client = SemanticScholarClient()
        with patch(
            "clients.semantic_scholar.urllib.request.urlopen",
            side_effect=urllib.error.URLError("fail"),
        ):
            client._get("/test")
        assert client._latched_unavailable is True

    def test_latch_sets_on_os_error(self):
        client = SemanticScholarClient()
        mock_resp = MagicMock()
        mock_resp.read.side_effect = OSError("socket drop")
        mock_resp.__enter__.return_value = mock_resp

        with patch("clients.semantic_scholar.urllib.request.urlopen", return_value=mock_resp):
            client._get("/test")
        assert client._latched_unavailable is True

    def test_latch_fail_fast(self):
        client = SemanticScholarClient()
        client._latched_unavailable = True
        result = client._get("/test")
        assert result is None

    def test_reset_outage_latch(self):
        client = SemanticScholarClient()
        client._latched_unavailable = True
        client.reset_outage_latch()
        assert client._latched_unavailable is False


class TestSemanticScholarDI:
    def test_sleep_injected(self):
        mock_sleep = MagicMock()
        client = SemanticScholarClient(sleep=mock_sleep)
        assert client._sleep is mock_sleep

    def test_clock_injected(self):
        mock_clock = MagicMock(return_value=123.0)
        client = SemanticScholarClient(clock=mock_clock)
        assert client._clock() == 123.0

    def test_clock_default_is_time(self):
        client = SemanticScholarClient()
        assert client._clock is not None


class TestYearTiebreaker:
    def test_crossref_year_tiebreaker(self):
        client = CrossrefClient()
        mock_data = {
            "message": {
                "items": [
                    {
                        "title": ["Artificial Intelligence"],
                        "issued": {"date-parts": [[2020]]},
                        "DOI": "1",
                    },
                    {
                        "title": ["Artificial Intelligence"],
                        "issued": {"date-parts": [[2022]]},
                        "DOI": "2",
                    },
                ]
            }
        }
        with patch.object(client, "_get", return_value=mock_data):
            results = client.search_by_title("Artificial Intelligence", year=2022)
            assert len(results) == 2
            assert results[0].doi == "2"  # 2022 won the tie

    def test_s2_year_tiebreaker(self):
        client = SemanticScholarClient()
        mock_data = {
            "data": [
                {
                    "paperId": "a",
                    "title": "Test Paper",
                    "authors": [],
                    "year": 2020,
                    "citationCount": 10,
                },
                {
                    "paperId": "b",
                    "title": "Test Paper",
                    "authors": [],
                    "year": 2022,
                    "citationCount": 10,
                },
            ]
        }
        with patch.object(client, "_get", return_value=mock_data):
            results = client.search_by_title("Test Paper", year=2022)
            assert len(results) == 2
            assert results[0].paper_id == "b"  # 2022 won the tie
