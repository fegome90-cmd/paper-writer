"""CLI direct-call functions for paper thesaurus commands."""

import json
import sys
from pathlib import Path


def _cmd_import(args) -> None:
    """Handle paper thesaurus import."""
    from thesaurus.factory import create_store
    from thesaurus.manifest import ManifestError, load_manifest, validate_manifest
    from thesaurus.mesh_loader import load_jsonl, validate_jsonl_readable

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    manifest_path = file_path.parent / "manifest.json"

    try:
        manifest = load_manifest(manifest_path)
        validate_manifest(manifest, file_path)
        validate_jsonl_readable(file_path)
        concepts = load_jsonl(file_path)
        store = create_store()
        count = store.import_concepts(concepts)
        print(f"Loaded {count} concepts from {file_path.name}")
    except ManifestError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_search(args) -> None:
    """Handle paper thesaurus search."""
    from thesaurus.factory import create_store

    store = create_store()
    results = store.search(args.query, limit=args.limit if hasattr(args, "limit") else 20)

    if not results:
        print("No concepts found")
        return

    for r in results:
        print(f"  [{r['match_type']}] {r['preferred_label']} ({r['id']})")


def _cmd_list(args) -> None:
    """Handle paper thesaurus list."""
    from thesaurus.factory import create_store

    store = create_store()
    offset = getattr(args, "offset", 0)
    limit = getattr(args, "limit", 50)
    results = store.list_concepts(offset=offset, limit=limit)

    if not results:
        print("No concepts found")
        return

    for r in results:
        notation = f" [{r['notation']}]" if r.get("notation") else ""
        print(f"  {r['preferred_label']}{notation} ({r['id']})")


def _cmd_audit(args) -> None:
    """Handle paper thesaurus audit."""
    from thesaurus.audit import format_audit
    from thesaurus.factory import create_store

    store = create_store()
    print(format_audit(store))


def _cmd_rebuild(args) -> None:
    """Handle paper thesaurus rebuild."""
    from thesaurus.factory import create_store

    store = create_store()
    store.rebuild()
    count = store.concept_count
    print(f"Rebuilt thesaurus: {count} concepts loaded")
