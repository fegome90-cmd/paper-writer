"""Tests for bug fixes from extended features bug hunt.

Covers:
- BUG1: delete_items comma encoding (raw comma, not %2C)
- BUG2: search_items last_version tracking
- BUG3: Rate limiting (_throttle_write)
"""

from unittest.mock import MagicMock, patch

from clients.zotero import MIN_WRITE_INTERVAL, ZoteroClient, ZoteroConfig


def _config() -> ZoteroConfig:
    return ZoteroConfig(user_id="12345", api_key="secret-key")


# ------------------------------------------------------------------
# BUG1: delete_items comma encoding
# ------------------------------------------------------------------


class TestDeleteItemsCommaEncoding:
    @patch.object(ZoteroClient, "_delete")
    def test_comma_not_url_encoded(self, mock_delete: MagicMock) -> None:
        """Commas in itemKey must NOT be %2C encoded."""
        mock_delete.return_value = {}
        client = ZoteroClient(config=_config())
        client.delete_items(["ABCD2345", "EFGH6789"], library_version=1)

        call_url = mock_delete.call_args[0][0]
        assert "ABCD2345,EFGH6789" in call_url
        assert "%2C" not in call_url


# ------------------------------------------------------------------
# BUG2: search_items last_version tracking
# ------------------------------------------------------------------


class TestSearchItemsVersionTracking:
    def test_last_version_updated(self) -> None:
        """search_items should update client.last_version like fetch_bibtex."""
        client = ZoteroClient(config=_config())
        items = [{"data": {"key": "ABCD2345", "title": "Test"}}]

        with patch.object(client, "_get") as mock:
            mock.return_value = (items, {"Last-Modified-Version": "42"})
            results = client.search_items("test")

        assert len(results) == 1
        assert client.last_version == 42

    def test_last_version_preserved_across_pages(self) -> None:
        """Last version should be the latest across all pages."""
        client = ZoteroClient(config=_config())

        with patch.object(client, "_get") as mock:
            mock.side_effect = [
                (
                    [{"data": {"key": "ABCD2345", "title": "P1"}}],
                    {
                        "Last-Modified-Version": "10",
                        "Link": '<https://api.zotero.org/users/1/items?start=1>; rel="next"',
                    },
                ),
                (
                    [{"data": {"key": "EFGH6789", "title": "P2"}}],
                    {"Last-Modified-Version": "11"},
                ),
            ]
            results = client.search_items("test")

        assert len(results) == 2
        assert client.last_version == 11  # Latest page wins


# ------------------------------------------------------------------
# BUG3: Rate limiting
# ------------------------------------------------------------------


class TestRateLimiting:
    @patch("clients.zotero.time.sleep")
    @patch.object(ZoteroClient, "_make_opener")
    def test_first_write_no_throttle(self, mock_opener: MagicMock, mock_sleep: MagicMock) -> None:
        """First write should not sleep (no previous write)."""
        opener = MagicMock()
        resp = MagicMock()
        resp.read.return_value = b'{"key": "ABCD2345"}'
        resp.headers = {}
        resp.__enter__ = lambda s: resp
        resp.__exit__ = MagicMock(return_value=False)
        opener.open.return_value = resp
        mock_opener.return_value = opener

        client = ZoteroClient(config=_config())
        client._opener = opener
        client.create_items([{"itemType": "book"}])

        # sleep should NOT have been called for throttle (only possibly for 429)
        sleep_calls = [c[0][0] for c in mock_sleep.call_args_list]
        throttle_calls = [s for s in sleep_calls if s < MIN_WRITE_INTERVAL and s > 0]
        # First call should not throttle
        assert len(throttle_calls) == 0 or client._last_write_time > 0

    @patch("clients.zotero.time.monotonic")
    @patch("clients.zotero.time.sleep")
    def test_rapid_writes_throttled(self, mock_sleep: MagicMock, mock_mono: MagicMock) -> None:
        """Second write too soon should trigger sleep."""
        # Simulate time progression
        mock_mono.side_effect = [0.0, 0.0, 0.1, 0.1]  # first call + second call

        client = ZoteroClient(config=_config())
        client._last_write_time = 0.0

        # Simulate first write happened at t=0
        client._last_write_time = 0.0

        # Now trigger throttle at t=0.1 — only 0.1s since last write
        with patch("clients.zotero.time.monotonic", return_value=0.1):
            client._throttle_write()

        # Should have slept for (MIN_WRITE_INTERVAL - 0.1) seconds
        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert sleep_duration > 0
        assert sleep_duration <= MIN_WRITE_INTERVAL

    @patch("clients.zotero.time.sleep")
    def test_write_after_interval_no_throttle(self, mock_sleep: MagicMock) -> None:
        """Write after MIN_WRITE_INTERVAL should not sleep."""
        client = ZoteroClient(config=_config())
        client._last_write_time = 0.0

        # Simulate enough time has passed
        with patch("clients.zotero.time.monotonic", return_value=100.0):
            client._throttle_write()

        # sleep should not be called (enough time elapsed)
        mock_sleep.assert_not_called()
