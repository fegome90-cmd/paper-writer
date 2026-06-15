"""Tests for PIPELINE_MAP + _make_key + resolvers (Phase C6, S3).

The MAP closes the CRITICAL 'verify' gap (verify gets an explicit owner) and
makes dispatch declarative. Every entry's resolve() must produce the exact
semantics of the prior if/elif — failure_policy and needs_review_config
migrated 1:1.
"""

from __future__ import annotations

import argparse

import pytest

from cli.paper.dispatch import PIPELINE_MAP, _make_key
from cli.paper.errors import UserInputError

EXPECTED_PIPELINE_KEYS = frozenset(
    {
        "init",
        "search",
        "chain",
        "export-bib",
        "screen",
        "draft:outline",
        "draft:section",
        "draft:all",
        "protocol",
        "lint:bib",
        "lint:style",
        "check:refs",
        "audit:reporting",
        "import:bib",
        "render",
        "verify",
    }
)


class TestMakeKey:
    """S3: _make_key produces composite keys for subcommands, plain for simples."""

    @pytest.mark.parametrize(
        "cmd,sub,expected",
        [
            ("init", None, "init"),
            ("search", None, "search"),
            ("draft", "outline", "draft:outline"),
            ("draft", "section", "draft:section"),
            ("draft", "all", "draft:all"),
            ("lint", "bib", "lint:bib"),
            ("lint", "style", "lint:style"),
            ("check", "refs", "check:refs"),
            ("audit", "reporting", "audit:reporting"),
            ("import", "bib", "import:bib"),
            ("render", None, "render"),
            ("verify", None, "verify"),
        ],
    )
    def test_key_formation(self, cmd: str, sub: str | None, expected: str) -> None:
        assert _make_key(cmd, sub) == expected


class TestPipelineMapCompleteness:
    """S3: PIPELINE_MAP contains all 16 pipeline routes — no orphans, no verify gap."""

    def test_map_has_exactly_16_entries(self) -> None:
        assert set(PIPELINE_MAP.keys()) == EXPECTED_PIPELINE_KEYS, (
            f"missing: {EXPECTED_PIPELINE_KEYS - set(PIPELINE_MAP.keys())}; "
            f"extra: {set(PIPELINE_MAP.keys()) - EXPECTED_PIPELINE_KEYS}"
        )

    def test_verify_is_explicitly_mapped(self) -> None:
        """CRITICAL gap closure: verify MUST be an explicit MAP entry (not default)."""
        assert "verify" in PIPELINE_MAP, "verify must have explicit owner (closes CRITICAL)"


class TestResolverSemantics:
    """1:1 migration: resolve() produces exact orch_command + policies from if/elif."""

    @staticmethod
    def _ns(**kw: object) -> argparse.Namespace:
        return argparse.Namespace(**kw)

    def test_init_resolver(self) -> None:
        args = self._ns(
            preset="nature",
            mode="rapid",
            search_window_start=2020,
            search_window_end=2024,
        )
        inv = PIPELINE_MAP["init"].resolve(args)
        assert inv.orch_command == "init"
        assert inv.args["preset"] == "nature"
        assert inv.args["search_window"] == {"start_year": 2020, "end_year": 2024}
        assert PIPELINE_MAP["init"].needs_review_config is False  # only init

    def test_search_resolver_validates_query(self) -> None:
        from cli.paper.errors import UserInputError

        args = self._ns(
            query="  ",
            raw_papers=None,
            year_min=None,
            year_max=None,
            study_types=None,
            human=None,
            sample_size_min=None,
            sjr_max=None,
            duration_min=None,
            duration_max=None,
            exclude_preprints=None,
            publisher_name=None,
            clinical_guideline=None,
            medical_mode=None,
        )
        with pytest.raises(UserInputError, match="--query"):
            PIPELINE_MAP["search"].resolve(args)

    def test_import_bib_resolver_picks_zotero_sync_when_from_zotero(self) -> None:
        """The runtime command selection that justified PipelineInvocation."""
        args = self._ns(
            source=None,
            from_zotero=True,
            target="ref.bib",
            collection="ABC12345",
            since=None,
            bbt_local=False,
        )
        inv = PIPELINE_MAP["import:bib"].resolve(args)
        assert inv.orch_command == "zotero_sync"

    def test_import_bib_resolver_picks_import_bib_with_source(self) -> None:
        args = self._ns(
            source="in.bib",
            from_zotero=False,
            target="ref.bib",
            collection=None,
            since=None,
            bbt_local=False,
        )
        inv = PIPELINE_MAP["import:bib"].resolve(args)
        assert inv.orch_command == "import_bib"

    def test_import_bib_resolver_requires_source_or_from_zotero(self) -> None:
        from cli.paper.errors import UserInputError

        args = self._ns(
            source=None,
            from_zotero=False,
            target="ref.bib",
            collection=None,
            since=None,
            bbt_local=False,
        )
        with pytest.raises(UserInputError, match="source"):
            PIPELINE_MAP["import:bib"].resolve(args)

    @pytest.mark.parametrize(
        "key,expected_policy",
        [
            ("init", "stop_on_error"),
            ("search", "stop_on_error"),
            ("export-bib", "stop_on_error"),
            ("render", "stop_on_error"),
            ("verify", "stop_on_error"),
            ("lint:bib", "continue_on_error"),
            ("lint:style", "continue_on_error"),
            ("check:refs", "continue_on_error"),
            ("audit:reporting", "continue_on_error"),
        ],
    )
    def test_failure_policy_preserved_1to1(self, key: str, expected_policy: str) -> None:
        assert PIPELINE_MAP[key].failure_policy == expected_policy, (
            f"{key} failure_policy must be 1:1 with prior if/elif"
        )

    def test_render_resolver_defaults_formats(self) -> None:
        args = self._ns(formats=None, csl=None, reference_doc=None)
        inv = PIPELINE_MAP["render"].resolve(args)
        assert inv.orch_command == "render"
        assert inv.args["output_formats"] == ["docx", "pdf"]


class TestResolverStrictValidation:
    """Resolvers must reject None with UserInputError, not send None to orchestrator."""

    def test_resolve_screen_rejects_none_min_tier(self) -> None:
        args = argparse.Namespace(min_tier=None)
        with pytest.raises(UserInputError, match="--min-tier"):
            PIPELINE_MAP["screen"].resolve(args)

    def test_resolve_draft_section_rejects_none_name(self) -> None:
        args = argparse.Namespace(name=None)
        with pytest.raises(UserInputError, match="name"):
            PIPELINE_MAP["draft:section"].resolve(args)

    def test_resolve_export_bib_rejects_none_bib_path(self) -> None:
        args = argparse.Namespace(bib_path=None)
        with pytest.raises(UserInputError, match="--bib-path"):
            PIPELINE_MAP["export-bib"].resolve(args)
