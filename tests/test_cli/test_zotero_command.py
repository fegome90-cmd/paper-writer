"""Unit tests for cli/paper/commands/zotero.py — 8 handlers + register_zotero.

Closes the coverage gap to the --cov-fail-under=70 gate (Fix A, S19).
All 8 handlers tested by mocking the lazy import `_zotero_client` so the real
ZoteroClient is never instantiated. A socket-blocking autouse fixture enforces
'no network risk' as a behaviorally-tested property, not a trust-me claim.

register_zotero() is covered via argparse _actions introspection mirroring
test_clean_cancel.py / test_output_policy_registry.py.
"""

from __future__ import annotations

import argparse
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
    register_zotero,
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


def _patch_client(client: MagicMock | None = None, error: str | None = None) -> Any:
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
        args = MagicMock(
            local=False,
            query="test",
            item_type=None,
            tag=None,
            collection=None,
            limit=25,
            output_json=True,
        )
        with _patch_client(client):
            _cmd_zotero_search(args)
        data = json.loads(capsys.readouterr().out)
        assert data[0]["key"] == "K1"

    def test_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        client = _mock_client()
        client.search_items.return_value = [
            {"key": "K1", "title": "Paper", "date": "2024", "itemType": "journalArticle"}
        ]
        args = MagicMock(
            local=False,
            query="test",
            item_type=None,
            tag=None,
            collection=None,
            limit=25,
            output_json=False,
        )
        with _patch_client(client):
            _cmd_zotero_search(args)
        out = capsys.readouterr().out
        assert "K1" in out
        assert "1 result(s)" in out

    def test_zotero_error_raises_external(self) -> None:
        client = _mock_client()
        client.search_items.side_effect = ZoteroError("timeout")
        args = MagicMock(
            local=False,
            query="x",
            item_type=None,
            tag=None,
            collection=None,
            limit=25,
            output_json=False,
        )
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
        args = MagicMock(
            local=False, key="K1", file=str(changes_file), dry_run=True, partial=False, version=None
        )
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
        args = MagicMock(
            local=False, key="K1", file=str(changes_file), dry_run=False, partial=False, version=1
        )
        with _patch_client(client):
            with pytest.raises(ExternalServiceError):
                _cmd_zotero_update(args)

    def test_partial_patch_success(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Partial update (PATCH) path with known version."""
        changes_file = tmp_path / "changes.json"
        changes_file.write_text(json.dumps({"title": "New"}))
        client = _mock_client()
        client.partial_update_item.return_value = {"Last-Modified-Version": 2}
        args = MagicMock(
            local=False, key="K1", file=str(changes_file), dry_run=False, partial=True, version=1
        )
        with _patch_client(client):
            _cmd_zotero_update(args)
        out = capsys.readouterr().out
        assert "Updated K1" in out

    def test_put_merge_success(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        """Full PUT path: get current item, merge changes, update."""
        changes_file = tmp_path / "changes.json"
        changes_file.write_text(json.dumps({"title": "Merged"}))
        client = _mock_client()
        client.get_item.return_value = {
            "version": 1,
            "data": {"title": "Old", "key": "K1", "version": 1},
        }
        client.update_item.return_value = {"Last-Modified-Version": 2}
        args = MagicMock(
            local=False, key="K1", file=str(changes_file), dry_run=False, partial=False, version=1
        )
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

    def test_decline_cancel(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
            "status": "uploaded",
            "filename": "doc.pdf",
            "size": 8,
            "md5": "abc",
        }
        args = MagicMock(
            local=False, key="K1", file=str(upload_file), existing_md5=None, force=False
        )
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
        args = MagicMock(
            local=False, key="K1", file=str(upload_file), existing_md5=None, force=False
        )
        with _patch_client(client):
            _cmd_zotero_upload(args)
        out = capsys.readouterr().out
        assert "already there" in out

    def test_zotero_error_raises_external(self, tmp_path: Path) -> None:
        upload_file = tmp_path / "doc.pdf"
        upload_file.write_bytes(b"%PDF")
        client = _mock_client()
        client.upload_file.side_effect = ZoteroError("too large")
        args = MagicMock(
            local=False, key="K1", file=str(upload_file), existing_md5=None, force=False
        )
        with _patch_client(client):
            with pytest.raises(ExternalServiceError):
                _cmd_zotero_upload(args)

    def test_env_missing_raises_user_input(self) -> None:
        """upload env-missing path raises UserInputError (line 288)."""
        with _patch_client(error="ZOTERO_USER_ID is not set"):
            with pytest.raises(UserInputError, match="ZOTERO_USER_ID"):
                _cmd_zotero_upload(
                    MagicMock(local=False, key="K1", file="x", existing_md5=None, force=False)
                )


# --- _zotero_client body (lines 19-29) ---


class TestZoteroClientFactory:
    """Cover the real _zotero_client body (success + local-mode branch).

    The handler tests patch _zotero_client entirely, bypassing its body.
    These tests exercise the real function with mocked ZoteroConfig.from_env
    and ZoteroClient so the lazy-import + dataclasses.replace lines are hit.
    """

    def test_cloud_mode_returns_client(self) -> None:
        """Cloud mode (local=False): from_env → ZoteroClient(config)."""
        from cli.paper.commands import zotero as zotero_mod

        fake_config = MagicMock()
        fake_client = MagicMock()
        with (
            patch("clients.zotero.ZoteroConfig.from_env", return_value=fake_config),
            patch("clients.zotero.ZoteroClient", return_value=fake_client) as mock_client,
        ):
            client, err = zotero_mod._zotero_client(local=False)
        assert err is None
        assert client is fake_client
        mock_client.assert_called_once_with(config=fake_config)

    def test_local_mode_replaces_config(self) -> None:
        """Local mode (local=True): dataclasses.replace flips local_mode."""
        from cli.paper.commands import zotero as zotero_mod

        fake_config = MagicMock()
        fake_client = MagicMock()
        with (
            patch("clients.zotero.ZoteroConfig.from_env", return_value=fake_config),
            patch("clients.zotero.ZoteroClient", return_value=fake_client),
            patch("dataclasses.replace", return_value=fake_config) as mock_replace,
        ):
            client, err = zotero_mod._zotero_client(local=True)
        assert err is None
        assert client is fake_client
        mock_replace.assert_called_once_with(fake_config, local_mode=True)

    def test_env_missing_returns_error(self) -> None:
        """KeyError from from_env → (None, error_msg)."""
        from cli.paper.commands import zotero as zotero_mod

        with patch("clients.zotero.ZoteroConfig.from_env", side_effect=KeyError("ZOTERO_USER_ID")):
            client, err = zotero_mod._zotero_client()
        assert client is None
        assert err == "ZOTERO_USER_ID"


# --- env-missing branches across all handlers (lines 55, 84, 106, 148, 163, 229) ---


class TestEnvMissingBranches:
    """Each handler's `if err: raise UserInputError(err)` branch.

    collections is covered above; these cover the SAME branch in search, get,
    create, template, update, delete (upload covered in TestUpload).
    """

    @pytest.mark.parametrize(
        "handler,kwargs",
        [
            (
                _cmd_zotero_search,
                {
                    "query": "x",
                    "item_type": None,
                    "tag": None,
                    "collection": None,
                    "limit": 25,
                    "output_json": False,
                },
            ),
            (_cmd_zotero_get, {"key": "K1", "output_json": False}),
            (_cmd_zotero_create, {"file": "x.json", "collection": None}),
            (_cmd_zotero_template, {"item_type": "journalArticle"}),
            (
                _cmd_zotero_update,
                {
                    "key": "K1",
                    "file": "x.json",
                    "dry_run": False,
                    "partial": False,
                    "version": None,
                },
            ),
            (_cmd_zotero_delete, {"keys": ["K1"], "dry_run": False, "yes": True, "version": None}),
        ],
        ids=["search", "get", "create", "template", "update", "delete"],
    )
    def test_env_missing_raises_user_input(self, handler: Any, kwargs: dict[str, Any]) -> None:
        with _patch_client(error="ZOTERO_USER_ID is not set"):
            with pytest.raises(UserInputError, match="ZOTERO_USER_ID"):
                handler(MagicMock(local=False, **kwargs))


# --- _cmd_zotero_create extra branches (lines 113, 135, 137) ---


class TestCreateExtraBranches:
    def test_single_dict_wrapped_to_list(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Line 113: non-list JSON is wrapped into a list before create."""
        items_file = tmp_path / "item.json"
        items_file.write_text(json.dumps({"key": "K1", "title": "Solo"}))  # dict, not list
        client = _mock_client()
        client.create_items.return_value = {
            "successful": {"0": {"key": "K1", "title": "Solo"}},
            "failed": {},
            "unchanged": {},
        }
        args = MagicMock(local=False, file=str(items_file), collection=None)
        with _patch_client(client):
            _cmd_zotero_create(args)
        # The dict was wrapped into a list before being sent
        sent = client.create_items.call_args[0][0]
        assert sent == [{"key": "K1", "title": "Solo"}]

    def test_successful_non_dict_item(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Line 135: non-dict successful entry renders as '[idx]: value'."""
        items_file = tmp_path / "items.json"
        items_file.write_text(json.dumps([{"key": "K1"}]))
        client = _mock_client()
        client.create_items.return_value = {
            "successful": {"0": "OK_STRING"},  # non-dict
            "failed": {},
            "unchanged": {},
        }
        args = MagicMock(local=False, file=str(items_file), collection=None)
        with _patch_client(client):
            _cmd_zotero_create(args)
        out = capsys.readouterr().out
        assert "[0]: OK_STRING" in out

    def test_failed_items_reported(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Line 137: failed entries are emitted via emit_info."""
        items_file = tmp_path / "items.json"
        items_file.write_text(json.dumps([{"key": "K1"}]))
        client = _mock_client()
        client.create_items.return_value = {
            "successful": {},
            "failed": {"0": {"code": "BAD_PAYLOAD"}},
            "unchanged": {},
        }
        args = MagicMock(local=False, file=str(items_file), collection=None)
        with _patch_client(client):
            _cmd_zotero_create(args)
        out = capsys.readouterr().out
        assert "Created: 0" in out
        assert "Failed: 1" in out

    def test_file_not_found_raises_user_input(self) -> None:
        """Lines 109-110: missing file raises UserInputError (not crash)."""
        args = MagicMock(local=False, file="/nonexistent/path.json", collection=None)
        with _patch_client(client=_mock_client()):
            with pytest.raises(UserInputError, match="Error reading"):
                _cmd_zotero_create(args)


# --- _cmd_zotero_update extra branches (lines 166-167, 186-192, 201-205, 209) ---


class TestUpdateExtraBranches:
    def test_bad_json_raises_user_input(self, tmp_path: Path) -> None:
        """Lines 166-167: malformed JSON file → UserInputError."""
        bad = tmp_path / "bad.json"
        bad.write_text("not json{")
        args = MagicMock(
            local=False, key="K1", file=str(bad), dry_run=False, partial=False, version=None
        )
        with _patch_client(client=_mock_client()):
            with pytest.raises(UserInputError, match="Error reading"):
                _cmd_zotero_update(args)

    def test_file_not_found_raises_user_input(self) -> None:
        """Lines 166-167: missing file → UserInputError."""
        args = MagicMock(
            local=False,
            key="K1",
            file="/no/such/file.json",
            dry_run=False,
            partial=False,
            version=None,
        )
        with _patch_client(client=_mock_client()):
            with pytest.raises(UserInputError, match="Error reading"):
                _cmd_zotero_update(args)

    def test_partial_auto_version_from_top_level(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Lines 186-187: partial PATCH, version=None, version from top-level."""
        changes = tmp_path / "c.json"
        changes.write_text(json.dumps({"title": "New"}))
        client = _mock_client()
        client.get_item.return_value = {"version": 7}  # version at top level
        client.partial_update_item.return_value = {"Last-Modified-Version": 8}
        args = MagicMock(
            local=False, key="K1", file=str(changes), dry_run=False, partial=True, version=None
        )
        with _patch_client(client):
            _cmd_zotero_update(args)
        out = capsys.readouterr().out
        assert "Updated K1" in out
        # partial_update_item called with the auto-detected version=7
        assert client.partial_update_item.call_args.kwargs["version"] == 7

    def test_partial_auto_version_from_data(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Lines 189-190: partial PATCH, version from nested data.version."""
        changes = tmp_path / "c.json"
        changes.write_text(json.dumps({"title": "New"}))
        client = _mock_client()
        client.get_item.return_value = {"data": {"version": 9}}  # no top-level version
        client.partial_update_item.return_value = {"Last-Modified-Version": 10}
        args = MagicMock(
            local=False, key="K1", file=str(changes), dry_run=False, partial=True, version=None
        )
        with _patch_client(client):
            _cmd_zotero_update(args)
        assert client.partial_update_item.call_args.kwargs["version"] == 9

    def test_partial_no_version_raises_user_input(self, tmp_path: Path) -> None:
        """Line 192: partial PATCH, version undeterminable → UserInputError."""
        changes = tmp_path / "c.json"
        changes.write_text(json.dumps({"title": "New"}))
        client = _mock_client()
        client.get_item.return_value = {}  # no version anywhere
        args = MagicMock(
            local=False, key="K1", file=str(changes), dry_run=False, partial=True, version=None
        )
        with _patch_client(client):
            with pytest.raises(UserInputError, match="Could not determine version"):
                _cmd_zotero_update(args)

    def test_put_auto_version_from_data(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Lines 201-203: PUT path, version=None, version from data.version."""
        changes = tmp_path / "c.json"
        changes.write_text(json.dumps({"title": "Merged"}))
        client = _mock_client()
        client.get_item.return_value = {"data": {"title": "Old", "version": 5}}  # version in data
        client.update_item.return_value = {"Last-Modified-Version": 6}
        args = MagicMock(
            local=False, key="K1", file=str(changes), dry_run=False, partial=False, version=None
        )
        with _patch_client(client):
            _cmd_zotero_update(args)
        assert client.update_item.call_args.kwargs["version"] == 5

    def test_put_no_version_raises_user_input(self, tmp_path: Path) -> None:
        """Line 205: PUT path, version undeterminable → UserInputError."""
        changes = tmp_path / "c.json"
        changes.write_text(json.dumps({"title": "X"}))
        client = _mock_client()
        client.get_item.return_value = {"data": {}}  # no version anywhere
        args = MagicMock(
            local=False, key="K1", file=str(changes), dry_run=False, partial=False, version=None
        )
        with _patch_client(client):
            with pytest.raises(UserInputError, match="Could not determine version"):
                _cmd_zotero_update(args)

    def test_put_non_dict_data_raises_user_input(self, tmp_path: Path) -> None:
        """Line 209: PUT path, current_data not a dict → UserInputError."""
        changes = tmp_path / "c.json"
        changes.write_text(json.dumps({"title": "X"}))
        client = _mock_client()
        # current is a non-dict (e.g. a list), version explicitly provided
        client.get_item.return_value = ["not", "a", "dict"]
        args = MagicMock(
            local=False, key="K1", file=str(changes), dry_run=False, partial=False, version=1
        )
        with _patch_client(client):
            with pytest.raises(UserInputError, match="Could not extract item data"):
                _cmd_zotero_update(args)


# --- _cmd_zotero_delete extra branches (lines 259, 276) ---


class TestDeleteExtraBranches:
    def test_single_no_version_raises_user_input(self) -> None:
        """Line 259: single delete, version undeterminable → UserInputError."""
        client = _mock_client()
        client.get_item.return_value = {}  # no version anywhere
        args = MagicMock(local=False, keys=["K1"], dry_run=False, yes=True, version=None)
        with _patch_client(client):
            with pytest.raises(UserInputError, match="Could not determine item version"):
                _cmd_zotero_delete(args)

    def test_batch_without_version_raises_user_input(self) -> None:
        """Line 276: batch delete requires --version."""
        client = _mock_client()
        args = MagicMock(local=False, keys=["K1", "K2"], dry_run=False, yes=True, version=None)
        with _patch_client(client):
            with pytest.raises(UserInputError, match="--version"):
                _cmd_zotero_delete(args)

    def test_single_auto_version_from_data(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Single delete where version comes from data.version (line 257 branch)."""
        client = _mock_client()
        client.get_item.return_value = {"data": {"version": 4}}  # version nested
        client.delete_item.return_value = None
        args = MagicMock(local=False, keys=["K1"], dry_run=False, yes=True, version=None)
        with _patch_client(client):
            _cmd_zotero_delete(args)
        out = capsys.readouterr().out
        assert "Deleted K1" in out
        assert "version 4" in out


# --- register_zotero (lines 310-401) ---


def _build_zotero_subparser() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    """Register zotero onto a fresh root parser; return (root, zotero_parser)."""
    root = argparse.ArgumentParser(prog="paper")
    subparsers = root.add_subparsers(dest="command")
    register_zotero(subparsers)
    # Find the zotero subparser
    sub_action = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    zotero_parser = sub_action.choices["zotero"]
    return root, zotero_parser


def _zotero_subcommands() -> dict[str, argparse.ArgumentParser]:
    """Map of zotero subcommand name → its subparser, post-registration."""
    _, zotero_parser = _build_zotero_subparser()
    sub_action = next(
        a for a in zotero_parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    return dict(sub_action.choices)


def _option_strings(parser: argparse.ArgumentParser) -> set[str]:
    """All option strings (--flags) declared on a parser, flattened."""
    return {s for action in parser._actions for s in action.option_strings if action.option_strings}


def _defaults(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """The set_defaults(...) metadata attached to a parser."""
    return dict(parser._defaults)


class TestRegisterZotero:
    """register_zotero() registers 8 subcommands with correct metadata + args.

    Mirrors the introspection style of test_clean_cancel.py and
    test_output_policy_registry.py (parse via real argparse, assert metadata).
    """

    @pytest.mark.parametrize(
        "name",
        ["collections", "search", "get", "create", "template", "update", "delete", "upload"],
    )
    def test_all_eight_subcommands_registered(self, name: str) -> None:
        subs = _zotero_subcommands()
        assert name in subs, f"zotero {name} not registered"

    def test_zotero_parser_has_local_flag(self) -> None:
        """The zotero parser itself exposes --local."""
        _, zotero_parser = _build_zotero_subparser()
        assert "--local" in _option_strings(zotero_parser)

    @pytest.mark.parametrize(
        "name,expected_policy",
        [
            ("collections", "json-capable"),
            ("search", "json-capable"),
            ("get", "json-capable"),
            ("template", "json-capable"),
            ("create", "text-only"),
            ("update", "text-only"),
            ("delete", "text-only"),
            ("upload", "text-only"),
        ],
    )
    def test_output_policy_metadata(self, name: str, expected_policy: str) -> None:
        subs = _zotero_subcommands()
        defaults = _defaults(subs[name])
        assert defaults.get("output_policy") == expected_policy

    @pytest.mark.parametrize(
        "name,expected_func_name",
        [
            ("collections", "_cmd_zotero_collections"),
            ("search", "_cmd_zotero_search"),
            ("get", "_cmd_zotero_get"),
            ("create", "_cmd_zotero_create"),
            ("template", "_cmd_zotero_template"),
            ("update", "_cmd_zotero_update"),
            ("delete", "_cmd_zotero_delete"),
            ("upload", "_cmd_zotero_upload"),
        ],
    )
    def test_func_metadata(self, name: str, expected_func_name: str) -> None:
        subs = _zotero_subcommands()
        defaults = _defaults(subs[name])
        func = defaults.get("func")
        assert func is not None, f"zotero {name} missing func default"
        assert func.__name__ == expected_func_name

    @pytest.mark.parametrize("name", ["create", "update", "delete", "upload"])
    def test_write_ops_have_clean_cancel(self, name: str) -> None:
        """Write operations are marked clean_cancel=True (side effects)."""
        subs = _zotero_subcommands()
        defaults = _defaults(subs[name])
        assert defaults.get("clean_cancel") is True

    @pytest.mark.parametrize("name", ["collections", "search", "get", "template"])
    def test_read_ops_no_clean_cancel(self, name: str) -> None:
        """Read operations must NOT set clean_cancel."""
        subs = _zotero_subcommands()
        defaults = _defaults(subs[name])
        assert not defaults.get("clean_cancel")

    def test_search_arguments(self) -> None:
        """zotero search registers query + filters + --json + --limit."""
        subs = _zotero_subcommands()
        opts = _option_strings(subs["search"])
        for flag in ["--type", "--tag", "--collection", "--limit", "--json"]:
            assert flag in opts, f"search missing {flag}"

    def test_get_arguments(self) -> None:
        """zotero get registers key positional + --json."""
        subs = _zotero_subcommands()
        opts = _option_strings(subs["get"])
        assert "--json" in opts

    def test_create_arguments(self) -> None:
        """zotero create registers file positional + --collection."""
        subs = _zotero_subcommands()
        opts = _option_strings(subs["create"])
        assert "--collection" in opts

    def test_template_arguments(self) -> None:
        """zotero template registers item_type positional."""
        subs = _zotero_subcommands()
        # template has no option flags, but the positional arg exists.
        positional_dests = {a.dest for a in subs["template"]._actions if not a.option_strings}
        assert "item_type" in positional_dests

    def test_update_arguments(self) -> None:
        """zotero update registers key/file positionals + --version/--partial/--dry-run."""
        subs = _zotero_subcommands()
        opts = _option_strings(subs["update"])
        for flag in ["--version", "--partial", "--dry-run"]:
            assert flag in opts, f"update missing {flag}"

    def test_delete_arguments(self) -> None:
        """zotero delete registers keys positional + --version/--dry-run/--yes."""
        subs = _zotero_subcommands()
        opts = _option_strings(subs["delete"])
        for flag in ["--version", "--dry-run", "--yes", "-y"]:
            assert flag in opts, f"delete missing {flag}"

    def test_upload_arguments(self) -> None:
        """zotero upload registers key/file positionals + --existing-md5/--force."""
        subs = _zotero_subcommands()
        opts = _option_strings(subs["upload"])
        for flag in ["--existing-md5", "--force"]:
            assert flag in opts, f"upload missing {flag}"

    def test_subparser_dest_is_subcommand(self) -> None:
        """The zotero subparser tree uses dest='subcommand'."""
        _, zotero_parser = _build_zotero_subparser()
        sub_action = next(
            a for a in zotero_parser._actions if isinstance(a, argparse._SubParsersAction)
        )
        assert sub_action.dest == "subcommand"

    def test_full_parse_round_trip(self) -> None:
        """End-to-end: parse a real argv and confirm func/output_policy resolve."""
        root, _ = _build_zotero_subparser()
        args = root.parse_args(
            ["zotero", "--local", "search", "--json", "--limit", "5", "machine learning"]
        )
        assert args.local is True
        assert args.subcommand == "search"
        assert args.query == "machine learning"
        assert args.output_json is True
        assert args.limit == 5
        assert args.output_policy == "json-capable"
        func = args.func
        assert func is not None
        assert func.__name__ == "_cmd_zotero_search"
