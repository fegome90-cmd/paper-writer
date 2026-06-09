"""Zotero live-sync wrapper.

Fetches a BibTeX export directly from a Zotero account via the Web API
(or local Zotero 7 / Better BibTeX endpoints) and then delegates to
ZoteroImporter for validation + copy into the pipeline.

Requires ZOTERO_USER_ID in the environment. For cloud mode also needs
ZOTERO_API_KEY. See clients/zotero.py for full config reference.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from clients.zotero import ZoteroClient, ZoteroConfig, ZoteroError
from harness.ports.tool_wrapper import ToolNotAvailableError, ToolWrapper, ValidatorResult
from integrations.tools.zotero_import import ZoteroImporter


class ZoteroSyncImporter(ToolWrapper):
    """Fetch .bib directly from a Zotero account and import it.

    Pipeline position: runs *before* BibliographyNormalizer (lint_bib).
    Opens gate ``bib_imported`` — a distinct gate from ``bib_normalized``
    so the pipeline distinguishes "fetched from Zotero" from "tidied by
    bibtex-tidy".

    Environment variables (resolved at run-time, not at construction):
        ZOTERO_USER_ID       — required
        ZOTERO_API_KEY       — required for cloud mode
        ZOTERO_LIBRARY_TYPE  — default "user"
        ZOTERO_LOCAL         — "true" → localhost:23119
        ZOTERO_BBT_LOCAL     — "true" → Better BibTeX pull

    Expected artifacts (all optional):
        collection_key  — Zotero collection key (8-char). None → full library.
        target_bib      — destination path (default: templates/references.bib).
        since_version   — int; only fetch items changed since this version.
    """

    @property
    def name(self) -> str:
        return "zotero-sync"

    @property
    def gate(self) -> str:
        # Distinct from "bib_normalized" (which bibtex-tidy sets).
        # The orchestrator must register this gate in the pipeline state.
        return "bib_imported"

    def is_available(self) -> bool:
        """Always returns True; run() performs strict environment checks based on artifacts."""
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        """Fetch from Zotero and delegate validation to ZoteroImporter.

        Steps:
        1. Build ZoteroConfig from environment.
        2. Fetch BibTeX via ZoteroClient (handles pagination + rate-limiting).
        3. Write to a named temp file.
        4. Delegate to ZoteroImporter.run() for validation + copy to target.

        Raises:
            ToolNotAvailableError: when ZOTERO_USER_ID is missing.
        """
        bbt_local_override = bool(artifacts.get("bbt_local"))
        import os
        if not bbt_local_override and not os.environ.get("ZOTERO_BBT_LOCAL", "").lower() == "true" and not os.environ.get("ZOTERO_USER_ID", "").strip():
            raise ToolNotAvailableError(
                "ZOTERO_USER_ID is not set. "
                "Set it in .envrc or your shell environment."
            )

        # Build config (raises KeyError with helpful message if USER_ID missing)
        try:
            config = ZoteroConfig.from_env(bbt_local_override=bbt_local_override)
        except KeyError as exc:
            raise ToolNotAvailableError(str(exc)) from exc

        collection_key: str | None = artifacts.get("collection_key")
        since_version_raw = artifacts.get("since_version")
        since_version: int | None = (
            int(since_version_raw) if since_version_raw is not None else None
        )

        # Fetch BibTeX from Zotero
        client = ZoteroClient(config=config)
        try:
            bibtex = client.fetch_bibtex(
                collection_key=collection_key,
                since_version=since_version,
            )
        except ZoteroError as exc:
            return ValidatorResult(
                validator="zotero-sync",
                status="fail",
                summary=f"Zotero API error: {exc}",
                findings=[
                    {
                        "code": "zotero_api_error",
                        "severity": "error",
                        "message": str(exc),
                    }
                ],
                artifacts_checked=[],
            )

        if not bibtex.strip():
            if since_version is not None:
                return ValidatorResult(
                    validator="zotero-sync",
                    status="pass",
                    summary="Incremental sync completed. No new changes since provided version.",
                    findings=[],
                    artifacts_checked=[],
                )
            return ValidatorResult(
                validator="zotero-sync",
                status="fail",
                summary="Zotero returned an empty BibTeX response. "
                "Check your collection key, API key, and library permissions.",
                findings=[
                    {
                        "code": "empty_response",
                        "severity": "error",
                        "message": "Zotero API returned no BibTeX entries.",
                    }
                ],
                artifacts_checked=[],
            )

        # Write to temp file and delegate to ZoteroImporter for validation + copy
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".bib",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(bibtex)
            tmp_path = tmp.name

        try:
            import_artifacts = {
                "source_bib": tmp_path,
                "target_bib": artifacts.get("target_bib", "templates/references.bib"),
            }

            importer = ZoteroImporter()
            result = importer.run(import_artifacts, context)
        finally:
            # Clean up temp file
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass

        # Rewrite validator name so logs are clear about which path ran
        return ValidatorResult(
            validator="zotero-sync",
            status=result.status,
            summary=result.summary.replace("zotero-import", "zotero-sync"),
            findings=result.findings,
            artifacts_checked=result.artifacts_checked,
        )
