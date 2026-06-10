"""Tests for Zotero write API methods.

Tests use mocked urllib to verify request construction, header handling,
and response parsing for all write operations (POST, PUT, PATCH, DELETE).
"""

import hashlib
import json
import urllib.error
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clients.zotero import (
    ZoteroClient,
    ZoteroConfig,
    ZoteroError,
    _parse_retry_after,
)


def _make_config(**overrides: object) -> ZoteroConfig:
    defaults = {"user_id": "12345", "api_key": "secret-key"}
    defaults.update(overrides)
    return ZoteroConfig(**defaults)  # type: ignore[arg-type]


def _mock_response(
    data: bytes = b"",
    headers: dict[str, str] | None = None,
    status: int = 200,
) -> MagicMock:
    """Build a mock HTTP response."""
    resp = MagicMock()
    resp.read.return_value = data
    resp.headers = headers or {}
    resp.status = status
    resp.__enter__ = lambda s: resp
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ------------------------------------------------------------------
# _parse_retry_after
# ------------------------------------------------------------------


class TestParseRetryAfter:
    def test_valid_header(self) -> None:
        err = MagicMock()
        err.headers = {"Retry-After": "5"}
        result = _parse_retry_after(err)
        assert result == 5

    def test_missing_header(self) -> None:
        err = MagicMock()
        err.headers = {}
        result = _parse_retry_after(err)
        assert result == 10  # default

    def test_invalid_header(self) -> None:
        err = MagicMock()
        err.headers = {"Retry-After": "not-a-number"}
        result = _parse_retry_after(err)
        assert result == 10

    def test_custom_default(self) -> None:
        err = MagicMock()
        err.headers = {}
        result = _parse_retry_after(err, default=30)
        assert result == 30


# ------------------------------------------------------------------
# _require_api_key
# ------------------------------------------------------------------


class TestRequireApiKey:
    def test_raises_without_key(self) -> None:
        config = _make_config(api_key=None)
        client = ZoteroClient(config=config)
        with pytest.raises(ZoteroError, match="API key is required"):
            client._require_api_key()

    def test_returns_key(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)
        assert client._require_api_key() == "secret-key"


# ------------------------------------------------------------------
# _write_headers
# ------------------------------------------------------------------


class TestWriteHeaders:
    def test_includes_content_type(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)
        headers = client._write_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Zotero-API-Key"] == "secret-key"

    def test_merges_extra_headers(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)
        headers = client._write_headers({"If-Unmodified-Since-Version": "42"})
        assert headers["If-Unmodified-Since-Version"] == "42"


# ------------------------------------------------------------------
# _lib_prefix
# ------------------------------------------------------------------


class TestLibPrefix:
    def test_user_cloud(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)
        assert client._lib_prefix() == "https://api.zotero.org/users/12345"

    def test_group_cloud(self) -> None:
        config = _make_config(library_type="group")
        client = ZoteroClient(config=config)
        assert client._lib_prefix() == "https://api.zotero.org/groups/12345"

    def test_user_local(self) -> None:
        config = _make_config(local_mode=True)
        client = ZoteroClient(config=config)
        assert client._lib_prefix() == "http://localhost:23119/api/users/12345"


# ------------------------------------------------------------------
# create_items
# ------------------------------------------------------------------


class TestCreateItems:
    @patch.object(ZoteroClient, "_post")
    def test_create_single_item(self, mock_post: MagicMock) -> None:
        mock_post.return_value = (
            {"successful": {"0": {"key": "ABCD2345"}}, "unchanged": {}, "failed": {}},
            {},
        )
        config = _make_config()
        client = ZoteroClient(config=config)
        result = client.create_items([{"itemType": "book", "title": "Test"}])

        assert result["successful"]["0"]["key"] == "ABCD2345"
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        assert call_url.endswith("/items")

    @patch.object(ZoteroClient, "_post")
    def test_create_with_library_version(self, mock_post: MagicMock) -> None:
        mock_post.return_value = ({"successful": {}}, {})
        config = _make_config()
        client = ZoteroClient(config=config)
        client.create_items([{"itemType": "book"}], library_version=42)

        call_headers = mock_post.call_args[1].get("headers") or mock_post.call_args.kwargs.get(
            "headers"
        )
        assert call_headers is not None
        assert call_headers["If-Unmodified-Since-Version"] == "42"

    @patch.object(ZoteroClient, "_post")
    def test_create_with_write_token(self, mock_post: MagicMock) -> None:
        mock_post.return_value = ({"successful": {}}, {})
        config = _make_config()
        client = ZoteroClient(config=config)
        client.create_items([{"itemType": "book"}], write_token="abc123")

        call_headers = mock_post.call_args[1].get("headers") or mock_post.call_args.kwargs.get(
            "headers"
        )
        assert call_headers is not None
        assert call_headers["Zotero-Write-Token"] == "abc123"

    @patch.object(ZoteroClient, "_post")
    def test_create_with_failed_items(self, mock_post: MagicMock) -> None:
        mock_post.return_value = (
            {
                "successful": {"0": {"key": "MM234567"}},
                "failed": {"1": {"code": 400, "message": "Bad data"}},
            },
            {},
        )
        config = _make_config()
        client = ZoteroClient(config=config)
        result = client.create_items([{"itemType": "book"}, {"itemType": "invalid"}])
        assert "failed" in result
        assert result["failed"]["1"]["code"] == 400


# ------------------------------------------------------------------
# create_collection
# ------------------------------------------------------------------


class TestCreateCollection:
    @patch.object(ZoteroClient, "_post")
    def test_create_collection(self, mock_post: MagicMock) -> None:
        mock_post.return_value = (
            {"successful": {"0": {"key": "CC234567"}}},
            {},
        )
        config = _make_config()
        client = ZoteroClient(config=config)
        result = client.create_collection({"name": "My Collection"})

        assert result["successful"]["0"]["key"] == "CC234567"
        call_url = mock_post.call_args[0][0]
        assert call_url.endswith("/collections")


# ------------------------------------------------------------------
# update_item (PUT)
# ------------------------------------------------------------------


class TestUpdateItem:
    @patch.object(ZoteroClient, "_put")
    def test_update_item(self, mock_put: MagicMock) -> None:
        mock_put.return_value = (None, {"Last-Modified-Version": "43"})
        config = _make_config()
        client = ZoteroClient(config=config)
        headers = client.update_item("ABCD2345", {"key": "ABCD2345", "title": "Updated"}, version=1)

        assert headers["Last-Modified-Version"] == "43"
        call_url = mock_put.call_args[0][0]
        assert "/items/ABCD2345" in call_url


# ------------------------------------------------------------------
# partial_update_item (PATCH)
# ------------------------------------------------------------------


class TestPartialUpdateItem:
    @patch.object(ZoteroClient, "_patch")
    def test_partial_update(self, mock_patch: MagicMock) -> None:
        mock_patch.return_value = (None, {})
        config = _make_config()
        client = ZoteroClient(config=config)
        client.partial_update_item("ABCD2345", {"title": "New Title"}, version=5)

        call_url = mock_patch.call_args[0][0]
        assert "/items/ABCD2345" in call_url
        call_data = mock_patch.call_args[0][1]
        parsed = json.loads(call_data)
        assert parsed["title"] == "New Title"


# ------------------------------------------------------------------
# delete_item
# ------------------------------------------------------------------


class TestDeleteItem:
    @patch.object(ZoteroClient, "_delete")
    def test_delete_item(self, mock_delete: MagicMock) -> None:
        mock_delete.return_value = {"Last-Modified-Version": "44"}
        config = _make_config()
        client = ZoteroClient(config=config)
        headers = client.delete_item("ABCD2345", version=2)

        assert headers["Last-Modified-Version"] == "44"
        call_url = mock_delete.call_args[0][0]
        assert "/items/ABCD2345" in call_url


# ------------------------------------------------------------------
# get_item_template
# ------------------------------------------------------------------


class TestGetItemTemplate:
    def test_get_journal_article_template(self) -> None:
        template_data = {"itemType": "journalArticle", "title": "", "creators": []}
        config = _make_config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=(template_data, {})):
            result = client.get_item_template("journalArticle")

        assert result["itemType"] == "journalArticle"

    def test_template_url_encoded(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_get", return_value=({"itemType": "book"}, {})) as mock_get:
            client.get_item_template("book")
            call_url = mock_get.call_args[0][0]
            assert "itemType=book" in call_url


# ------------------------------------------------------------------
# _post (low-level)
# ------------------------------------------------------------------


class TestPostLowLevel:
    def test_post_json_success(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)
        resp_data = json.dumps({"key": "ABCD2345"}).encode("utf-8")

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            opener.open.return_value = _mock_response(resp_data)
            mock_opener.return_value = opener
            client._opener = opener

            body, _headers = client._post(
                "https://api.zotero.org/users/12345/items", b'{"itemType":"book"}'
            )
            assert isinstance(body, dict)
            assert body["key"] == "ABCD2345"

    def test_post_raises_on_412(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            http_err = urllib.error.HTTPError(
                "https://api.zotero.org/users/12345/items",
                412,
                "Precondition Failed",
                {},
                None,
            )
            opener.open.side_effect = http_err
            mock_opener.return_value = opener
            client._opener = opener

            with pytest.raises(ZoteroError, match="412"):
                client._post("https://api.zotero.org/users/12345/items", b"data")

    def test_post_raises_on_409(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            http_err = urllib.error.HTTPError(
                "https://api.zotero.org/users/12345/items",
                409,
                "Conflict",
                {},
                None,
            )
            opener.open.side_effect = http_err
            mock_opener.return_value = opener
            client._opener = opener

            with pytest.raises(ZoteroError, match="409"):
                client._post("https://api.zotero.org/users/12345/items", b"data")

    def test_post_retries_on_429(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)
        resp_data = json.dumps({"ok": True}).encode("utf-8")

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            http_err = urllib.error.HTTPError(
                "https://api.zotero.org/users/12345/items",
                429,
                "Too Many Requests",
                {"Retry-After": "0"},
                None,
            )
            # First call: 429, second call: success
            opener.open.side_effect = [http_err, _mock_response(resp_data)]
            mock_opener.return_value = opener
            client._opener = opener

            with patch("clients.zotero.time.sleep"):
                body, _ = client._post("https://api.zotero.org/users/12345/items", b"data")
                assert isinstance(body, dict)
                assert body["ok"] is True

    def test_post_requires_api_key(self) -> None:
        config = _make_config(api_key=None)
        client = ZoteroClient(config=config)

        with pytest.raises(ZoteroError, match="API key is required"):
            client._post("https://api.zotero.org/users/12345/items", b"data")


# ------------------------------------------------------------------
# _put (low-level)
# ------------------------------------------------------------------


class TestPutLowLevel:
    def test_put_success(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            opener.open.return_value = _mock_response(b"", headers={"Last-Modified-Version": "43"})
            mock_opener.return_value = opener
            client._opener = opener

            _body, headers = client._put(
                "https://api.zotero.org/users/12345/items/ABCD2345", b"data"
            )
            assert headers["Last-Modified-Version"] == "43"


# ------------------------------------------------------------------
# _delete (low-level)
# ------------------------------------------------------------------


class TestDeleteLowLevel:
    def test_delete_success(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            opener.open.return_value = _mock_response(b"", headers={"Last-Modified-Version": "44"})
            mock_opener.return_value = opener
            client._opener = opener

            headers = client._delete("https://api.zotero.org/users/12345/items/ABCD2345")
            assert headers["Last-Modified-Version"] == "44"

    def test_delete_raises_on_412(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            http_err = urllib.error.HTTPError(
                "https://api.zotero.org/users/12345/items/ABCD2345",
                412,
                "Precondition Failed",
                {},
                None,
            )
            opener.open.side_effect = http_err
            mock_opener.return_value = opener
            client._opener = opener

            with pytest.raises(ZoteroError, match="412"):
                client._delete("https://api.zotero.org/users/12345/items/ABCD2345")


# ------------------------------------------------------------------
# create_attachment
# ------------------------------------------------------------------


class TestCreateAttachment:
    @patch.object(ZoteroClient, "create_items")
    @patch.object(ZoteroClient, "get_item_template")
    def test_create_attachment(self, mock_template: MagicMock, mock_create: MagicMock) -> None:
        mock_template.return_value = {
            "itemType": "attachment",
            "linkMode": "imported_file",
            "title": "",
            "filename": "",
            "contentType": "",
            "md5": None,
            "mtime": None,
        }
        mock_create.return_value = {
            "successful": {"0": {"key": "ATT23456"}},
            "unchanged": {},
            "failed": {},
        }

        config = _make_config()
        client = ZoteroClient(config=config)
        key = client.create_attachment("PARE2345", "paper.pdf")

        assert key == "ATT23456"
        mock_template.assert_called_once_with("attachment", link_mode="imported_file")
        # Verify the template was populated correctly
        sent_items = mock_create.call_args[0][0]
        assert sent_items[0]["parentItem"] == "PARE2345"
        assert sent_items[0]["filename"] == "paper.pdf"
        assert "md5" not in sent_items[0]

    @patch.object(ZoteroClient, "create_items")
    @patch.object(ZoteroClient, "get_item_template")
    def test_create_attachment_with_title(
        self, mock_template: MagicMock, mock_create: MagicMock
    ) -> None:
        mock_template.return_value = {
            "itemType": "attachment",
            "linkMode": "imported_file",
            "title": "",
            "filename": "",
            "contentType": "",
            "md5": None,
            "mtime": None,
        }
        mock_create.return_value = {
            "successful": {"0": {"key": "ATT99999"}},
            "unchanged": {},
            "failed": {},
        }

        config = _make_config()
        client = ZoteroClient(config=config)
        key = client.create_attachment("PARE2345", "doc.pdf", title="Full Text PDF")
        assert key == "ATT99999"


# ------------------------------------------------------------------
# upload_file
# ------------------------------------------------------------------


class TestUploadFile:
    @patch.object(ZoteroClient, "_post")
    def test_upload_file_exists(self, mock_post: MagicMock) -> None:
        """When file already exists on server, no upload needed."""
        mock_post.return_value = ({"exists": 1}, {})
        config = _make_config()
        client = ZoteroClient(config=config)

        with pytest.MonkeyPatch.context():
            # Create a temp file
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(b"fake pdf content")
                tmp_path = tmp.name

            try:
                result = client.upload_file("ATT23456", tmp_path)
                assert result["status"] == "exists"
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    def test_upload_file_not_found(self) -> None:
        config = _make_config()
        client = ZoteroClient(config=config)
        with pytest.raises(ZoteroError, match="File not found"):
            client.upload_file("ATT23456", "/nonexistent/file.pdf")

    @patch.object(ZoteroClient, "_post")
    def test_upload_file_full_flow(self, mock_post: MagicMock) -> None:
        """Test the full 3-step upload flow with mocked file."""
        import tempfile

        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test content for upload")
            tmp_path = tmp.name

        try:
            file_data = Path(tmp_path).read_bytes()
            file_md5 = hashlib.md5(file_data).hexdigest()

            # Step 1: Authorization response
            auth_response = {
                "url": "https://upload.zotero.org/upload",
                "contentType": "application/x-www-form-urlencoded",
                "prefix": "--boundary\r\n",
                "suffix": "\r\n--boundary--",
                "uploadKey": "upload-key-123",
            }

            # Step 3: Register response
            register_response = {"status": "registered"}

            # Mock _post to return different things for auth vs register
            mock_post.side_effect = [
                (auth_response, {}),  # Step 1: authorization
                (register_response, {}),  # Step 3: register
            ]

            config = _make_config()
            client = ZoteroClient(config=config)

            # Mock the file upload step (Step 2) by mocking opener
            with patch.object(client, "_make_opener") as mock_opener:
                opener = MagicMock()
                opener.open.return_value = _mock_response(b"201 Created")
                mock_opener.return_value = opener
                client._opener = opener

                result = client.upload_file("ATT23456", tmp_path)
                assert result["status"] == "uploaded"
                assert result["md5"] == file_md5
                assert result["size"] == len(file_data)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------


class TestWriteErrorHandling:
    def test_413_quota_exceeded(self) -> None:
        """413 Request Entity Too Large = storage quota exceeded."""
        config = _make_config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            http_err = urllib.error.HTTPError(
                "https://api.zotero.org/users/12345/items/ATT/file",
                413,
                "Request Entity Too Large",
                {},
                None,
            )
            opener.open.side_effect = http_err
            mock_opener.return_value = opener
            client._opener = opener

            with pytest.raises(ZoteroError, match="413"):
                client._post("https://api.zotero.org/users/12345/items/ATT/file", b"data")

    def test_428_precondition_required(self) -> None:
        """428 Precondition Required = missing version header."""
        config = _make_config()
        client = ZoteroClient(config=config)

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            http_err = urllib.error.HTTPError(
                "https://api.zotero.org/users/12345/items",
                428,
                "Precondition Required",
                {},
                None,
            )
            opener.open.side_effect = http_err
            mock_opener.return_value = opener
            client._opener = opener

            with pytest.raises(ZoteroError, match="428"):
                client._post("https://api.zotero.org/users/12345/items", b"data")


# ------------------------------------------------------------------
# Integration: full item creation flow
# ------------------------------------------------------------------


class TestItemCreationFlow:
    @patch.object(ZoteroClient, "_post")
    @patch.object(ZoteroClient, "get_item_template")
    def test_create_journal_article(self, mock_template: MagicMock, mock_post: MagicMock) -> None:
        """End-to-end: get template → fill → create item."""
        mock_template.return_value = {
            "itemType": "journalArticle",
            "title": "",
            "creators": [{"creatorType": "author", "firstName": "", "lastName": ""}],
            "abstractNote": "",
            "publicationTitle": "",
            "tags": [],
            "collections": [],
            "relations": {},
        }
        mock_post.return_value = (
            {"successful": {"0": {"key": "ART23456", "version": 1}}, "unchanged": {}, "failed": {}},
            {"Last-Modified-Version": "100"},
        )

        config = _make_config()
        client = ZoteroClient(config=config)

        template = client.get_item_template("journalArticle")
        template["title"] = "Deep Learning for Papers"
        template["creators"] = [{"creatorType": "author", "name": "Smith, John"}]
        template["publicationTitle"] = "Nature"

        result = client.create_items([template])
        assert result["successful"]["0"]["key"] == "ART23456"

    @patch.object(ZoteroClient, "_post")
    @patch.object(ZoteroClient, "_put")
    def test_create_then_update(self, mock_put: MagicMock, mock_post: MagicMock) -> None:
        """End-to-end: create item then update it."""
        mock_post.return_value = (
            {"successful": {"0": {"key": "ITEM2345", "version": 1}}},
            {},
        )
        mock_put.return_value = (None, {"Last-Modified-Version": "2"})

        config = _make_config()
        client = ZoteroClient(config=config)

        # Create
        create_result = client.create_items([{"itemType": "book", "title": "Original"}])
        item_data = create_result["successful"]["0"]

        # Update
        item_data["title"] = "Updated Title"
        headers = client.update_item(item_data["key"], item_data, version=item_data["version"])
        assert "Last-Modified-Version" in headers
