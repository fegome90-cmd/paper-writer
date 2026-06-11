"""Real integration tests against a running local Zotero instance."""

import socket

import pytest

from clients.zotero import ZoteroClient, ZoteroConfig


def is_zotero_running() -> bool:
    try:
        with socket.create_connection(("localhost", 23119), timeout=0.5):
            return True
    except OSError:
        return False


# Skip all tests in this module if Zotero is not running locally.
pytestmark = pytest.mark.skipif(
    not is_zotero_running(), reason="Local Zotero instance is not running on port 23119"
)


class TestZoteroRealIntegration:
    def test_local_api_collections(self) -> None:
        import os

        user_id = os.environ.get("ZOTERO_USER_ID", "0")
        config = ZoteroConfig(user_id=user_id, local_mode=True)
        client = ZoteroClient(config=config)
        collections = client.fetch_collections()
        assert isinstance(collections, list)

    def test_local_api_fetch_bibtex(self) -> None:
        import os

        user_id = os.environ.get("ZOTERO_USER_ID", "0")
        config = ZoteroConfig(user_id=user_id, local_mode=True)
        client = ZoteroClient(config=config)
        bib = client.fetch_bibtex()
        assert isinstance(bib, str)

    def test_bbt_local_fetch_bibtex(self) -> None:
        config = ZoteroConfig(user_id="20772197", bbt_local=True)
        client = ZoteroClient(config=config)
        bib = client.fetch_bibtex()
        assert isinstance(bib, str)
