"""Tests for ArxivClient — arXiv API client for citation verification."""

from __future__ import annotations

import urllib.error
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from clients.arxiv import (
    _ATOM_NS,
    ArxivClient,
    _extract_arxiv_id,
    _extract_authors,
    _extract_categories,
    _extract_title,
    _extract_year,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_entry(
    title: str = "Attention Is All You Need",
    year: str = "2017-06-12T00:00:00Z",
    arxiv_id: str = "1706.03762v5",
    authors: list[str] | None = None,
    categories: list[str] | None = None,
) -> ET.Element:
    """Build an Atom <entry> element for testing."""
    entry = ET.Element(f"{_ATOM_NS}entry")

    title_el = ET.SubElement(entry, f"{_ATOM_NS}title")
    title_el.text = title

    id_el = ET.SubElement(entry, f"{_ATOM_NS}id")
    id_el.text = f"http://arxiv.org/abs/{arxiv_id}"

    published = ET.SubElement(entry, f"{_ATOM_NS}published")
    published.text = year

    if authors:
        for name in authors:
            author_el = ET.SubElement(entry, f"{_ATOM_NS}author")
            name_el = ET.SubElement(author_el, f"{_ATOM_NS}name")
            name_el.text = name

    if categories:
        for cat in categories:
            cat_el = ET.SubElement(entry, f"{_ATOM_NS}category")
            cat_el.set("term", cat)

    return entry


def _make_feed(entries: list[ET.Element]) -> bytes:
    """Build a complete Atom feed XML document."""
    root = ET.Element(f"{_ATOM_NS}feed")
    for entry in entries:
        root.append(entry)
    return ET.tostring(root, encoding="unicode").encode("utf-8")


# ── Extractor tests ──────────────────────────────────────────────────


class TestExtractors:
    def test_extract_title(self) -> None:
        entry = _make_entry(title="Neural Machine Translation")
        assert _extract_title(entry) == "Neural Machine Translation"

    def test_extract_title_normalizes_whitespace(self) -> None:
        entry = _make_entry(title="Deep   Learning\nfor  NLP")
        assert _extract_title(entry) == "Deep Learning for NLP"

    def test_extract_title_empty(self) -> None:
        entry = ET.Element(f"{_ATOM_NS}entry")
        assert _extract_title(entry) == ""

    def test_extract_year(self) -> None:
        entry = _make_entry(year="2023-11-15T10:30:00Z")
        assert _extract_year(entry) == 2023

    def test_extract_year_missing(self) -> None:
        entry = ET.Element(f"{_ATOM_NS}entry")
        assert _extract_year(entry) is None

    def test_extract_year_non_numeric(self) -> None:
        entry = _make_entry(year="invalid")
        assert _extract_year(entry) is None

    def test_extract_arxiv_id(self) -> None:
        entry = _make_entry(arxiv_id="2301.00001v1")
        assert _extract_arxiv_id(entry) == "2301.00001v1"

    def test_extract_arxiv_id_missing(self) -> None:
        entry = ET.Element(f"{_ATOM_NS}entry")
        assert _extract_arxiv_id(entry) is None

    def test_extract_authors(self) -> None:
        entry = _make_entry(authors=["Vaswani, Ashish", "Shazeer, Noam"])
        assert _extract_authors(entry) == ["Vaswani, Ashish", "Shazeer, Noam"]

    def test_extract_authors_empty(self) -> None:
        entry = _make_entry()
        assert _extract_authors(entry) == []

    def test_extract_categories(self) -> None:
        entry = _make_entry(categories=["cs.CL", "cs.LG"])
        assert _extract_categories(entry) == ["cs.CL", "cs.LG"]

    def test_extract_categories_empty(self) -> None:
        entry = _make_entry()
        assert _extract_categories(entry) == []


# ── Client unit tests (mocked HTTP) ──────────────────────────────────


class TestArxivClientOffline:
    def test_verify_arxiv_id_offline(self) -> None:
        client = ArxivClient(offline=True)
        result = client.verify_arxiv_id("2301.00001")
        assert result.found is False

    def test_search_by_title_offline(self) -> None:
        client = ArxivClient(offline=True)
        results = client.search_by_title("attention is all you need")
        assert results == []

    def test_reset_outage_latch(self) -> None:
        client = ArxivClient(offline=True)
        client._latched_unavailable = True
        client.reset_outage_latch()
        assert client._latched_unavailable is False


class TestArxivClientVerify:
    def test_verify_existing_id(self) -> None:
        entry = _make_entry(
            title="Attention Is All You Need",
            arxiv_id="1706.03762v5",
            authors=["Vaswani, Ashish"],
            categories=["cs.CL"],
        )
        feed_xml = _make_feed([entry])

        client = ArxivClient(
            offline=False,
            sleep=MagicMock(),
            clock=lambda: 100.0,
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = feed_xml
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = client.verify_arxiv_id("1706.03762")

        assert result.found is True
        assert result.arxiv_id == "1706.03762v5"
        assert result.title == "Attention Is All You Need"
        assert result.authors == ["Vaswani, Ashish"]
        assert result.year == 2017
        assert result.categories == ["cs.CL"]
        assert result.score == 1.0

    def test_verify_nonexistent_id(self) -> None:
        """Empty feed returns found=False."""
        feed_xml = _make_feed([])

        client = ArxivClient(
            offline=False,
            sleep=MagicMock(),
            clock=lambda: 100.0,
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = feed_xml
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = client.verify_arxiv_id("0000.00000")

        assert result.found is False


class TestArxivClientSearch:
    def test_search_by_title_found(self) -> None:
        entry = _make_entry(
            title="Attention Is All You Need",
            authors=["Vaswani"],
        )
        feed_xml = _make_feed([entry])

        client = ArxivClient(
            offline=False,
            sleep=MagicMock(),
            clock=lambda: 100.0,
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = feed_xml
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            results = client.search_by_title("Attention Is All You Need")

        assert len(results) == 1
        assert results[0].found is True
        assert results[0].title == "Attention Is All You Need"
        assert results[0].score > 0.0

    def test_search_by_title_no_match(self) -> None:
        """Title below similarity threshold returns empty."""
        entry = _make_entry(title="Completely Different Paper")
        feed_xml = _make_feed([entry])

        client = ArxivClient(
            offline=False,
            sleep=MagicMock(),
            clock=lambda: 100.0,
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = feed_xml
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            results = client.search_by_title("Attention Is All You Need")

        assert results == []

    def test_search_by_title_year_tiebreaker(self) -> None:
        """Year match adds 0.05 to score."""
        entry = _make_entry(title="Deep Learning for NLP", year="2023-01-01T00:00:00Z")
        feed_xml = _make_feed([entry])

        client = ArxivClient(
            offline=False,
            sleep=MagicMock(),
            clock=lambda: 100.0,
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = feed_xml
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            results = client.search_by_title("Deep Learning for NLP", year=2023)

        assert len(results) == 1
        assert results[0].year == 2023
        # Score should include year bonus
        assert results[0].score >= 1.0


class TestArxivClientErrorHandling:
    def test_network_error_returns_not_found(self) -> None:
        client = ArxivClient(
            offline=False,
            sleep=MagicMock(),
            clock=lambda: 100.0,
        )
        with patch("urllib.request.urlopen", side_effect=OSError("network error")):
            result = client.verify_arxiv_id("2301.00001")

        assert result.found is False
        assert client._latched_unavailable is True

    def test_latched_unavailable_returns_empty(self) -> None:
        client = ArxivClient(
            offline=False,
            sleep=MagicMock(),
            clock=lambda: 100.0,
        )
        client._latched_unavailable = True

        result = client.verify_arxiv_id("2301.00001")
        assert result.found is False

    def test_xml_parse_error_returns_not_found(self) -> None:
        client = ArxivClient(
            offline=False,
            sleep=MagicMock(),
            clock=lambda: 100.0,
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"not valid xml"
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = client.verify_arxiv_id("2301.00001")

        assert result.found is False

    def test_404_returns_not_found(self) -> None:
        client = ArxivClient(
            offline=False,
            sleep=MagicMock(),
            clock=lambda: 100.0,
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="http://example.com",
                code=404,
                msg="Not Found",
                hdrs={},  # type: ignore[arg-type]
                fp=None,
            )

            result = client.verify_arxiv_id("2301.00001")

        assert result.found is False
        # 404 should NOT latch unavailable — it's a normal miss
        assert client._latched_unavailable is False


class TestArxivClientRateLimit:
    def test_throttle_enforces_interval(self) -> None:
        fake_sleep = MagicMock()

        # clock() returns 101.5 → elapsed = 101.5 - 100.0 = 1.5 < 3.0
        client = ArxivClient(
            offline=False,
            sleep=fake_sleep,
            clock=lambda: 101.5,
        )
        client._last_request_at = 100.0
        client._throttle()

        # Should have slept (3.0 - 1.5) = 1.5s
        fake_sleep.assert_called_once()
        call_args = fake_sleep.call_args[0][0]
        assert abs(call_args - 1.5) < 0.01

    def test_no_throttle_when_elapsed_sufficient(self) -> None:
        fake_sleep = MagicMock()

        client = ArxivClient(
            offline=False,
            sleep=fake_sleep,
            clock=lambda: 200.0,  # elapsed = 100.0 since last_request_at
        )
        client._last_request_at = 100.0
        client._throttle()

        fake_sleep.assert_not_called()

    def test_no_throttle_when_no_previous_request(self) -> None:
        fake_sleep = MagicMock()

        client = ArxivClient(
            offline=False,
            sleep=fake_sleep,
            clock=lambda: 100.0,
        )
        # _last_request_at is 0.0 (default) → no throttle
        client._throttle()

        fake_sleep.assert_not_called()
