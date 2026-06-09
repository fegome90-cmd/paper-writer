"""Tests for clients.crossref — Crossref API client."""

from __future__ import annotations

import json
import os
import urllib.error
from unittest.mock import MagicMock, patch

from clients.crossref import CrossrefClient, CrossrefResult


class TestCrossrefResult:
    def test_default_not_found(self):
        r = CrossrefResult(found=False)
        assert r.found is False
        assert r.doi is None
        assert r.title is None
        assert r.authors == []
        assert r.year is None
        assert r.score == 0.0


class TestCrossrefClientOffline:
    def test_offline_returns_not_found(self):
        client = CrossrefClient(offline=True)
        result = client.verify_doi("10.1038/s41586-020-2649-2")
        assert result.found is False

    def test_offline_search_returns_empty(self):
        client = CrossrefClient(offline=True)
        results = client.search_by_title("Deep Learning")
        assert results == []


class TestCrossrefClientVerifyDoi:
    @patch("clients.crossref.urllib.request.urlopen")
    def test_valid_doi_found(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "message": {
                    "title": ["Nature Paper"],
                    "author": [{"given": "A", "family": "B"}],
                    "issued": {"date-parts": [[2023]]},
                    "container-title": ["Nature"],
                    "license": [{"URL": "http://creativecommons.org/licenses/by/4.0/"}],
                }
            }
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = CrossrefClient(offline=False)
        result = client.verify_doi("10.1038/s41586-020-2649-2")
        assert result.found is True
        assert result.doi == "10.1038/s41586-020-2649-2"
        assert result.title == "Nature Paper"

    @patch("clients.crossref.urllib.request.urlopen")
    def test_404_returns_not_found(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=None
        )
        client = CrossrefClient(offline=False)
        result = client.verify_doi("10.99999/fake")
        assert result.found is False

    @patch("clients.crossref.urllib.request.urlopen")
    def test_network_timeout_returns_not_found(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")
        client = CrossrefClient(offline=False)
        result = client.verify_doi("10.1038/s41586-020-2649-2")
        assert result.found is False


class TestCrossrefClientSearchByTitle:
    @patch("clients.crossref.urllib.request.urlopen")
    def test_search_returns_ranked_results(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "message": {
                    "items": [
                        {
                            "title": ["Deep Learning Methods for Vision"],
                            "author": [{"given": "Y", "family": "L"}],
                            "issued": {"date-parts": [[2020]]},
                            "container-title": ["IEEE TPAMI"],
                        }
                    ]
                }
            }
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = CrossrefClient(offline=False)
        results = client.search_by_title("Deep Learning for Vision")
        assert len(results) >= 1
        assert results[0].found is True


class TestCrossrefTimestamp:
    @patch("clients.crossref.urllib.request.urlopen")
    def test_last_request_at_updates_on_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "message": {
                    "title": ["Test"],
                    "author": [],
                    "issued": {"date-parts": [[2023]]},
                }
            }
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        mock_clock = MagicMock(return_value=1000.0)
        client = CrossrefClient(offline=False, clock=mock_clock)
        assert client._last_request_at == 0.0
        client.verify_doi("10.1000/test")
        assert client._last_request_at == 1000.0

    @patch("clients.crossref.urllib.request.urlopen")
    def test_last_request_at_updates_after_429_backoff(self, mock_urlopen):
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None)
            resp = MagicMock()
            resp.read.return_value = json.dumps(
                {
                    "message": {
                        "title": ["Test"],
                        "author": [],
                        "issued": {"date-parts": [[2023]]},
                    }
                }
            ).encode()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        mock_urlopen.side_effect = side_effect

        # _get calls _clock() twice: once in on_retry lambda, once after success
        mock_clock = MagicMock(side_effect=[500.0, 2000.0])
        mock_sleep = MagicMock()
        client = CrossrefClient(offline=False, clock=mock_clock, sleep=mock_sleep)
        client.verify_doi("10.1000/test")
        assert client._last_request_at == 2000.0


class TestCrossrefPoliteEmail:
    def test_explicit_email_used(self):
        client = CrossrefClient(email="user@example.com")
        assert client.email == "user@example.com"

    @patch.dict(os.environ, {"CROSSREF_POLITE_EMAIL": "env@example.com"})
    def test_env_var_fallback(self):
        client = CrossrefClient()
        assert client.email == "env@example.com"

    @patch.dict(os.environ, {}, clear=True)
    def test_no_email_no_mailto(self):
        client = CrossrefClient()
        assert client.email is None

    @patch.dict(os.environ, {}, clear=True)
    def test_explicit_email_overrides_env(self):
        client = CrossrefClient(email="explicit@example.com")
        assert client.email == "explicit@example.com"


class TestCrossrefGetErrorHandling:
    @patch("clients.crossref.urllib.request.urlopen")
    def test_json_decode_error_returns_none(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json at all"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = CrossrefClient(offline=False)
        result = client._get("/works/10.1000/test", {})
        assert result is None

    @patch("clients.crossref.urllib.request.urlopen")
    def test_unicode_decode_error_returns_none(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"\x80\x81\x82"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = CrossrefClient(offline=False)
        result = client._get("/works/10.1000/test", {})
        assert result is None
