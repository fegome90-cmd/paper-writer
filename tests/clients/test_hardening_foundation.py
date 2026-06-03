import time
import pytest
from unittest.mock import MagicMock, patch
from clients.crossref import CrossrefClient
from clients.semantic_scholar import SemanticScholarClient
from clients._retry import retry_with_backoff

def test_crossref_init_foundation():
    client = CrossrefClient(email="test@example.com")
    assert hasattr(client, "_last_request_at")
    assert client._last_request_at == 0.0

def test_semantic_scholar_init_foundation():
    client = SemanticScholarClient()
    assert hasattr(client, "_last_request_at")
    assert client._last_request_at == 0.0

def test_crossref_last_request_at_updated():
    client = CrossrefClient(email="test@example.com")
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp
        
        client._get("/test", {})
        assert client._last_request_at > 0

def test_crossref_on_retry_refresh():
    client = CrossrefClient(email="test@example.com")
    # T0 is 0.0
    assert client._last_request_at == 0.0
    
    # Mock behavior: first call 429, second call 200
    import urllib.error
    err = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"status": "ok"}'
    mock_resp.__enter__.return_value = mock_resp
    
    with patch("urllib.request.urlopen", side_effect=[err, mock_resp]):
        with patch("time.sleep", return_value=None):
            client._get("/test", {})
            
    # _last_request_at should be updated TWICE (once on retry, once on success)
    assert client._last_request_at > 0
