"""Tests for Zotero sync client and tool wrapper."""

import os
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clients.zotero import ZoteroClient, ZoteroConfig, ZoteroError
from harness.ports.tool_wrapper import ToolNotAvailableError
from integrations.tools.zotero_sync import ZoteroSyncImporter


class TestZoteroConfig:
    def test_config_from_env_all(self) -> None:
        environ = {
            "ZOTERO_USER_ID": "12345",
            "ZOTERO_API_KEY": "secret-key",
            "ZOTERO_LIBRARY_TYPE": "group",
            "ZOTERO_LOCAL": "true",
            "ZOTERO_BBT_LOCAL": "true",
        }
        with patch.dict(os.environ, environ):
            config = ZoteroConfig.from_env()
            assert config.user_id == "12345"
            assert config.api_key == "secret-key"
            assert config.library_type == "group"
            assert config.local_mode is True
            assert config.bbt_local is True

    def test_config_from_env_missing_user_id(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(KeyError, match="ZOTERO_USER_ID"):
                ZoteroConfig.from_env()


class TestZoteroClient:
    @patch("urllib.request.urlopen")
    def test_fetch_bibtex_cloud_basic(self, mock_urlopen: MagicMock) -> None:
        # Create a mock response
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"@article{key1, title={Paper 1}}"
        mock_resp.headers = {"Last-Modified-Version": "42"}
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        config = ZoteroConfig(user_id="12345", api_key="secret-key")
        client = ZoteroClient(config)
        bib = client.fetch_bibtex()

        assert bib == "@article{key1, title={Paper 1}}"
        assert client.last_version == 42

        req = mock_urlopen.call_args[0][0]
        assert req.headers.get("Zotero-api-key") == "secret-key"
        assert req.headers.get("Zotero-api-version") == "3"
        assert "users/12345/items/top" in req.full_url

    @patch("urllib.request.urlopen")
    def test_fetch_bibtex_pagination(self, mock_urlopen: MagicMock) -> None:
        # Mocking multiple pages of results
        mock_resp_1 = MagicMock()
        mock_resp_1.read.return_value = b"@article{key1, title={Paper 1}}"
        mock_resp_1.headers = {
            "Link": (
                "<https://api.zotero.org/users/12345/items/top"
                '?format=bibtex&limit=100&start=100>; rel="next"'
            ),
            "Last-Modified-Version": "42",
        }
        mock_resp_1.__enter__ = lambda s: mock_resp_1
        mock_resp_1.__exit__ = MagicMock(return_value=False)

        mock_resp_2 = MagicMock()
        mock_resp_2.read.return_value = b"@article{key2, title={Paper 2}}"
        mock_resp_2.headers = {"Last-Modified-Version": "45"}
        mock_resp_2.__enter__ = lambda s: mock_resp_2
        mock_resp_2.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [mock_resp_1, mock_resp_2]

        config = ZoteroConfig(user_id="12345")
        client = ZoteroClient(config)
        bib = client.fetch_bibtex()

        assert bib == "@article{key1, title={Paper 1}}\n@article{key2, title={Paper 2}}"
        assert client.last_version == 45
        assert mock_urlopen.call_count == 2

    @patch("urllib.request.urlopen")
    def test_fetch_bibtex_incremental(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.headers = {"Last-Modified-Version": "100"}
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        config = ZoteroConfig(user_id="12345")
        client = ZoteroClient(config)
        client.fetch_bibtex(since_version=99)

        req = mock_urlopen.call_args[0][0]
        assert "since=99" in req.full_url

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_rate_limiting_retry(self, mock_sleep: MagicMock, mock_urlopen: MagicMock) -> None:
        # First request returns HTTPError 429, second succeeds
        mock_resp_err = MagicMock()
        mock_resp_err.headers = {"Retry-After": "2"}
        err = urllib.error.HTTPError(
            url="https://api.zotero.org",
            code=429,
            msg="Too Many Requests",
            hdrs=mock_resp_err.headers,
            fp=None,
        )

        mock_resp_ok = MagicMock()
        mock_resp_ok.read.return_value = b"@article{key1}"
        mock_resp_ok.headers = {}
        mock_resp_ok.__enter__ = lambda s: mock_resp_ok
        mock_resp_ok.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [err, mock_resp_ok]

        config = ZoteroConfig(user_id="12345")
        client = ZoteroClient(config)
        bib = client.fetch_bibtex()

        assert bib == "@article{key1}"
        mock_sleep.assert_called_once_with(2)
        assert mock_urlopen.call_count == 2

    @patch("urllib.request.urlopen")
    def test_bbt_local_pull(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"@article{key1, title={Local BBT}}"
        mock_resp.headers = {}
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        config = ZoteroConfig(user_id="my_user_id", bbt_local=True)
        client = ZoteroClient(config)
        bib = client.fetch_bibtex()

        assert bib == "@article{key1, title={Local BBT}}"
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:23119/better-bibtex/library?/1/library.bibtex"

    @patch("urllib.request.urlopen")
    def test_bbt_local_collection(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"@article{key1}"
        mock_resp.headers = {}
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        config = ZoteroConfig(user_id="my_user_id", bbt_local=True)
        client = ZoteroClient(config)
        bib = client.fetch_bibtex(collection_key="COL123")
        assert isinstance(bib, str)

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:23119/better-bibtex/collection?/1/COL123.bibtex"

    @patch("urllib.request.urlopen")
    def test_fetch_collections(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = (
            b'[{"data": {"key": "COL1", "name": "Collection 1", "parentCollection": false}}]'
        )
        mock_resp.headers = {}
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        config = ZoteroConfig(user_id="12345")
        client = ZoteroClient(config)
        cols = client.fetch_collections()

        assert len(cols) == 1
        assert cols[0]["key"] == "COL1"
        assert cols[0]["name"] == "Collection 1"


class TestZoteroSyncImporter:
    def test_is_available(self) -> None:
        with patch.dict(os.environ, {"ZOTERO_USER_ID": "123"}):
            assert ZoteroSyncImporter().is_available() is True
        with patch.dict(os.environ, {}, clear=True):
            assert ZoteroSyncImporter().is_available() is False

    def test_run_not_available_raises(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ToolNotAvailableError):
                ZoteroSyncImporter().run({}, {})

    @patch("integrations.tools.zotero_sync.ZoteroClient")
    def test_run_success(self, mock_client_cls: MagicMock, tmp_path: Path) -> None:
        mock_client = MagicMock()
        # Returns a valid entry
        mock_client.fetch_bibtex.return_value = (
            "@article{ok2024,\n"
            "  author = {Ok},\n"
            "  title = {OK},\n"
            "  journal = {J},\n"
            "  year = {2024},\n"
            "  doi = {10.1234/ok},\n"
            "}\n"
        )
        mock_client_cls.return_value = mock_client

        target = tmp_path / "references.bib"
        with patch.dict(os.environ, {"ZOTERO_USER_ID": "123"}):
            importer = ZoteroSyncImporter()
            result = importer.run({"target_bib": str(target)}, {})

        assert result.status == "pass"
        assert result.validator == "zotero-sync"
        assert target.exists()
        assert "ok2024" in target.read_text()

    @patch("integrations.tools.zotero_sync.ZoteroClient")
    def test_run_empty_response_fails(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.fetch_bibtex.return_value = "   \n "
        mock_client_cls.return_value = mock_client

        with patch.dict(os.environ, {"ZOTERO_USER_ID": "123"}):
            importer = ZoteroSyncImporter()
            result = importer.run({}, {})

        assert result.status == "fail"
        assert any(f["code"] == "empty_response" for f in result.findings)

    @patch("integrations.tools.zotero_sync.ZoteroClient")
    def test_run_client_error(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.fetch_bibtex.side_effect = ZoteroError("API key invalid")
        mock_client_cls.return_value = mock_client

        with patch.dict(os.environ, {"ZOTERO_USER_ID": "123"}):
            importer = ZoteroSyncImporter()
            result = importer.run({}, {})

        assert result.status == "fail"
        assert any(f["code"] == "zotero_api_error" for f in result.findings)
