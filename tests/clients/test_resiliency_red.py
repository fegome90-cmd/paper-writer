import pytest
import time
import urllib.error
from unittest.mock import MagicMock, patch
from clients.semantic_scholar import SemanticScholarClient
from clients.crossref import CrossrefClient

def test_s2_latch_presence():
    client = SemanticScholarClient()
    assert hasattr(client, "_latched_unavailable")

def test_s2_di_presence():
    client = SemanticScholarClient(sleep=lambda x: None, clock=lambda: 123.0)
    assert client._sleep is not None
    assert client._clock() == 123.0

def test_s2_latch_behavior_url_error():
    client = SemanticScholarClient()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail")):
        client._get("/test")
    
    assert client._latched_unavailable is True

def test_s2_latch_behavior_os_error():
    client = SemanticScholarClient()
    mock_resp = MagicMock()
    mock_resp.read.side_effect = OSError("socket drop")
    mock_resp.__enter__.return_value = mock_resp
    
    with patch("urllib.request.urlopen", return_value=mock_resp):
        client._get("/test")
        
    assert client._latched_unavailable is True

def test_year_tiebreaker():
    client = CrossrefClient()
    mock_data = {
        "message": {
            "items": [
                {"title": ["Artificial Intelligence"], "issued": {"date-parts": [[2020]]}, "DOI": "1"},
                {"title": ["Artificial Intelligence"], "issued": {"date-parts": [[2022]]}, "DOI": "2"}
            ]
        }
    }
    with patch.object(client, "_get", return_value=mock_data):
        results = client.search_by_title("Artificial Intelligence", year=2022)
        assert len(results) == 2
        assert results[0].doi == "2" # 2022 won the tie
