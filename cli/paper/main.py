import argparse
import importlib.metadata
import os
import sys
from pathlib import Path
from typing import Any

from cli.paper.commands.audit import (
    _cmd_audit_citations,
    _cmd_audit_claims,
    _cmd_audit_code_health,
    _cmd_audit_ethics,
    _cmd_audit_factuality,
    _cmd_audit_prose,
    _cmd_audit_quality_appraisal,
    _cmd_audit_tables,
    _cmd_audit_writing_quality,
)
from cli.paper.commands.gate import _cmd_gate_method
from cli.paper.commands.graph import _cmd_graph_overview, _cmd_trace
from harness.services.orchestrator import Orchestrator, OrchestratorRequest, OrchestratorResult
from harness.services.orchestrator_builder import build_orchestrator_dependencies


def _get_version() -> str:
    """Get package version from metadata."""
    try:
        return importlib.metadata.version("paper-writer")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0-dev"


MAX_ASCENDING_DEPTH = 20
DEFAULT_SEARCH_QUERY = "systematic literature review"
DEFAULT_SEARCH_QUERY_NOTICE = (
    "[--] No --query supplied; using compatibility fallback query for provider-backed search."
)


# ------------------------------------------------------------------
# Zotero CLI handlers
# ------------------------------------------------------------------


def _zotero_client(*, local: bool = False) -> tuple[Any, str | None]:
    """Build ZoteroClient from env. Returns (client, error_msg)."""
    from clients.zotero import ZoteroClient, ZoteroConfig

    try:
        config = ZoteroConfig.from_env()
        if local:
            import dataclasses

            config = dataclasses.replace(config, local_mode=True)
    except KeyError as exc:
        return None, str(exc).strip("'")
    return ZoteroClient(config=config), None


def _cmd_zotero_collections(args: Any) -> None:
    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from None
    try:
        collections = client.fetch_collections()
        for c in collections:
            parent = c.get("parentCollection", False)
            prefix = "  " if parent else ""
            print(f"{prefix}{c['key']}: {c['name']}")
        print(f"\n{len(collections)} collection(s)")
    except ZoteroError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _cmd_zotero_search(args: Any) -> None:
    import json as _json

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from None
    try:
        results = client.search_items(
            args.query,
            item_type=args.item_type,
            tag=args.tag,
            collection_key=args.collection,
            limit=args.limit,
        )
        if args.output_json:
            print(_json.dumps(results, indent=2, ensure_ascii=False))
            return
        for item in results:
            key = item.get("key", "?")
            title = item.get("title", "(no title)")
            year = item.get("date", "")[:4] if item.get("date") else ""
            item_type = item.get("itemType", "")
            print(f"  {key}  {year:>4}  {item_type:<20}  {title}")
        print(f"\n{len(results)} result(s)")
    except ZoteroError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _cmd_zotero_get(args: Any) -> None:
    import json as _json

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from None
    try:
        item = client.get_item(args.key)
        if args.output_json:
            print(_json.dumps(item, indent=2, ensure_ascii=False))
            return
        data = item.get("data", item) if isinstance(item, dict) else item
        if isinstance(data, dict):
            for k, v in data.items():
                if k not in ("key", "version", "itemType") and v:
                    print(f"  {k}: {v}")
    except (ZoteroError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _cmd_zotero_create(args: Any) -> None:
    import json as _json

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from None
    try:
        items = _json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"Error reading {args.file}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    if not isinstance(items, list):
        items = [items]

    if args.collection:
        for item in items:
            if isinstance(item, dict):
                collections = item.get("collections", [])
                if args.collection not in collections:
                    collections.append(args.collection)
                item["collections"] = collections

    try:
        result = client.create_items(items)
        successful = result.get("successful") or {}
        failed = result.get("failed") or {}
        unchanged = result.get("unchanged") or {}
        print(f"Created: {len(successful)}, Unchanged: {len(unchanged)}, Failed: {len(failed)}")
        for idx, item_data in successful.items():
            if isinstance(item_data, dict):
                print(f"  {item_data.get('key', '?')}: {item_data.get('title', 'ok')}")
            else:
                print(f"  [{idx}]: {item_data}")
        for idx, info in failed.items():
            print(f"  FAILED [{idx}]: {info}", file=sys.stderr)
    except ZoteroError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _cmd_zotero_template(args: Any) -> None:
    import json as _json

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from None
    try:
        template = client.get_item_template(args.item_type)
        print(_json.dumps(template, indent=2, ensure_ascii=False))
    except ZoteroError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _cmd_zotero_update(args: Any) -> None:
    import json as _json

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from None
    try:
        changes = _json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"Error reading {args.file}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    # Dry-run: show what would be updated without executing
    if args.dry_run:
        is_local = client.config.local_mode if hasattr(client, "config") else False
        base_url = "http://localhost:23119/api" if is_local else "https://api.zotero.org"
        print(
            "[DRY RUN] Would update "
            f"{args.key} with {len(changes)} field(s): {', '.join(changes.keys())}"
        )
        print(f"[DRY RUN] Target: {base_url}")
        return

    try:
        version = args.version

        if args.partial:
            # PATCH: only send changed fields. Skip GET if version is known.
            if version is None:
                current = client.get_item(args.key)
                version = current.get("version") if isinstance(current, dict) else None
                if version is None:
                    d = current.get("data", {}) if isinstance(current, dict) else {}
                    version = d.get("version") if isinstance(d, dict) else None
                if version is None:
                    print("Error: could not determine version. Use --version.", file=sys.stderr)
                    raise SystemExit(1) from None
            headers = client.partial_update_item(args.key, changes, version=version)
        else:
            # PUT: must send complete item data. Fetch current, merge changes.
            current = client.get_item(args.key)
            current_data = current.get("data", current) if isinstance(current, dict) else current

            if version is None:
                version = current.get("version") if isinstance(current, dict) else None
                if version is None and isinstance(current_data, dict):
                    version = current_data.get("version")
            if version is None:
                print("Error: could not determine item version. Use --version.", file=sys.stderr)
                raise SystemExit(1) from None

            if not isinstance(current_data, dict):
                print("Error: could not extract item data for update", file=sys.stderr)
                raise SystemExit(1) from None
            # Merge: user data overwrites current fields
            merged = {**current_data, **changes}
            merged["key"] = args.key
            merged["version"] = version
            # Remove read-only fields that cause 400 on PUT
            for readonly_field in ("dateAdded", "dateModified", "citationKey"):
                merged.pop(readonly_field, None)
            headers = client.update_item(args.key, merged, version=version)
        new_version = headers.get("Last-Modified-Version", "?")
        print(f"Updated {args.key} → version {new_version}")
    except (ZoteroError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _cmd_zotero_delete(args: Any) -> None:
    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from None

    # Dry-run: show what would be deleted without executing
    if args.dry_run:
        is_local = client.config.local_mode if hasattr(client, "config") else False
        base_url = "http://localhost:23119/api" if is_local else "https://api.zotero.org"
        print(f"[DRY RUN] Would delete {len(args.keys)} item(s): {', '.join(args.keys)}")
        print(f"[DRY RUN] Target: {base_url}")
        return

    # Confirmation prompt unless --yes
    if not args.yes:
        count = len(args.keys)
        items = f"{count} items" if count > 1 else args.keys[0]
        try:
            response = input(f"Delete {items}? [y/N] ")
        except EOFError:
            response = "n"
        if response.lower() not in ("y", "yes"):
            print("Cancelled.")
            return

    try:
        if len(args.keys) == 1:
            # Single item: auto-detect version if not provided
            version = args.version
            if version is None:
                item = client.get_item(args.keys[0])
                version = item.get("version") or item.get("data", {}).get("version")
                if version is None:
                    print(
                        "Error: could not determine item version. Use --version.", file=sys.stderr
                    )
                    raise SystemExit(1) from None
            try:
                client.delete_item(args.keys[0], version=version)
            except ZoteroError as exc:
                if "412" in str(exc) and args.version is None:
                    # Race: item was modified since auto-detect. Retry once.
                    item = client.get_item(args.keys[0])
                    version = item.get("version") or item.get("data", {}).get("version")
                    if version is None:
                        raise
                    client.delete_item(args.keys[0], version=version)
                else:
                    raise
            print(f"Deleted {args.keys[0]} (version {version})")
        else:
            # Batch: require library version
            if args.version is None:
                print(
                    "Error: --version (library version) is required for batch delete.",
                    file=sys.stderr,
                )
                raise SystemExit(1) from None
            client.delete_items(args.keys, library_version=args.version)
            print(f"Deleted {len(args.keys)} items")
    except (ZoteroError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def _cmd_zotero_upload(args: Any) -> None:
    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from None

    try:
        result = client.upload_file(
            args.key,
            args.file,
            existing_md5=args.existing_md5,
            force_update=args.force,
        )
        print(f"Status: {result.get('status')}")
        if result.get("status") == "uploaded":
            print(f"  File: {result.get('filename')}")
            print(f"  Size: {result.get('size')} bytes")
            print(f"  MD5:  {result.get('md5')}")
        else:
            print(f"  {result.get('message', 'File already exists')}")
    except (ZoteroError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def resolve_project_root(explicit_path: Path | None, cwd: Path) -> Path:
    """Resolve project root. Priority: flag → ascending search → CWD.

    Ascending search resolves symlinks via Path.resolve() before
    checking for outputs/state.yaml to prevent symlink injection.
    """
    if explicit_path is not None:
        resolved = explicit_path.resolve()
        if not resolved.is_dir():
            print(
                f"Error: Project path does not exist: {explicit_path}",
                file=sys.stderr,
            )
            raise SystemExit(1) from None
        return resolved

    # Ascending search for outputs/state.yaml (innermost match)
    candidate = cwd.resolve()
    for _ in range(MAX_ASCENDING_DEPTH):
        marker = candidate / "outputs" / "state.yaml"
        if marker.is_file():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break  # filesystem root
        candidate = parent

    # Fallback: CWD
    return cwd.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="paper CLI - Single entrypoint for scientific drafting CI/CD pipeline."
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=_get_version(),
    )
    parser.add_argument(
        "--project",
        "-C",
        default=None,
        type=Path,
        help="Project root directory (default: auto-detect from CWD).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # paper init
    init_parser = subparsers.add_parser("init", help="Initialize repository and state.")
    init_parser.add_argument(
        "--preset",
        default=None,
        help="Journal preset name (e.g. 'nature'). Loads from templates/journals/<name>/.",
    )
    init_parser.add_argument(
        "--mode",
        choices=["rapid", "academic"],
        default="rapid",
        help="Review mode: 'rapid' (default) or 'academic' for full evidence curation.",
    )
    init_parser.add_argument(
        "--search-window-start",
        type=int,
        default=None,
        help="Academic mode: start year for search window.",
    )
    init_parser.add_argument(
        "--search-window-end",
        type=int,
        default=None,
        help="Academic mode: end year for search window.",
    )

    # paper search
    search_parser = subparsers.add_parser("search", help="Execute scientific literature search.")
    search_parser.add_argument(
        "--query",
        default=None,
        help="Research query to use for provider-backed search.",
    )
    search_parser.add_argument(
        "--raw-papers",
        help="Path to JSON file containing raw paper candidates.",
    )
    # Consensus/academic search filter params (forwarded to provider)
    search_parser.add_argument(
        "--year-min",
        type=int,
        default=None,
        help="Exclude papers published before this year.",
    )
    search_parser.add_argument(
        "--year-max",
        type=int,
        default=None,
        help="Exclude papers published after this year.",
    )
    search_parser.add_argument(
        "--study-types",
        nargs="*",
        default=None,
        help="Only include these study types (e.g. 'rct' 'systematic review').",
    )
    search_parser.add_argument(
        "--human",
        action="store_true",
        default=False,
        help="Only include human studies.",
    )
    search_parser.add_argument(
        "--sample-size-min",
        type=int,
        default=None,
        help="Exclude studies with fewer participants.",
    )
    search_parser.add_argument(
        "--sjr-max",
        type=int,
        default=None,
        help="Exclude journals in lesser quartiles (1=best, 4=worst).",
    )
    search_parser.add_argument(
        "--duration-min",
        type=int,
        default=None,
        help="Minimum study duration in days.",
    )
    search_parser.add_argument(
        "--duration-max",
        type=int,
        default=None,
        help="Maximum study duration in days.",
    )
    search_parser.add_argument(
        "--exclude-preprints",
        action="store_true",
        default=False,
        help="Only include peer-reviewed papers.",
    )
    search_parser.add_argument(
        "--publisher-name",
        default=None,
        help="Comma-separated publisher names to filter by.",
    )
    search_parser.add_argument(
        "--clinical-guideline",
        action="store_true",
        default=False,
        help="Filter to papers classified as clinical guidelines.",
    )
    search_parser.add_argument(
        "--medical-mode",
        action="store_true",
        default=False,
        help="Filter to top medical journals and guidelines.",
    )

    # paper chain
    chain_parser = subparsers.add_parser(
        "chain",
        help="Expand corpus via Semantic Scholar citation chaining.",
    )
    chain_parser.add_argument(
        "--max-rounds",
        type=int,
        default=2,
        help="Maximum chaining iterations (default: 2).",
    )
    chain_parser.add_argument(
        "--max-papers",
        type=int,
        default=80,
        help="Stop when corpus reaches this size (default: 80).",
    )
    chain_parser.add_argument(
        "--relevance-threshold",
        type=float,
        default=0.15,
        help=(
            "Minimum relevance score to include"
            " (default: 0.15, auto-lowered for highly-cited papers)."
        ),
    )
    chain_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable API response caching.",
    )

    # paper screen
    screen_parser = subparsers.add_parser("screen", help="Screen search results to evidence set.")
    screen_parser.add_argument(
        "--min-tier",
        default=os.environ.get("PAPER_SCREEN_MIN_TIER", "Tier 3"),
        help="Minimum tier to include (Tier 1, Tier 2, Tier 3, Discard). "
        "Default: Tier 3. Env: PAPER_SCREEN_MIN_TIER.",
    )

    # paper export-bib
    export_bib_parser = subparsers.add_parser(
        "export-bib", help="Export screened papers to BibTeX."
    )
    export_bib_parser.add_argument(
        "--bib-path",
        default="templates/references.bib",
        help="Output BibTeX file path.",
    )

    # paper draft
    draft_parser = subparsers.add_parser("draft", help="Draft outline or sections.")
    draft_sub = draft_parser.add_subparsers(dest="subcommand", required=True)
    draft_sub.add_parser("outline", help="Draft outline.")
    sec_parser = draft_sub.add_parser("section", help="Draft section.")
    sec_parser.add_argument(
        "name",
        help=(
            "Section name"
            " (abstract, introduction, literature_review,"
            " methods, results, discussion, conclusion)"
        ),
    )
    draft_sub.add_parser(
        "all", help="Draft all sections in dependency order with cross-section context."
    )

    # paper protocol — generate reproducibility protocol
    protocol_parser = subparsers.add_parser(
        "protocol", help="Generate reproducibility protocol from pipeline metadata."
    )
    protocol_parser.add_argument(
        "--search-dir", required=True, help="Path to search output directory"
    )
    protocol_parser.add_argument(
        "--output", "-o", default=None, help="Output file path (default: stdout)"
    )
    protocol_parser.add_argument(
        "--project-name", default="paper-writer", help="Project name for header"
    )

    # paper lint
    lint_parser = subparsers.add_parser("lint", help="Lint bibliography or style.")
    lint_sub = lint_parser.add_subparsers(dest="subcommand", required=True)
    lint_sub.add_parser("bib", help="Lint and normalize references.bib.")
    lint_sub.add_parser("style", help="Lint styling rules.")

    # paper check
    check_parser = subparsers.add_parser(
        "check", help="Check citations and references consistency."
    )
    check_sub = check_parser.add_subparsers(dest="subcommand", required=True)
    check_sub.add_parser("refs", help="Check inline citations against references.bib.")

    # paper audit (Phase 0 + existing)
    audit_parser = subparsers.add_parser("audit", help="Audit manuscript quality.")
    audit_sub = audit_parser.add_subparsers(dest="subcommand", required=True)
    audit_sub.add_parser("reporting", help="Audit manuscript against reporting checklists.")
    audit_prose = audit_sub.add_parser("prose", help="Analyze scientific prose quality (Phase 0).")
    audit_prose.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_prose.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_prose.add_argument("--whitelist", "-w", action="append", default=[], help="Terms to skip")
    audit_prose.set_defaults(func=_cmd_audit_prose)
    audit_claims = audit_sub.add_parser("claims", help="Detect claim candidates (Phase 0).")
    audit_claims.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_claims.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_claims.add_argument(
        "--whitelist", "-w", action="append", default=[], help="Terms to skip"
    )
    audit_claims.set_defaults(func=_cmd_audit_claims)
    audit_code_health = audit_sub.add_parser(
        "code-health",
        help="Audit code health (dead code, unused methods) via Trifecta graph.",
    )
    audit_code_health.add_argument(
        "--output", "-o", choices=["terminal", "json"], default="terminal"
    )
    audit_code_health.set_defaults(func=_cmd_audit_code_health)

    # paper audit citations
    audit_citations = audit_sub.add_parser(
        "citations", help="Verify citations against Crossref + Semantic Scholar."
    )
    audit_citations.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_citations.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_citations.add_argument(
        "--offline", action="store_true", help="Skip API calls (offline mode)"
    )
    audit_citations.set_defaults(func=_cmd_audit_citations)

    # paper audit ethics
    audit_ethics = audit_sub.add_parser("ethics", help="Check AI disclosure compliance.")
    audit_ethics.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_ethics.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_ethics.set_defaults(func=_cmd_audit_ethics)

    # paper audit writing-quality
    audit_wq = audit_sub.add_parser("writing-quality", help="Detect AI-typical writing patterns.")
    audit_wq.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_wq.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_wq.add_argument("--whitelist", "-w", action="append", default=[], help="Terms to skip")
    audit_wq.set_defaults(func=_cmd_audit_writing_quality)

    # paper audit factuality — claim-evidence overlap check
    audit_fact = audit_sub.add_parser(
        "factuality", help="Check claim-evidence factual accuracy via keyword overlap."
    )
    audit_fact.add_argument("file", help="Path to manuscript file")
    audit_fact.add_argument("--evidence", required=True, help="Path to screened_evidence.json")
    audit_fact.add_argument(
        "--threshold", type=float, default=0.30, help="Overlap threshold (default: 0.30)"
    )
    audit_fact.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_fact.set_defaults(func=_cmd_audit_factuality)

    # paper audit tables — validate required tables and figures
    audit_tbl = audit_sub.add_parser(
        "tables", help="Validate draft sections for required tables and figures."
    )
    audit_tbl.add_argument("draft_dir", help="Path to draft sections directory")
    audit_tbl.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_tbl.set_defaults(func=_cmd_audit_tables)

    # paper audit quality-appraisal — study quality scoring
    audit_qa = audit_sub.add_parser(
        "quality-appraisal", help="Score study quality on 5 dimensions."
    )
    audit_qa.add_argument("--evidence", required=True, help="Path to screened_evidence.json")
    audit_qa.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_qa.set_defaults(func=_cmd_audit_quality_appraisal)

    # paper trace — code traceability via Trifecta graph
    trace_parser = subparsers.add_parser(
        "trace", help="Trace code structure (callers, callees, paths) via Trifecta graph."
    )
    trace_parser.add_argument("symbol", help="Symbol to trace (e.g. 'Orchestrator.execute')")
    trace_parser.add_argument(
        "--action",
        "-a",
        choices=["callers", "callees", "path"],
        default="callers",
        help="Trace action (default: callers)",
    )
    trace_parser.add_argument(
        "--to",
        dest="to_symbol",
        default=None,
        help="Target symbol (required for 'path' action)",
    )
    trace_parser.add_argument(
        "--depth",
        "-d",
        type=int,
        default=1,
        help="Traversal depth for callers (1=direct, 3=transitive). Default: 1",
    )
    trace_parser.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    trace_parser.set_defaults(func=_cmd_trace)

    # paper graph-overview — graph health summary
    overview_parser = subparsers.add_parser(
        "graph-overview",
        help="Show Trifecta graph health overview (nodes, edges, cycles, orphans, hubs).",
    )
    overview_parser.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    overview_parser.set_defaults(func=_cmd_graph_overview)

    # paper gate (Phase 0)
    gate_parser = subparsers.add_parser(
        "gate", help="Run fail-closed methodological gates (Phase 0)."
    )
    gate_sub = gate_parser.add_subparsers(dest="subcommand", required=True)
    gate_method = gate_sub.add_parser("method", help="Apply EQUATOR-derived checklist gate.")
    gate_method.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    gate_method.add_argument(
        "--study-type",
        "-t",
        default="*",
        choices=[
            "*",
            "rct",
            "randomized_controlled_trial",
            "randomised_controlled_trial",
            "cohort",
            "case_control",
            "cross_sectional",
            "observational",
            "prospective",
            "retrospective",
            "systematic_review",
            "meta_analysis",
            "scoping_review",
            "literature_review",
            "narrative_review",
            "qualitative",
        ],
        help="Study type for checklist selection",
    )
    gate_method.add_argument(
        "--checklist",
        "-c",
        default=None,
        help="Explicit checklist name (e.g. 'consort', 'strobe', 'prisma')",
    )
    gate_method.add_argument(
        "--na", action="append", default=[], help="Item ID to mark as not applicable (repeatable)"
    )
    gate_method.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    gate_method.set_defaults(func=_cmd_gate_method)

    # paper import
    import_parser = subparsers.add_parser("import", help="Import external resources.")
    import_sub = import_parser.add_subparsers(dest="subcommand", required=True)
    import_bib = import_sub.add_parser("bib", help="Import .bib from Zotero/Better BibTeX export.")

    import_bib_source = import_bib.add_mutually_exclusive_group()
    import_bib_source.add_argument("source", nargs="?", help="Path to source .bib file to import.")
    import_bib_source.add_argument(
        "--from-zotero",
        action="store_true",
        help="Sync directly from Zotero/Better BibTeX library/collection.",
    )

    import_bib.add_argument(
        "--target",
        default="templates/references.bib",
        help="Target bibliography path (default: templates/references.bib).",
    )
    import_bib.add_argument(
        "--collection",
        default=None,
        help="Specific Zotero collection key (8-char string) to sync.",
    )
    import_bib.add_argument(
        "--since",
        type=int,
        default=None,
        help="Sync only changes made since this library version (integer).",
    )
    import_bib.add_argument(
        "--bbt-local",
        action="store_true",
        help="Pull from local Better BibTeX endpoint instead of cloud API.",
    )

    # paper render
    render_parser = subparsers.add_parser("render", help="Render final output formats.")
    render_parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=["docx", "pdf"],
        default=None,
        help="Output format(s). Can be repeated. Default: docx and pdf.",
    )
    render_parser.add_argument(
        "--csl",
        default=None,
        help="Path to CSL citation style file (e.g. styles/csl/vancouver.csl).",
    )
    render_parser.add_argument(
        "--reference-doc",
        default=None,
        help="Path to reference docx for styling.",
    )

    # paper zotero
    zotero_parser = subparsers.add_parser("zotero", help="Zotero library operations.")
    zotero_parser.add_argument(
        "--local",
        action="store_true",
        help="Use local Zotero (ZOTERO_LOCAL=true) instead of cloud API.",
    )
    zotero_sub = zotero_parser.add_subparsers(dest="subcommand", required=True)

    # zotero collections
    zotero_collections = zotero_sub.add_parser("collections", help="List all collections.")
    zotero_collections.set_defaults(func=_cmd_zotero_collections)

    # zotero search
    zotero_search = zotero_sub.add_parser("search", help="Full-text search in library.")
    zotero_search.add_argument("query", help="Search query.")
    zotero_search.add_argument(
        "--type", dest="item_type", default=None, help="Filter by item type (e.g. journalArticle)."
    )
    zotero_search.add_argument("--tag", default=None, help="Filter by tag.")
    zotero_search.add_argument("--collection", default=None, help="Limit to collection key.")
    zotero_search.add_argument("--limit", type=int, default=25, help="Max results (default 25).")
    zotero_search.add_argument(
        "--json", dest="output_json", action="store_true", help="Output as JSON."
    )
    zotero_search.set_defaults(func=_cmd_zotero_search)

    # zotero get
    zotero_get = zotero_sub.add_parser("get", help="Fetch a single item by key.")
    zotero_get.add_argument("key", help="8-character Zotero item key.")
    zotero_get.add_argument(
        "--json", dest="output_json", action="store_true", help="Output as JSON."
    )
    zotero_get.set_defaults(func=_cmd_zotero_get)

    # zotero create
    zotero_create = zotero_sub.add_parser("create", help="Create items from a JSON file.")
    zotero_create.add_argument("file", help="Path to JSON file with item data (array of items).")
    zotero_create.add_argument(
        "--collection", default=None, help="Add items to this collection key."
    )
    zotero_create.set_defaults(func=_cmd_zotero_create)

    # zotero template
    zotero_template = zotero_sub.add_parser("template", help="Get empty template for an item type.")
    zotero_template.add_argument("item_type", help="Item type (e.g. journalArticle, book).")
    zotero_template.set_defaults(func=_cmd_zotero_template)

    # zotero update
    zotero_update = zotero_sub.add_parser("update", help="Update an existing item.")
    zotero_update.add_argument("key", help="8-character Zotero item key.")
    zotero_update.add_argument("file", help="Path to JSON file with updated item data.")
    zotero_update.add_argument(
        "--version", type=int, default=None, help="Current item version. Auto-detected if omitted."
    )
    zotero_update.add_argument("--partial", action="store_true", help="Partial update (PATCH).")
    zotero_update.add_argument(
        "--dry-run", action="store_true", help="Show what would be updated without executing."
    )
    zotero_update.set_defaults(func=_cmd_zotero_update)

    # zotero delete
    zotero_delete = zotero_sub.add_parser("delete", help="Delete one or more items.")
    zotero_delete.add_argument("keys", nargs="+", help="Item key(s) to delete (max 50).")
    zotero_delete.add_argument(
        "--version",
        type=int,
        default=None,
        help="Current item/library version. Auto-detected if omitted.",
    )
    zotero_delete.add_argument(
        "--dry-run", action="store_true", help="Show what would be deleted without executing."
    )
    zotero_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt.")
    zotero_delete.set_defaults(func=_cmd_zotero_delete)

    # zotero upload
    zotero_upload = zotero_sub.add_parser("upload", help="Upload file to an attachment item.")
    zotero_upload.add_argument("key", help="Attachment item key.")
    zotero_upload.add_argument("file", help="Path to file to upload.")
    zotero_upload.add_argument(
        "--existing-md5", default=None, help="MD5 of existing file (for updates)."
    )
    zotero_upload.add_argument(
        "--force", action="store_true", help="Force re-upload if file exists."
    )
    zotero_upload.set_defaults(func=_cmd_zotero_upload)

    # paper verify
    subparsers.add_parser("verify", help="Run final verification check.")

    # paper doctor
    subparsers.add_parser("doctor", help="Check environment and report tool status.")

    # paper thesaurus (lazy — module may not be installed)
    _thesaurus_available = False
    try:
        from thesaurus.cli import _cmd_audit, _cmd_import, _cmd_list, _cmd_rebuild, _cmd_search

        _thesaurus_available = True
    except ImportError:

        def _cmd_unavailable(args: Any) -> None:
            print(
                "Error: thesaurus module not installed. "
                "Install with: cd skills/local/thesaurus && uv pip install -e .",
                file=sys.stderr,
            )
            sys.exit(1)

        _cmd_import = _cmd_search = _cmd_list = _cmd_audit = _cmd_rebuild = _cmd_unavailable

    thesaurus_parser = subparsers.add_parser(
        "thesaurus", help="Biomedical concept normalization (MeSH/DeCS)."
    )
    thesaurus_sub = thesaurus_parser.add_subparsers(dest="subcommand", required=True)

    thesaurus_import = thesaurus_sub.add_parser("import", help="Import concepts from JSONL.")
    thesaurus_import.add_argument("file", help="Path to JSONL file.")
    thesaurus_import.set_defaults(func=_cmd_import)

    thesaurus_search = thesaurus_sub.add_parser("search", help="Search concepts.")
    thesaurus_search.add_argument("query", help="Search query.")
    thesaurus_search.add_argument("--limit", type=int, default=20, help="Max results (default 20).")
    thesaurus_search.set_defaults(func=_cmd_search)

    thesaurus_list = thesaurus_sub.add_parser("list", help="List loaded concepts.")
    thesaurus_list.add_argument("--offset", type=int, default=0, help="Offset for pagination.")
    thesaurus_list.add_argument("--limit", type=int, default=50, help="Max results (default 50).")
    thesaurus_list.set_defaults(func=_cmd_list)

    thesaurus_audit = thesaurus_sub.add_parser("audit", help="Show thesaurus audit info.")
    thesaurus_audit.set_defaults(func=_cmd_audit)

    thesaurus_rebuild = thesaurus_sub.add_parser("rebuild", help="Rebuild DB from JSONL.")
    thesaurus_rebuild.set_defaults(func=_cmd_rebuild)

    # paper mesh (lazy — module may not be installed)
    try:
        from mesh_import.cli import register as _register_mesh

        _register_mesh(subparsers)
    except ImportError:

        def _cmd_mesh_unavailable(args: Any) -> None:
            print(
                "Error: mesh-import module not installed. "
                "Install with: cd skills/local/mesh-import && uv pip install -e .",
                file=sys.stderr,
            )
            sys.exit(1)

        mesh_parser = subparsers.add_parser("mesh", help="MeSH vocabulary import and lookup.")
        mesh_sub = mesh_parser.add_subparsers(dest="mesh_subcommand", required=True)
        mesh_fallback = mesh_sub.add_parser("import")
        mesh_fallback.set_defaults(func=_cmd_mesh_unavailable)
        mesh_resolve_fb = mesh_sub.add_parser("resolve")
        mesh_resolve_fb.set_defaults(func=_cmd_mesh_unavailable)
        mesh_expand_fb = mesh_sub.add_parser("expand")
        mesh_expand_fb.set_defaults(func=_cmd_mesh_unavailable)
        mesh_export_fb = mesh_sub.add_parser("export")
        mesh_export_fb.set_defaults(func=_cmd_mesh_unavailable)

    args = parser.parse_args()

    # Phase 0 commands (audit prose, audit claims, gate method, thesaurus) — run directly
    func = getattr(args, "func", None)
    if func is not None:
        func(args)
        return

    # paper doctor — runs directly, exits directly
    if args.command == "doctor":
        from harness.services.doctor import (
            check_all_tools,
            check_internal_capabilities,
            format_doctor_report,
        )

        repo_path = resolve_project_root(args.project, Path.cwd())
        tools = check_all_tools()
        caps = check_internal_capabilities(repo_path)
        print(format_doctor_report(tools, caps))
        sys.exit(0)

    # Map parsed arguments to OrchestratorRequest
    cmd_name = args.command
    sub_name = getattr(args, "subcommand", None)

    orch_command = cmd_name
    orch_args: dict[str, Any] = {}
    failure_policy = "stop_on_error"

    if cmd_name == "init":
        orch_args["preset"] = args.preset
        orch_args["mode"] = args.mode
        if args.search_window_start is not None and args.search_window_end is not None:
            orch_args["search_window"] = {
                "start_year": args.search_window_start,
                "end_year": args.search_window_end,
            }
    elif cmd_name == "search":
        if not args.query or not args.query.strip():
            print("Error: --query is required. Provide a research query.", file=sys.stderr)
            raise SystemExit(1) from None
        orch_args["query"] = args.query
        if args.raw_papers:
            orch_args["raw_papers"] = args.raw_papers
        # Forward Consensus/academic filter params to provider
        _CLI_FILTER_MAP = {  # noqa: N806  # Keys mirror SEARCH_FILTER_KEYS in harness.ports.paper_search_provider
            "year_min": args.year_min,
            "year_max": args.year_max,
            "study_types": args.study_types,
            "human": args.human or None,
            "sample_size_min": args.sample_size_min,
            "sjr_max": args.sjr_max,
            "duration_min": args.duration_min,
            "duration_max": args.duration_max,
            "exclude_preprints": args.exclude_preprints or None,
            "publisher_name": args.publisher_name,
            "clinical_guideline": args.clinical_guideline or None,
            "medical_mode": args.medical_mode or None,
        }
        for key, val in _CLI_FILTER_MAP.items():
            if val is not None:
                orch_args[key] = val
    elif cmd_name == "chain":
        orch_command = "chain"
        # R2-BH3: Validate chain parameter bounds
        _chain_errors: list[str] = []
        if args.max_rounds < 1:
            _chain_errors.append(f"--max-rounds must be ≥1, got {args.max_rounds}")
        if args.max_papers < 1:
            _chain_errors.append(f"--max-papers must be ≥1, got {args.max_papers}")
        if args.relevance_threshold <= 0 or args.relevance_threshold > 1:
            _chain_errors.append(
                f"--relevance-threshold must be 0<val≤1, got {args.relevance_threshold}"
            )
        if _chain_errors:
            print("Chain parameter validation error:", file=sys.stderr)
            for e in _chain_errors:
                print(f"  - {e}", file=sys.stderr)
            sys.exit(1)
        orch_args["max_rounds"] = args.max_rounds
        orch_args["max_papers"] = args.max_papers
        orch_args["relevance_threshold"] = args.relevance_threshold
        if not args.no_cache:
            orch_args["cache_dir"] = "outputs/.cache/s2_api"
    elif cmd_name == "export-bib":
        orch_command = "export_bib"
        orch_args["bib_path"] = args.bib_path
    elif cmd_name == "screen":
        orch_args["min_tier"] = args.min_tier
    elif cmd_name == "draft":
        if sub_name == "outline":
            orch_command = "draft_outline"
        elif sub_name == "section":
            orch_command = "draft_section"
            orch_args["name"] = args.name
        elif sub_name == "all":
            orch_command = "draft_all"
    elif cmd_name == "protocol":
        orch_command = "protocol"
        orch_args["search_dir"] = args.search_dir
        orch_args["output"] = args.output
        orch_args["project_name"] = args.project_name
    elif cmd_name == "lint":
        failure_policy = "continue_on_error"
        if sub_name == "bib":
            orch_command = "lint_bib"
        elif sub_name == "style":
            orch_command = "lint_style"
    elif cmd_name == "check":
        failure_policy = "continue_on_error"
        if sub_name == "refs":
            orch_command = "check_refs"
    elif cmd_name == "audit":
        failure_policy = "continue_on_error"
        if sub_name == "reporting":
            orch_command = "audit_reporting"
        elif sub_name == "ethics":
            orch_command = "audit_ethics"
            orch_args["manuscript"] = args.file
    elif cmd_name == "import":
        if sub_name == "bib":
            if not args.source and not args.from_zotero:
                sys.stderr.write(
                    "Error: Must specify source .bib file or "
                    "use --from-zotero to sync from Zotero.\n"
                )
                sys.exit(1)
            orch_command = "zotero_sync" if args.from_zotero else "import_bib"
            orch_args["source_bib"] = args.source or ""
            orch_args["target_bib"] = args.target
            orch_args["from_zotero"] = args.from_zotero
            orch_args["collection_key"] = args.collection
            orch_args["since_version"] = args.since
            orch_args["bbt_local"] = args.bbt_local
    elif cmd_name == "render":
        orch_args["output_formats"] = args.formats if args.formats else ["docx", "pdf"]
        orch_args["csl"] = args.csl
        orch_args["reference_doc"] = args.reference_doc

    repo_path = resolve_project_root(args.project, Path.cwd())

    # Load review config for non-init commands to forward mode + search_window
    if cmd_name != "init" and cmd_name not in ("doctor", "thesaurus", "mesh"):
        from harness.services.review_config import load_review_config

        review_cfg = load_review_config(repo_path)
        orch_args["mode"] = review_cfg.get("mode", "rapid")
        if review_cfg.get("search_window"):
            orch_args.setdefault("search_window", review_cfg["search_window"])
        if review_cfg.get("amendments"):
            orch_args.setdefault("amendments", review_cfg["amendments"])

    request = OrchestratorRequest(
        command=orch_command,
        requested_stage="unknown",
        failure_policy=failure_policy,
        args=orch_args,
        context={"cwd": str(repo_path), "actor": "cli"},
    )

    deps = build_orchestrator_dependencies(project_root=repo_path)
    orchestrator = Orchestrator(
        deps.repo_path,
        deps.state_manager,
        deps.checker,
        deps.action_runner,
        dict(deps.wrappers),
    )
    result = orchestrator.execute(request)

    # Format outputs
    _print_summary(result)
    sys.exit(result.exit_code)


def _print_summary(result: OrchestratorResult) -> None:
    """Outputs status-oriented console logs."""
    for step in result.steps:
        status = step.get("status")
        step_id = step.get("step_id")
        error = step.get("error")

        if status == "succeeded":
            print(f"[ok] Step: {step_id}")
        elif status == "failed":
            print(f"[!!] Step: {step_id} - FAILED")
            if error:
                print(f"     Error: {error}")
        else:
            print(f"[--] Step: {step_id} - {status.upper() if status else 'UNKNOWN'}")

    if result.success:
        print(
            f"\nSuccess: Stage progressed from '{result.stage_before}' to '{result.stage_after}'."
        )
    else:
        print("\nPipeline Blocked:")
        for blocker in result.blockers:
            print(f"  - {blocker}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.artifacts:
        print("\nArtifacts:")
        for artifact in result.artifacts:
            print(f"  - {artifact}")


if __name__ == "__main__":
    main()
