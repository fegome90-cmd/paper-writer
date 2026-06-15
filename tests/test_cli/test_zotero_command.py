"""Unit tests for cli/paper/commands/zotero.py — 8 handlers (Fix A).

Closes the 22% coverage gap (only NEEDS-WORK finding from mr-thorough review).
All 8 handlers tested by mocking the lazy import `_zotero_client` so the real
ZoteroClient is never instantiated. A socket-blocking autouse fixture enforces
'no network risk' as a behaviorally-tested property, not a trust-me claim.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cli.paper.commands.zotero import (
    _cmd_zotero_collections,
    _cmd_zotero_create,
    _cmd_zotero_delete,
    _cmd_zotero_get,
    _cmd_zotero_search,
    _cmd_zotero_template,
    _cmd_zotero_update,
    _cmd_zotero_upload,
)
from cli.paper.errors import ExternalServiceError, UserInputError
from clients.zotero import ZoteroError


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """CR-2: block any real socket creation — enforces no-network as a property.

    Any test that forgets to patch _zotero_client (and thus instantiates the
    real ZoteroClient reaching the network) fails immediately rather than flaking.
    """
    import socket as _socket

    def _fail(*_a: object, **_k: object) -> None:
        pytest.fail("NETWORK LEAK: real socket created — did you patch _zotero_client?")

    monkeypatch.setattr(_socket, "socket", _fail)


def _mock_client() -> MagicMock:
    """A MagicMock Zotero client — all methods return sensible defaults."""
    client = MagicMock()
    client.config.local_mode = False
    return client


def _patch_client(
    client: MagicMock | None = None, error: str | None = None
) -> Any:
    """Patch _zotero_client to return (client, None) or (None, error)."""
    return patch(
        "cli.paper.commands.zotero._zotero_client",
        return_value=(client or _mock_client(), error),
    )


# --- _cmd_zotero_collections ---


class TestCollections:
    def test_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = _mock_client()
        client.fetch_collections.return_value = [
            {"key": "ABC12345", "name": "My Papers", "parentCollection": False}
        ]
        with _patch_client(client):
            _cmd_zotero_collections(MagicMock(local=False))
        out = capsys.readouterr().out
        assert "ABC12345" in out
        assert "My Papers" in out
        assert "1 collection(s)" in out

    def test_zotero_error_raises_external(self) -> None:
        client = _mock_client()
        client.fetch_collections.side_effect = ZoteroError("api down")
        with _patch_client(client):
            with pytest.raises(ExternalServiceError, match="api down"):
                _cmd_zotero_collections(MagicMock(local=False))

    def test_env_missing_raises_user_input(self) -> None:
        with _patch_client(error="ZOTERO_USER_ID is not set"):
            with pytest.raises(UserInputError, match="ZOTERO_USER_ID"):
                _cmd_zotero_collections(MagicMock(local=False))


# --- _cmd_zotero_search ---


class TestSearch:
    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = _mock_client()
        client.search_items.return_value = [{"key": "K1", "title": "Paper One"}]
        args = MagicMock(local=False, query="test", item_type=None, tag=None,
                         collection=None, limit=25, output_json=True)
        with _patch_client(client):
            _cmd_zotero_search(args)
        data = json.loads(capsys.readouterr().out)
        assert data[0]["key"] == "K1"

    def test_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = _mock_client()
        client.search_items.return_value = [
            {"key": "K1", "title": "Paper", "date": "2024", "itemType": "journalArticle"}
        ]
        args = MagicMock(local=False, query="test", item_type=None, tag=None,
                         collection=None, limit=25, output_json=False)
        with _patch_client(client):
            _cmd_zotero_search(args)
        out = capsys.readouterr().out
        assert "K1" in out
        assert "1 result(s)" in out

    def test_zotero_error_raises_external(self) -> None:
        client = _mock_client()
        client.search_items.side_effect = ZoteroError("timeout")
        args = MagicMock(local=False, query="x", item_type=None, tag=None,
                         collection=None, limit=25, output_json=False)
        with _patch_client(client):
            with pytest.raises(ExternalServiceError):
                _cmd_zotero_search(args)


# --- _cmd_zotero_get ---


class TestGet:
    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = _mock_client()
        client.get_item.return_value = {"key": "K1", "title": "Item"}
        args = MagicMock(local=False, key="K1", output_json=True)
        with _patch_client(client):
            _cmd_zotero_get(args)
        data = json.loads(capsys.readouterr().out)
        assert data["key"] == "K1"

    def test_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = _mock_client()
        client.get_item.return_value = {"data": {"title": "X", "dateAdded": "2024"}}
        args = MagicMock(local=False, key="K1", output_json=False)
        with _patch_client(client):
            _cmd_zotero_get(args)
        out = capsys.readouterr().out
        assert "title" in out
        assert "X" in out

    def test_zotero_error_raises_external(self) -> None:
        client = _mock_client()
        client.get_item.side_effect = ZoteroError("not found")
        args = MagicMock(local=False, key="K1", output_json=False)
        with _patch_client(client):
            with pytest.raises(ExternalServiceError):
                _cmd_zotero_get(args)


# --- _cmd_zotero_create ---


class TestCreate:
    def test_success_counts(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        items_file = tmp_path / "items.json"
        items_file.write_text(json.dumps([{"key": "K1", "title": "New"}]))
        client = _mock_client()
        client.create_items.return_value = {
            "successful": {"0": {"key": "K1", "title": "New"}},
            "failed": {},
            "unchanged": {},
        }
        args = MagicMock(local=False, file=str(items_file), collection=None)
        with _patch_client(client):
            _cmd_zotero_create(args)
        out = capsys.readouterr().out
        assert "Created: 1" in out

    def test_bad_json_raises_user_input(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json{{{")
        args = MagicMock(local=False, file=str(bad_file), collection=None)
        with _patch_client(client=_mock_client()):
            with pytest.raises(UserInputError):
                _cmd_zotero_create(args)

    def test_collection_merge(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        """Create with --collection merges collection into each item."""
        items_file = tmp_path / "items.json"
        items_file.write_text(json.dumps([{"key": "K1", "title": "New"}]))
        client = _mock_client()
        client.create_items.return_value = {
            "successful": {"0": {"key": "K1", "title": "New"}},
            "failed": {},
            "unchanged": {},
        }
        args = MagicMock(local=False, file=str(items_file), collection="COL12345")
        with _patch_client(client):
            _cmd_zotero_create(args)
        # Verify collection was merged into the item before create
        sent_items = client.create_items.call_args[0][0]
        assert "COL12345" in sent_items[0]["collections"]

    def test_zotero_error_raises_external(self, tmp_path: Path) -> None:
        items_file = tmp_path / "items.json"
        items_file.write_text(json.dumps([{"key": "K1"}]))
        client = _mock_client()
        client.create_items.side_effect = ZoteroError("quota exceeded")
        args = MagicMock(local=False, file=str(items_file), collection=None)
        with _patch_client(client):
            with pytest.raises(ExternalServiceError):
                _cmd_zotero_create(args)


# --- _cmd_zotero_template ---


class TestTemplate:
    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = _mock_client()
        client.get_item_template.return_value = {"itemType": "journalArticle"}
        args = MagicMock(local=False, item_type="journalArticle")
        with _patch_client(client):
            _cmd_zotero_template(args)
        data = json.loads(capsys.readouterr().out)
        assert data["itemType"] == "journalArticle"

    def test_zotero_error_raises_external(self) -> None:
        client = _mock_client()
        client.get_item_template.side_effect = ZoteroError("no template")
        args = MagicMock(local=False, item_type="journalArticle")
        with _patch_client(client):
            with pytest.raises(ExternalServiceError):
                _cmd_zotero_template(args)


# --- _cmd_zotero_update ---


class TestUpdate:
    def test_dry_run(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        changes_file = tmp_path / "changes.json"
        changes_file.write_text(json.dumps({"title": "Updated"}))
        client = _mock_client()
        args = MagicMock(local=False, key="K1", file=str(changes_file),
                         dry_run=True, partial=False, version=None)
        with _patch_client(client):
            _cmd_zotero_update(args)
        out = capsys.readouterr().out
        assert "[DRY RUN]" in out

    def test_zotero_error_raises_external(self, tmp_path: Path) -> None:
        changes_file = tmp_path / "changes.json"
        changes_file.write_text(json.dumps({"title": "X"}))
        client = _mock_client()
        # PUT path: get_item returns valid data, then update_item fails
        client.get_item.return_value = {"version": 1, "data": {"title": "Old", "version": 1}}
        client.update_item.side_effect = ZoteroError("conflict")
        args = MagicMock(local=False, key="K1", file=str(changes_file),
                         dry_run=False, partial=False, version=1)
        with _patch_client(client):
            with pytest.raises(ExternalServiceError):
                _cmd_zotero_update(args)

    def test_partial_patch_success(self, capsys: pytest.CaptureFixture[str],
                                   tmp_path: Path) -> None:
        """Partial update (PATCH) path with known version."""
        changes_file = tmp_path / "changes.json"
        changes_file.write_text(json.dumps({"title": "New"}))
        client = _mock_client()
        client.partial_update_item.return_value = {"Last-Modified-Version": 2}
        args = MagicMock(local=False, key="K1", file=str(changes_file),
                         dry_run=False, partial=True, version=1)
        with _patch_client(client):
            _cmd_zotero_update(args)
        out = capsys.readouterr().out
        assert "Updated K1" in out

    def test_put_merge_success(self, capsys: pytest.CaptureFixture[str],
                               tmp_path: Path) -> None:
        """Full PUT path: get current item, merge changes, update."""
        changes_file = tmp_path / "changes.json"
        changes_file.write_text(json.dumps({"title": "Merged"}))
        client = _mock_client()
        client.get_item.return_value = {
            "version": 1, "data": {"title": "Old", "key": "K1", "version": 1}
        }
        client.update_item.return_value = {"Last-Modified-Version": 2}
        args = MagicMock(local=False, key="K1", file=str(changes_file),
                         dry_run=False, partial=False, version=1)
        with _patch_client(client):
            _cmd_zotero_update(args)
        out = capsys.readouterr().out
        assert "Updated K1" in out


# --- _cmd_zotero_delete ---


class TestDelete:
    def test_dry_run(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = _mock_client()
        args = MagicMock(local=False, keys=["K1"], dry_run=True, yes=False, version=None)
        with _patch_client(client):
            _cmd_zotero_delete(args)
        out = capsys.readouterr().out
        assert "[DRY RUN]" in out

    def test_decline_cancel(self, capsys: pytest.CaptureFixture[str],
                            monkeypatch: pytest.MonkeyPatch) -> None:
        client = _mock_client()
        monkeypatch.setattr("builtins.input", lambda _: "n")
        args = MagicMock(local=False, keys=["K1"], dry_run=False, yes=False, version=None)
        with _patch_client(client):
            _cmd_zotero_delete(args)
        out = capsys.readouterr().out
        assert "Cancelled." in out

    def test_zotero_error_raises_external(self) -> None:
        client = _mock_client()
        client.delete_item.side_effect = ZoteroError("forbidden")
        args = MagicMock(local=False, keys=["K1"], dry_run=False, yes=True, version=1)
        with _patch_client(client):
            with pytest.raises(ExternalServiceError):
                _cmd_zotero_delete(args)

    def test_single_delete_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Single item delete with auto-detected version."""
        client = _mock_client()
        client.get_item.return_value = {"version": 3}
        client.delete_item.return_value = None
        args = MagicMock(local=False, keys=["K1"], dry_run=False, yes=True, version=None)
        with _patch_client(client):
            _cmd_zotero_delete(args)
        out = capsys.readouterr().out
        assert "Deleted K1" in out

    def test_batch_delete_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Batch delete with explicit library version."""
        client = _mock_client()
        client.delete_items.return_value = None
        args = MagicMock(local=False, keys=["K1", "K2"], dry_run=False, yes=True, version=5)
        with _patch_client(client):
            _cmd_zotero_delete(args)
        out = capsys.readouterr().out
        assert "Deleted 2 items" in out


# --- _cmd_zotero_upload ---


class TestUpload:
    def test_success(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        upload_file = tmp_path / "doc.pdf"
        upload_file.write_bytes(b"%PDF-1.4")
        client = _mock_client()
        client.upload_file.return_value = {
            "status": "uploaded", "filename": "doc.pdf", "size": 8, "md5": "abc"
        }
        args = MagicMock(local=False, key="K1", file=str(upload_file),
                         existing_md5=None, force=False)
        with _patch_client(client):
            _cmd_zotero_upload(args)
        out = capsys.readouterr().out
        assert "uploaded" in out
        assert "doc.pdf" in out

    def test_already_exists(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        upload_file = tmp_path / "doc.pdf"
        upload_file.write_bytes(b"%PDF")
        client = _mock_client()
        client.upload_file.return_value = {"status": "exists", "message": "already there"}
        args = MagicMock(local=False, key="K1", file=str(upload_file),
                         existing_md5=None, force=False)
        with _patch_client(client):
            _cmd_zotero_upload(args)
        out = capsys.readouterr().out
        assert "already there" in out

    def test_zotero_error_raises_external(self, tmp_path: Path) -> None:
        upload_file = tmp_path / "doc.pdf"
        upload_file.write_bytes(b"%PDF")
        client = _mock_client()
        client.upload_file.side_effect = ZoteroError("too large")
        args = MagicMock(local=False, key="K1", file=str(upload_file),
                         existing_md5=None, force=False)
        with _patch_client(client):
            with pytest.raises(ExternalServiceError):
                _cmd_zotero_upload(args)
