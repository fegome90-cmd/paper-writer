"""Zotero CLI handlers and parser registration.

Extracted from main.py in PR1 of cli-structural-refactoring.
All handlers preserve current behavior: SystemExit(1) on error,
lazy imports of clients.zotero inside handler bodies.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from cli.paper.errors import ExternalServiceError, UserInputError
from cli.paper.output import emit_json, emit_result


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
        raise UserInputError(err)
    try:
        collections = client.fetch_collections()
        for c in collections:
            parent = c.get("parentCollection", False)
            prefix = "  " if parent else ""
            emit_result(f"{prefix}{c['key']}: {c['name']}")
        emit_result(f"\n{len(collections)} collection(s)")
    except ZoteroError as exc:
        raise ExternalServiceError(str(exc)) from exc


def _cmd_zotero_search(args: Any) -> None:

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        raise UserInputError(err)
    try:
        results = client.search_items(
            args.query,
            item_type=args.item_type,
            tag=args.tag,
            collection_key=args.collection,
            limit=args.limit,
        )
        if args.output_json:
            emit_json(results)
            return
        for item in results:
            key = item.get("key", "?")
            title = item.get("title", "(no title)")
            year = item.get("date", "")[:4] if item.get("date") else ""
            item_type = item.get("itemType", "")
            emit_result(f"  {key}  {year:>4}  {item_type:<20}  {title}")
        emit_result(f"\n{len(results)} result(s)")
    except ZoteroError as exc:
        raise ExternalServiceError(str(exc)) from exc


def _cmd_zotero_get(args: Any) -> None:

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        raise UserInputError(err)
    try:
        item = client.get_item(args.key)
        if args.output_json:
            emit_json(item)
            return
        data = item.get("data", item) if isinstance(item, dict) else item
        if isinstance(data, dict):
            for k, v in data.items():
                if k not in ("key", "version", "itemType") and v:
                    emit_result(f"  {k}: {v}")
    except (ZoteroError, ValueError) as exc:
        raise ExternalServiceError(str(exc)) from exc


def _cmd_zotero_create(args: Any) -> None:
    import json as _json

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        raise UserInputError(err)
    try:
        items = _json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, FileNotFoundError) as exc:
        raise UserInputError(f"Error reading {args.file}: {exc}") from exc

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
        emit_result(
            f"Created: {len(successful)}, Unchanged: {len(unchanged)}, Failed: {len(failed)}"
        )
        for idx, item_data in successful.items():
            if isinstance(item_data, dict):
                emit_result(f"  {item_data.get('key', '?')}: {item_data.get('title', 'ok')}")
            else:
                emit_result(f"  [{idx}]: {item_data}")
        for idx, info in failed.items():
            print(f"  FAILED [{idx}]: {info}", file=sys.stderr)
    except ZoteroError as exc:
        raise ExternalServiceError(str(exc)) from exc


def _cmd_zotero_template(args: Any) -> None:

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        raise UserInputError(err)
    try:
        template = client.get_item_template(args.item_type)
        emit_json(template)
    except ZoteroError as exc:
        raise ExternalServiceError(str(exc)) from exc


def _cmd_zotero_update(args: Any) -> None:
    import json as _json

    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        raise UserInputError(err)
    try:
        changes = _json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, FileNotFoundError) as exc:
        raise UserInputError(f"Error reading {args.file}: {exc}") from exc

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
                    raise UserInputError("Could not determine version. Use --version.")
                    # print removed
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
                raise UserInputError("Could not determine version. Use --version.")
                # print removed

            if not isinstance(current_data, dict):
                raise UserInputError("Could not extract item data for update")
            # Merge: user data overwrites current fields
            merged = {**current_data, **changes}
            merged["key"] = args.key
            merged["version"] = version
            # Remove read-only fields that cause 400 on PUT
            for readonly_field in ("dateAdded", "dateModified", "citationKey"):
                merged.pop(readonly_field, None)
            headers = client.update_item(args.key, merged, version=version)
        new_version = headers.get("Last-Modified-Version", "?")
        emit_result(f"Updated {args.key} → version {new_version}")
    except (ZoteroError, ValueError) as exc:
        raise ExternalServiceError(str(exc)) from exc


def _cmd_zotero_delete(args: Any) -> None:
    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        raise UserInputError(err)

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
                    raise UserInputError("Could not determine item version. Use --version.")
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
            emit_result(f"Deleted {args.keys[0]} (version {version})")
        else:
            # Batch: require library version
            if args.version is None:
                raise UserInputError("--version (library version) is required for batch delete.")
            client.delete_items(args.keys, library_version=args.version)
            emit_result(f"Deleted {len(args.keys)} items")
    except (ZoteroError, ValueError) as exc:
        raise ExternalServiceError(str(exc)) from exc


def _cmd_zotero_upload(args: Any) -> None:
    from clients.zotero import ZoteroError

    client, err = _zotero_client(local=getattr(args, "local", False))
    if err:
        raise UserInputError(err)

    try:
        result = client.upload_file(
            args.key,
            args.file,
            existing_md5=args.existing_md5,
            force_update=args.force,
        )
        emit_result(f"Status: {result.get('status')}")
        if result.get("status") == "uploaded":
            emit_result(f"  File: {result.get('filename')}")
            emit_result(f"  Size: {result.get('size')} bytes")
            emit_result(f"  MD5:  {result.get('md5')}")
        else:
            emit_result(f"  {result.get('message', 'File already exists')}")
    except (ZoteroError, ValueError) as exc:
        raise ExternalServiceError(str(exc)) from exc


def register_zotero(subparsers: Any) -> None:
    """Register all zotero subcommands on the given subparsers."""
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
