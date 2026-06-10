"""Tests for extended Zotero write API features.

Covers: get_item, delete_items (batch), search_items (full-text).
"""

from unittest.mock import MagicMock, patch

import pytest

from clients.zotero import ZoteroClient, ZoteroConfig, ZoteroError


def _config() -> ZoteroConfig:
    return ZoteroConfig(user_id="12345", api_key="secret-key")


# ------------------------------------------------------------------
# get_item
# ------------------------------------------------------------------


class TestGetItem:
    def test_get_item_valid_key(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)
        item_data = {"key": "ABCD2345", "itemType": "book", "title": "Test Book", "version": 1}

        with patch.object(client, "_get", return_value=(item_data, {})):
            result = client.get_item("ABCD2345")
        assert result["key"] == "ABCD2345"
        assert result["title"] == "Test Book"

    def test_get_item_invalid_key(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)
        with pytest.raises(ValueError, match="Invalid item_key"):
            client.get_item("bad/key!")

    def test_get_item_url(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=({"key": "ABCD2345"}, {})) as mock:
            client.get_item("ABCD2345")
            call_url = mock.call_args[0][0]
            assert "/items/ABCD2345" in call_url
            assert "users/12345" in call_url

    def test_get_item_group_library(self) -> None:
        config = ZoteroConfig(user_id="99", api_key="k", library_type="group")
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=({"key": "ABCD2345"}, {})) as mock:
            client.get_item("ABCD2345")
            call_url = mock.call_args[0][0]
            assert "groups/99" in call_url

    def test_get_item_non_dict_response(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=([], {})):
            with pytest.raises(ZoteroError, match="Unexpected"):
                client.get_item("ABCD2345")


# ------------------------------------------------------------------
# delete_items (batch)
# ------------------------------------------------------------------


class TestDeleteItems:
    @patch.object(ZoteroClient, "_delete")
    def test_batch_delete_single(self, mock_delete: MagicMock) -> None:
        mock_delete.return_value = {"Last-Modified-Version": "50"}
        config = _config()
        client = ZoteroClient(config=config)
        headers = client.delete_items(["ABCD2345"], library_version=42)

        assert headers["Last-Modified-Version"] == "50"
        call_url = mock_delete.call_args[0][0]
        assert "itemKey=ABCD2345" in call_url

    @patch.object(ZoteroClient, "_delete")
    def test_batch_delete_multiple(self, mock_delete: MagicMock) -> None:
        mock_delete.return_value = {"Last-Modified-Version": "51"}
        config = _config()
        client = ZoteroClient(config=config)
        keys = ["ABCD2345", "EFGH6789", "IJKL2345"]
        client.delete_items(keys, library_version=10)

        call_url = mock_delete.call_args[0][0]
        assert "itemKey=" in call_url
        for k in keys:
            assert k in call_url

    @patch.object(ZoteroClient, "_delete")
    def test_batch_delete_max_50(self, mock_delete: MagicMock) -> None:
        mock_delete.return_value = {}
        config = _config()
        client = ZoteroClient(config=config)
        # Generate 50 valid 8-char keys using digits 2-9
        chars = "23456789ABCDEFGH"
        keys = []
        for i in range(50):
            k = "".join(chars[(i + j) % len(chars)] for j in range(6))
            keys.append(f"KK{k}")
        client.delete_items(keys[:50], library_version=1)
        assert mock_delete.called

    def test_batch_delete_over_50_rejected(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)
        chars = "23456789ABCDEFGH"
        keys = []
        for i in range(51):
            k = "".join(chars[(i + j) % len(chars)] for j in range(6))
            keys.append(f"KK{k}")
        with pytest.raises(ValueError, match="Cannot delete more than 50"):
            client.delete_items(keys, library_version=1)

    def test_batch_delete_empty_list(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)
        with pytest.raises(ValueError, match="at least one"):
            client.delete_items([], library_version=1)

    def test_batch_delete_invalid_key(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)
        with pytest.raises(ValueError, match="Invalid item_key"):
            client.delete_items(["ABCD2345", "bad!key"], library_version=1)

    @patch.object(ZoteroClient, "_delete")
    def test_batch_delete_version_header(self, mock_delete: MagicMock) -> None:
        mock_delete.return_value = {}
        config = _config()
        client = ZoteroClient(config=config)
        client.delete_items(["ABCD2345"], library_version=99)

        call_headers = mock_delete.call_args.kwargs.get("headers") or mock_delete.call_args[1].get(
            "headers"
        )
        assert call_headers["If-Unmodified-Since-Version"] == "99"

    @patch.object(ZoteroClient, "_delete")
    def test_batch_delete_url_encoded(self, mock_delete: MagicMock) -> None:
        mock_delete.return_value = {}
        config = _config()
        client = ZoteroClient(config=config)
        client.delete_items(["ABCD2345", "EFGH6789"], library_version=1)

        call_url = mock_delete.call_args[0][0]
        # Keys should be comma-separated in URL (may be URL-encoded as %2C)
        assert "ABCD2345" in call_url and "EFGH6789" in call_url


# ------------------------------------------------------------------
# search_items (full-text)
# ------------------------------------------------------------------


class TestSearchItems:
    def test_basic_search(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)
        items = [
            {"data": {"key": "ABCD2345", "itemType": "journalArticle", "title": "Deep Learning"}},
            {"data": {"key": "EFGH6789", "itemType": "book", "title": "Learning Deep"}},
        ]

        with patch.object(client, "_get", return_value=(items, {})):
            results = client.search_items("deep learning")
        assert len(results) == 2
        assert results[0]["title"] == "Deep Learning"

    def test_search_with_item_type(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=([], {})) as mock:
            client.search_items("quantum", item_type="journalArticle")
            call_url = mock.call_args[0][0]
            assert "itemType=journalArticle" in call_url

    def test_search_with_tag(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=([], {})) as mock:
            client.search_items("neural", tag="machine-learning")
            call_url = mock.call_args[0][0]
            assert "tag=" in call_url

    def test_search_with_collection(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=([], {})) as mock:
            client.search_items("test", collection_key="ABCD2345")
            call_url = mock.call_args[0][0]
            assert "/collections/ABCD2345/items" in call_url

    def test_search_invalid_collection(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)
        with pytest.raises(ValueError, match="Invalid collection_key"):
            client.search_items("test", collection_key="bad/key!")

    def test_search_pagination(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)

        page1 = [{"data": {"key": "ABCD2345", "title": "P1"}}]
        page2 = [{"data": {"key": "EFGH6789", "title": "P2"}}]

        with patch.object(client, "_get") as mock:
            mock.side_effect = [
                (page1, {"Link": '<https://api.zotero.org/users/12345/items?start=1>; rel="next"'}),
                (page2, {}),
            ]
            results = client.search_items("test")
        assert len(results) == 2

    def test_search_empty_results(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=([], {})):
            results = client.search_items("nonexistent")
        assert results == []

    def test_search_limit_capped_at_100(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=([], {})) as mock:
            client.search_items("test", limit=500)
            call_url = mock.call_args[0][0]
            assert "limit=100" in call_url

    def test_search_url_encoding(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=([], {})) as mock:
            client.search_items("deep learning & AI")
            call_url = mock.call_args[0][0]
            # The query should be URL-encoded
            assert "q=" in call_url

    def test_search_non_dict_items_skipped(self) -> None:
        config = _config()
        client = ZoteroClient(config=config)
        items = [
            "not a dict",
            {"data": {"key": "ABCD2345", "title": "Valid"}},
            {"no_data_key": True},
        ]

        with patch.object(client, "_get", return_value=(items, {})):
            results = client.search_items("test")
        assert len(results) == 1
        assert results[0]["key"] == "ABCD2345"
