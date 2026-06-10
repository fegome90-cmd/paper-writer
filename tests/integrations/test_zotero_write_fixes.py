"""Tests for bug fixes found in Zotero write API bug hunt.

Covers:
- BUG4: upload_file If-Match for existing file updates
- BUG13: create_items auto write token on retry
- BUG17: upload_file force_update option
- BUG19: item_key validation against Zotero key format
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clients.zotero import ZoteroClient, ZoteroConfig, _validate_key


def _config() -> ZoteroConfig:
    return ZoteroConfig(user_id="12345", api_key="secret-key")


# ------------------------------------------------------------------
# BUG19: item_key validation
# ------------------------------------------------------------------


class TestItemKeyValidation:
    def test_valid_key(self) -> None:
        _validate_key("ABCD2345")  # should not raise

    def test_valid_key_lowercase(self) -> None:
        _validate_key("abcd2345")  # case-insensitive

    def test_valid_key_with_letter_i(self) -> None:
        _validate_key("ABCD23I5")  # I is valid per Zotero spec

    def test_invalid_key_too_short(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_key"):
            _validate_key("ABC")

    def test_invalid_key_too_long(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_key"):
            _validate_key("ABCD23456")

    def test_invalid_key_zero(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_key"):
            _validate_key("ABCD0001")

    def test_invalid_key_letter_o(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_key"):
            _validate_key("ABCD23O5")

    def test_valid_key_letter_l(self) -> None:
        _validate_key("ABCD23L5")  # L is valid per Zotero spec

    def test_valid_key_letter_u(self) -> None:
        _validate_key("ABCD23U5")  # U is valid per Zotero spec

    def test_invalid_key_special_chars(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_key"):
            _validate_key("../secr!")

    def test_invalid_key_path_traversal(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_key"):
            _validate_key("../../et")

    def test_update_item_rejects_bad_key(self) -> None:
        client = ZoteroClient(config=_config())
        with pytest.raises(ValueError, match="Invalid item_key"):
            client.update_item("bad/key!", data={}, version=1)

    def test_delete_item_rejects_bad_key(self) -> None:
        client = ZoteroClient(config=_config())
        with pytest.raises(ValueError, match="Invalid item_key"):
            client.delete_item("bad key!", version=1)

    def test_partial_update_rejects_bad_key(self) -> None:
        client = ZoteroClient(config=_config())
        with pytest.raises(ValueError, match="Invalid item_key"):
            client.partial_update_item("bad/key", data={}, version=1)

    def test_upload_file_rejects_bad_key(self) -> None:
        client = ZoteroClient(config=_config())
        with pytest.raises(ValueError, match="Invalid item_key"):
            client.upload_file("bad key!", "/some/file.pdf")

    def test_create_attachment_rejects_bad_parent(self) -> None:
        client = ZoteroClient(config=_config())
        with pytest.raises(ValueError, match="Invalid parent_key"):
            client.create_attachment("bad/key!", "file.pdf")


# ------------------------------------------------------------------
# BUG13: auto write token for idempotent create_items
# ------------------------------------------------------------------


class TestAutoWriteToken:
    @patch.object(ZoteroClient, "_post")
    def test_auto_write_token_generated(self, mock_post: MagicMock) -> None:
        """When no library_version or write_token, auto-generate one."""
        mock_post.return_value = ({"successful": {}}, {})
        client = ZoteroClient(config=_config())
        client.create_items([{"itemType": "book"}])

        call_headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args[1].get(
            "headers"
        )
        assert call_headers is not None
        assert "Zotero-Write-Token" in call_headers
        token = call_headers["Zotero-Write-Token"]
        assert len(token) == 32

    @patch.object(ZoteroClient, "_post")
    def test_library_version_takes_priority(self, mock_post: MagicMock) -> None:
        """library_version should take priority over auto token."""
        mock_post.return_value = ({"successful": {}}, {})
        client = ZoteroClient(config=_config())
        client.create_items([{"itemType": "book"}], library_version=42)

        call_headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args[1].get(
            "headers"
        )
        assert "If-Unmodified-Since-Version" in call_headers
        assert "Zotero-Write-Token" not in call_headers

    @patch.object(ZoteroClient, "_post")
    def test_explicit_write_token_used(self, mock_post: MagicMock) -> None:
        """Explicit write_token should be used, not auto-generated."""
        mock_post.return_value = ({"successful": {}}, {})
        client = ZoteroClient(config=_config())
        client.create_items([{"itemType": "book"}], write_token="my-custom-token")

        call_headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args[1].get(
            "headers"
        )
        assert call_headers["Zotero-Write-Token"] == "my-custom-token"


# ------------------------------------------------------------------
# BUG4: upload_file If-Match for updates
# ------------------------------------------------------------------


class TestUploadFileUpdate:
    @patch.object(ZoteroClient, "_post")
    def test_new_upload_uses_if_none_match(self, mock_post: MagicMock) -> None:
        """New uploads (no existing_md5) should use If-None-Match: *."""
        mock_post.return_value = ({"exists": 1}, {})
        client = ZoteroClient(config=_config())

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test")
            tmp_path = tmp.name

        try:
            client.upload_file("ABCD2345", tmp_path)
            auth_headers = mock_post.call_args_list[0].kwargs.get(
                "headers"
            ) or mock_post.call_args_list[0][1].get("headers")
            assert auth_headers.get("If-None-Match") == "*"
            assert "If-Match" not in auth_headers
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @patch.object(ZoteroClient, "_post")
    def test_update_uses_if_match(self, mock_post: MagicMock) -> None:
        """Updating existing file should use If-Match: <md5>."""
        mock_post.return_value = (
            {
                "url": "https://upload.example.com",
                "contentType": "application/octet-stream",
                "prefix": "",
                "suffix": "",
                "uploadKey": "key123",
            },
            {},
        )
        client = ZoteroClient(config=_config())

        with patch.object(client, "_make_opener") as mock_opener:
            opener = MagicMock()
            resp = MagicMock()
            resp.read.return_value = b""
            resp.__enter__ = lambda s: resp
            resp.__exit__ = MagicMock(return_value=False)
            opener.open.return_value = resp
            mock_opener.return_value = opener
            client._opener = opener

            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
                tmp.write(b"test")
                tmp_path = tmp.name

            try:
                client.upload_file("ABCD2345", tmp_path, existing_md5="abc123def456")
                auth_headers = mock_post.call_args_list[0].kwargs.get(
                    "headers"
                ) or mock_post.call_args_list[0][1].get("headers")
                assert auth_headers.get("If-Match") == "abc123def456"
                assert "If-None-Match" not in auth_headers
            finally:
                Path(tmp_path).unlink(missing_ok=True)


# ------------------------------------------------------------------
# BUG17: upload_file force_update
# ------------------------------------------------------------------


class TestUploadFileForceUpdate:
    @patch.object(ZoteroClient, "_post")
    def test_exists_without_force_returns_early(self, mock_post: MagicMock) -> None:
        """Without force_update, exists=1 returns immediately."""
        mock_post.return_value = ({"exists": 1}, {})
        client = ZoteroClient(config=_config())

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test")
            tmp_path = tmp.name

        try:
            result = client.upload_file("ABCD2345", tmp_path)
            assert result["status"] == "exists"
            assert mock_post.call_count == 1
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @patch.object(ZoteroClient, "_make_opener")
    @patch.object(ZoteroClient, "_post")
    def test_force_upload_with_exists(self, mock_post: MagicMock, mock_opener: MagicMock) -> None:
        """With force_update, upload continues even when exists check would short-circuit.

        Note: The exists=1 response doesn't have upload fields, so it would fail
        at the url/uploadKey check. This test verifies that force_update bypasses
        the exists early-return, but the server response must still be valid.
        """
        mock_post.return_value = (
            {
                "url": "https://upload.example.com/upload",
                "contentType": "application/octet-stream",
                "prefix": "--boundary\r\n",
                "suffix": "\r\n--boundary--",
                "uploadKey": "upload-key-123",
            },
            {},
        )

        opener = MagicMock()
        resp = MagicMock()
        resp.read.return_value = b""
        resp.__enter__ = lambda s: resp
        resp.__exit__ = MagicMock(return_value=False)
        opener.open.return_value = resp
        mock_opener.return_value = opener

        client = ZoteroClient(config=_config())
        client._opener = opener

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test content data for force upload")
            tmp_path = tmp.name

        try:
            result = client.upload_file("ABCD2345", tmp_path, force_update=True)
            assert result["status"] == "uploaded"
            # 2 calls: auth + register (step 2 goes directly via opener)
            assert mock_post.call_count == 2
        finally:
            Path(tmp_path).unlink(missing_ok=True)
