import time
import pytest
import urllib.error
from unittest.mock import MagicMock, patch
from clients.crossref import CrossrefClient

def test_crossref_inter_retry_timing():
    current_time = 1000.0
    def fake_clock():
        return current_time
    
    def fake_sleep(seconds):
        nonlocal current_time
        current_time += seconds

    client = CrossrefClient(sleep=fake_sleep, clock=fake_clock)
    assert client._last_request_at == 0.0

    # Mock sequence: 429, then 200
    err = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"status": "ok"}'
    mock_resp.__enter__.return_value = mock_resp
    
    with patch("urllib.request.urlopen", side_effect=[err, mock_resp]):
        client._get("/test", {})
    
    # 1. T0 was 1000.0
    # 2. First request at 1000.0 fails with 429
    # 3. retry_with_backoff sleeps 2s -> clock becomes 1002.0
    # 4. on_retry is called -> _last_request_at becomes 1002.0
    # 5. Second request at 1002.0 succeeds
    # 6. _get sets _last_request_at to current clock (1002.0)
    
    assert client._last_request_at == 1002.0

def test_crossref_initial_t0_anchor():
    client = CrossrefClient()
    assert client._last_request_at == 0.0
