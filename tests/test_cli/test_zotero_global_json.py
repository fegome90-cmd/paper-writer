"""Tests for Zotero handlers respecting global --output-format json (S10+S13).

Spec S10/S13 mandate that `--output-format json` routes output through
emit_json() for: zotero collections, zotero search, zotero get, zotero template.
These handlers previously only checked the legacy --json flag (output_json),
ignoring the global _config.output_format set by --output-format json.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cli.paper import output
from cli.paper.commands.zotero import (
    _cmd_zotero_collections,
    _cmd_zotero_get,
    _cmd_zotero_search,
    _cmd_zotero_template,
)


@pytest.fixture(autouse=True)
def _reset_output() -> Iterator[None]:
    output.configure(quiet=False, output_format="text")
    yield
    output.configure(quiet=False, output_format="text")


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.config.local_mode = False
    return client




def _patch(client: MagicMock | None = None) -> Any:
    return patch(
        "cli.paper.commands.zotero._zotero_client",
        return_value=(client or _mock_client(), None),
    )


class TestCollectionsRespectsGlobalJson:
    """S10: zotero collections --output-format json → emit_json."""

    def test_global_json_produces_json(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        client = _mock_client()
        client.fetch_collections.return_value = [{"key": "K1", "name": "My"}]
        output.configure(quiet=False, output_format="json")
        with _patch(client):
            _cmd_zotero_collections(MagicMock(local=False))
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["key"] == "K1"


class TestSearchRespectsGlobalJson:
    """S10: zotero search --output-format json (without legacy --json) → emit_json."""

    def test_global_json_without_legacy_flag(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        client = _mock_client()
        client.search_items.return_value = [{"key": "K1", "title": "Paper"}]
        output.configure(quiet=False, output_format="json")
        args = MagicMock(local=False, query="test", item_type=None, tag=None,
                         collection=None, limit=25, output_json=False)
        with _patch(client):
            _cmd_zotero_search(args)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["title"] == "Paper"


class TestGetRespectsGlobalJson:
    """S10: zotero get --output-format json (without legacy --json) → emit_json."""

    def test_global_json_without_legacy_flag(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        client = _mock_client()
        client.get_item.return_value = {"key": "K1", "title": "Item"}
        output.configure(quiet=False, output_format="json")
        args = MagicMock(local=False, key="K1", output_json=False)
        with _patch(client):
            _cmd_zotero_get(args)
        data = json.loads(capsys.readouterr().out)
        assert data["key"] == "K1"


class TestTemplateRespectsGlobalJson:
    """S10: zotero template already uses emit_json directly — verify it stays."""

    def test_global_json_produces_json(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        client = _mock_client()
        client.get_item_template.return_value = {"itemType": "journalArticle"}
        output.configure(quiet=False, output_format="json")
        args = MagicMock(local=False, item_type="journalArticle")
        with _patch(client):
            _cmd_zotero_template(args)
        data = json.loads(capsys.readouterr().out)
        assert data["itemType"] == "journalArticle"
