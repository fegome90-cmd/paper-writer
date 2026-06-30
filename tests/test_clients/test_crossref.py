"""Tests for clients.crossref — Crossref API client."""

from __future__ import annotations

import json
import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from clients.crossref import CrossrefClient, CrossrefResult, _TransientError


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


class TestOutageLatchActivation:
    """Bug 1 P0: outage latch activates on transport error and blocks
    subsequent requests (fail-fast)."""

    @patch("clients.crossref.urllib.request.urlopen")
    def test_latch_activates_on_transport_error(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("network down")
        client = CrossrefClient(offline=False, sleep=MagicMock())
        result1 = client._get("/works/x", {})
        assert result1 is None
        assert client._latched_unavailable is True

    @patch("clients.crossref.urllib.request.urlopen")
    def test_latched_client_fail_fasts_within_cooldown(self, mock_urlopen):
        # W4 (Judgment Day): fail-fast within cooldown now raises
        # _TransientError (not returns None) so callers surface
        # transient_error=True instead of classifying as not_found/P0.
        mock_urlopen.side_effect = TimeoutError("network down")
        mock_clock = MagicMock(return_value=1000.0)
        client = CrossrefClient(offline=False, sleep=MagicMock(), clock=mock_clock)
        client._get("/works/x", {})
        assert client._latched_unavailable is True

        mock_urlopen.side_effect = AssertionError("should fail-fast, not call urlopen")
        mock_clock.return_value = 1100.0
        with pytest.raises(_TransientError):
            client._get("/works/y", {})
        assert client._latched_unavailable is True


class TestOutageLatchAutoReset:
    """Bug 1 P0 fix: latch auto-resets after LATCH_COOLDOWN_SECONDS so a
    single transient failure does not skip an entire batch."""

    @patch("clients.crossref.urllib.request.urlopen")
    def test_latch_auto_resets_after_cooldown(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("network down")
        mock_clock = MagicMock(return_value=1000.0)
        client = CrossrefClient(offline=False, sleep=MagicMock(), clock=mock_clock)
        client._get("/works/x", {})
        assert client._latched_unavailable is True

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"message": {"title": ["Ok"]}}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.side_effect = None
        mock_urlopen.return_value = mock_resp
        mock_clock.return_value = 1400.0

        result = client._get("/works/y", {})
        assert result is not None
        assert client._latched_unavailable is False


class TestOutageLatchCooldownFromActivation:
    """F1 (Judgment Day R1): cooldown measured from latch ACTIVATION
    (_latch_set_at), not from _last_request_at. The first-request-failure
    edge case (where _last_request_at is stale/zero) must NOT reset the
    latch instantly."""

    @patch("clients.crossref.urllib.request.urlopen")
    def test_first_request_failure_does_not_reset_instantly(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("network down")
        mock_clock = MagicMock(return_value=1_700_000_000.0)
        client = CrossrefClient(offline=False, sleep=MagicMock(), clock=mock_clock)
        client._get("/works/x", {})
        assert client._latched_unavailable is True
        assert client._latch_set_at == 1_700_000_000.0

        # 100s after activation: must STILL fail-fast (within 300s cooldown).
        mock_clock.return_value = 1_700_000_100.0
        mock_urlopen.side_effect = AssertionError("should fail-fast, not call urlopen")
        with pytest.raises(_TransientError):
            client._get("/works/y", {})
        assert client._latched_unavailable is True

    @patch("clients.crossref.urllib.request.urlopen")
    def test_latch_resets_exactly_after_cooldown_from_activation(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("down")
        mock_clock = MagicMock(return_value=5000.0)
        client = CrossrefClient(offline=False, sleep=MagicMock(), clock=mock_clock)
        client._get("/works/x", {})
        assert client._latch_set_at == 5000.0

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"message": {"title": ["Ok"]}}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.side_effect = None
        mock_urlopen.return_value = mock_resp
        mock_clock.return_value = 5301.0

        result = client._get("/works/y", {})
        assert result is not None
        assert client._latched_unavailable is False

    @patch("clients.crossref.urllib.request.urlopen")
    def test_latch_set_at_independent_of_last_request_at(self, mock_urlopen):
        """T1 (Judgment Day R2): exercise the DIVERGENCE between
        _last_request_at and _latch_set_at. A successful request at t=100
        sets _last_request_at=100; a later transport failure at t=200 sets
        _latch_set_at=200. The cooldown must be measured from 200, not 100."""
        # Successful request at t=100
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"message": {"title": ["Ok"]}}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        mock_clock = MagicMock(return_value=100.0)
        client = CrossrefClient(offline=False, sleep=MagicMock(), clock=mock_clock)
        client._get("/works/x", {})
        assert client._last_request_at == 100.0

        # Transport failure at t=200 latches
        mock_urlopen.side_effect = TimeoutError("down")
        mock_clock.return_value = 200.0
        client._get("/works/x", {})
        assert client._latched_unavailable is True
        assert client._latch_set_at == 200.0
        # _last_request_at was updated to 200 at _get entry too
        assert client._last_request_at == 200.0

        # At t=350 (150s after latch, but 250s after last success): within cooldown
        mock_clock.return_value = 350.0
        mock_urlopen.side_effect = AssertionError("should fail-fast")
        with pytest.raises(_TransientError):
            client._get("/works/y", {})

        # At t=550 (350s after latch activation): past cooldown → reset + real request
        mock_urlopen.side_effect = None
        mock_urlopen.return_value = mock_resp
        mock_clock.return_value = 550.0
        result = client._get("/works/y", {})
        assert result is not None
        assert client._latched_unavailable is False


class TestLatchFailFastIsTransient:
    """W4 (Judgment Day R2): when the latch fail-fasts within cooldown,
    the result surfaced via the PUBLIC API must carry transient_error=True
    (not plain found=False), so upstream does not classify latched
    citations as not_found/fabrication."""

    @patch("clients.crossref.urllib.request.urlopen")
    def test_latched_verify_doi_returns_transient(self, mock_urlopen):
        # Activate latch via transport error
        mock_urlopen.side_effect = TimeoutError("network down")
        mock_clock = MagicMock(return_value=1000.0)
        client = CrossrefClient(offline=False, sleep=MagicMock(), clock=mock_clock)
        client.verify_doi("10.1000/first")  # latches
        assert client._latched_unavailable is True

        # Second call within cooldown via public API: must be transient
        mock_clock.return_value = 1100.0
        result = client.verify_doi("10.1000/second")
        assert result.found is False
        assert result.transient_error is True

    @patch("clients.crossref.urllib.request.urlopen")
    def test_latched_search_by_title_returns_transient(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("network down")
        mock_clock = MagicMock(return_value=1000.0)
        client = CrossrefClient(offline=False, sleep=MagicMock(), clock=mock_clock)
        client.search_by_title("anything")  # latches
        assert client._latched_unavailable is True

        mock_clock.return_value = 1100.0
        results = client.search_by_title("anything")
        assert len(results) == 1
        assert results[0].found is False
        assert results[0].transient_error is True


class TestRateLimitExhaustedTransient:
    """Bug 3 P1: when 429 retries exhaust, the result must surface as
    transient_error=True, NOT as a plain found=False (which upstream
    classifies as not_found/fabrication)."""

    @patch("clients.crossref.urllib.request.urlopen")
    def test_429_exhausted_surfaces_transient_in_verify_doi(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=429, msg="Too Many Requests", hdrs=None, fp=None
        )
        client = CrossrefClient(offline=False, sleep=MagicMock())
        result = client.verify_doi("10.1000/test")
        assert result.found is False
        assert result.transient_error is True

    @patch("clients.crossref.urllib.request.urlopen")
    def test_429_exhausted_surfaces_transient_in_search(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=429, msg="Too Many Requests", hdrs=None, fp=None
        )
        client = CrossrefClient(offline=False, sleep=MagicMock())
        results = client.search_by_title("anything")
        assert len(results) == 1
        assert results[0].transient_error is True

    @patch("clients.crossref.urllib.request.urlopen")
    def test_429_then_success_is_not_transient(self, mock_urlopen):
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None)
            resp = MagicMock()
            resp.read.return_value = json.dumps(
                {"message": {"title": ["Test"], "author": [], "issued": {"date-parts": [[2023]]}}}
            ).encode()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        mock_urlopen.side_effect = side_effect
        client = CrossrefClient(offline=False, sleep=MagicMock())
        result = client.verify_doi("10.1000/test")
        assert result.found is True
        assert result.transient_error is False


class TestCrossrefResultTransientField:
    def test_default_transient_error_false(self):
        r = CrossrefResult(found=False)
        assert r.transient_error is False
