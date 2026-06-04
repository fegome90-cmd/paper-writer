"""Tests for clients.semantic_scholar — Semantic Scholar API client."""
from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

from clients.semantic_scholar import S2Result, SemanticScholarClient


class TestS2Result:
    def test_default_not_found(self):
        r = S2Result(found=False)
        assert r.found is False
        assert r.paper_id is None
        assert r.citation_count is None


class TestSemanticScholarClientOffline:
    def test_offline_returns_not_found(self):
        client = SemanticScholarClient(offline=True)
        result = client.verify_doi("10.1038/s41586-020-2649-2")
        assert result.found is False

    def test_offline_search_returns_empty(self):
        client = SemanticScholarClient(offline=True)
        results = client.search_by_title("Deep Learning")
        assert results == []


class TestSemanticScholarClientVerifyDoi:
    @patch("clients.semantic_scholar.urllib.request.urlopen")
    def test_valid_doi_found(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "paperId": "abc123",
            "title": "Nature Paper",
            "authors": [{"name": "Author B"}],
            "year": 2023,
            "venue": "Nature",
            "citationCount": 100,
            "isOpenAccess": True,
        }).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = SemanticScholarClient(offline=False)
        result = client.verify_doi("10.1038/s41586-020-2649-2")
        assert result.found is True
        assert result.paper_id == "abc123"
        assert result.citation_count == 100

    @patch("clients.semantic_scholar.urllib.request.urlopen")
    def test_404_returns_not_found(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=None
        )
        client = SemanticScholarClient(offline=False)
        result = client.verify_doi("10.99999/fake")
        assert result.found is False

    @patch("clients.semantic_scholar.urllib.request.urlopen")
    def test_network_error_returns_not_found(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("network error")
        client = SemanticScholarClient(offline=False)
        result = client.verify_doi("10.1038/s41586-020-2649-2")
        assert result.found is False


class TestSemanticScholarClientSearchByTitle:
    @patch("clients.semantic_scholar.urllib.request.urlopen")
    def test_search_returns_ranked_results(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "data": [
                {
                    "paperId": "xyz789",
                    "title": "Deep Learning for Vision",
                    "authors": [{"name": "Y L"}],
                    "year": 2020,
                    "venue": "IEEE TPAMI",
                    "citationCount": 500,
                }
            ]
        }).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = SemanticScholarClient(offline=False)
        results = client.search_by_title("Deep Learning for Vision")
        assert len(results) >= 1
        assert results[0].found is True
        assert results[0].citation_count == 500


class TestSemanticScholarTimestamp:
    def test_last_request_at_updates_on_success(self):
        mock_clock = MagicMock(return_value=1000.0)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "paperId": "abc123",
            "title": "Test",
        }).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("clients.semantic_scholar.urllib.request.urlopen", return_value=mock_resp):
            client = SemanticScholarClient(offline=False, clock=mock_clock)
            assert client._last_request_at == 0.0
            client.verify_doi("10.1000/test")
            assert client._last_request_at == 1000.0

    def test_last_request_at_updates_after_429_backoff(self):
        mock_clock = MagicMock(return_value=2000.0)
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None)
            resp = MagicMock()
            resp.read.return_value = json.dumps({
                "paperId": "abc123",
                "title": "Test",
            }).encode()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("clients.semantic_scholar.urllib.request.urlopen", side_effect=side_effect):
            mock_sleep = MagicMock()
            client = SemanticScholarClient(offline=False, clock=mock_clock, sleep=mock_sleep)
            client.verify_doi("10.1000/test")
            assert client._last_request_at == 2000.0


class TestSemanticScholarGetErrorHandling:
    @patch("clients.semantic_scholar.urllib.request.urlopen")
    def test_json_decode_error_returns_none(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json at all"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = SemanticScholarClient(offline=False)
        result = client._get("/paper/DOI:10.1000/test")
        assert result is None

    @patch("clients.semantic_scholar.urllib.request.urlopen")
    def test_unicode_decode_error_returns_none(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"\x80\x81\x82"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = SemanticScholarClient(offline=False)
        result = client._get("/paper/DOI:10.1000/test")
        assert result is None
