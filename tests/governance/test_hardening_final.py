import logging
from unittest.mock import MagicMock, patch

from clients.crossref import CrossrefClient
from clients.semantic_scholar import SemanticScholarClient


class TestHardeningErrors:
    def test_crossref_json_decode_error(self, caplog):
        client = CrossrefClient()
        with patch("clients.crossref.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'invalid json'
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp
            
            with caplog.at_level(logging.WARNING):
                res = client._get("/test", {})
                assert res is None
                assert "Request failed: JSONDecodeError" in caplog.text

    def test_semantic_scholar_unicode_error(self, caplog):
        client = SemanticScholarClient()
        with patch("clients.semantic_scholar.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'\xff\xfe'
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp
            
            with caplog.at_level(logging.WARNING):
                res = client._get("/test")
                assert res is None
                assert "Request failed: UnicodeDecodeError" in caplog.text

class TestHardeningPolite:
    def test_crossref_polite_env_var(self, monkeypatch):
        monkeypatch.setenv("CROSSREF_POLITE_EMAIL", "env@example.com")
        client = CrossrefClient()
        assert client.email == "env@example.com"

    def test_crossref_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("CROSSREF_POLITE_EMAIL", "env@example.com")
        client = CrossrefClient(email="explicit@example.com")
        assert client.email == "explicit@example.com"
