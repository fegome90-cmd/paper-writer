import pytest
import urllib.error
import json
import logging
from unittest.mock import MagicMock, patch
from clients.crossref import CrossrefClient, CrossrefResult
from clients.semantic_scholar import SemanticScholarClient, S2Result

def test_crossref_json_decode_error(caplog):
    client = CrossrefClient()
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'invalid json'
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp
        
        with caplog.at_level(logging.WARNING):
            res = client._get("/test", {})
            assert res is None
            assert "Request failed: JSONDecodeError" in caplog.text

def test_crossref_verify_doi_url_error():
    client = CrossrefClient()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("reason")):
        res = client.verify_doi("10.1234/test")
        assert isinstance(res, CrossrefResult)
        assert res.found is False

def test_semantic_scholar_unicode_error(caplog):
    client = SemanticScholarClient()
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        # Trigger UnicodeDecodeError on read().decode("utf-8")
        mock_resp.read.return_value = b'\xff\xfe'
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp
        
        with caplog.at_level(logging.WARNING):
            res = client._get("/test")
            assert res is None
            assert "Request failed: UnicodeDecodeError" in caplog.text
