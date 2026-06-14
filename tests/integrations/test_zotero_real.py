"""Real integration tests against a running local Zotero instance.

These require a live Zotero with the Better BibTeX plugin. They are skipped
when Zotero is not running locally. Per AGENTS.md gotcha #4, marked
@ pytest.mark.integration so they can be excluded with -m "not integration".
"""

import socket

import pytest

from clients.zotero import ZoteroClient, ZoteroConfig, ZoteroUnavailableError


def is_zotero_running() -> bool:
    try:
        with socket.create_connection(("localhost", 23119), timeout=0.5):
            return True
    except OSError:
        return False


# Mark all tests in this module as integration (real adapters) per AGENTS.md #4,
# and skip when Zotero is not running locally.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not is_zotero_running(),
        reason="Local Zotero instance is not running on port 23119",
    ),
]


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
        # The BBT endpoint can return 500 even when the Zotero socket responds
        # (plugin misconfigured/not installed). Skip rather than fail so local
        # 'make test' stays clean when only the BBT plugin is down.
        config = ZoteroConfig(user_id="20772197", bbt_local=True)
        client = ZoteroClient(config=config)
        try:
            bib = client.fetch_bibtex()
        except ZoteroUnavailableError as exc:
            pytest.skip(f"Better BibTeX endpoint unavailable: {exc}")
        assert isinstance(bib, str)
