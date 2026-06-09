"""CLI direct-call functions for paper mesh commands."""

import argparse
import json
import os
import sys

_DEFAULT_DB_PATH = os.path.join("workspace", "mesh.db")


def _print_error(message: str, phase: str) -> None:
    print(json.dumps({"error": message, "phase": phase}), file=sys.stderr)
    sys.exit(1)


def _infer_phase(exc: Exception) -> str:
    exc_type = type(exc).__name__
    msg = str(exc).lower()

    if exc_type in ("ParseError", "XMLSyntaxError"):
        return "xml_parse"
    if exc_type == "ChecksumMismatchError":
        return "xml_parse"
    if exc_type == "FileNotFoundError":
        return "xml_parse"
    if "staging" in msg or "migration" in msg:
        return "staging_create"
    if "validation" in msg:
        return "validation"
    if "fts" in msg or "rebuild" in msg:
        return "fts_rebuild"
    if "swap" in msg or "rename" in msg or "move" in msg or "exdev" in msg:
        return "final_swap"
    return "data_import"


def _cmd_import(args: argparse.Namespace) -> None:
    from lxml import etree

    from mesh_import.store import ChecksumMismatchError, MeshStore

    xml_path = args.xml_path
    dtd_path = getattr(args, "dtd_path", None)
    db_path = getattr(args, "db_path", None) or _DEFAULT_DB_PATH

    if not os.path.exists(xml_path):
        _print_error(f"File not found: {xml_path}", "xml_parse")

    store = MeshStore(db_path)

    try:
        result = store.import_xml(xml_path, dtd_path)
        print(json.dumps(result))
    except ChecksumMismatchError as exc:
        _print_error(str(exc), "xml_parse")
    except etree.ParseError as exc:
        _print_error(str(exc), "xml_parse")
    except Exception as exc:
        _print_error(str(exc), _infer_phase(exc))


def _cmd_resolve(args: argparse.Namespace) -> None:
    from mesh_import.store import MeshStore

    db_path = getattr(args, "db_path", None) or _DEFAULT_DB_PATH
    store = MeshStore(db_path)
    results = store.resolve(args.term)
    print(json.dumps(results, ensure_ascii=False))


def _cmd_expand(args: argparse.Namespace) -> None:
    from mesh_import.store import MeshStore

    db_path = getattr(args, "db_path", None) or _DEFAULT_DB_PATH
    store = MeshStore(db_path)
    results = store.expand_tree(args.descriptor_ui)
    print(json.dumps(results, ensure_ascii=False))


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register 'mesh' subparser with import, resolve, expand subcommands."""
    mesh_parser = subparsers.add_parser("mesh", help="MeSH vocabulary import and lookup.")
    mesh_sub = mesh_parser.add_subparsers(dest="mesh_subcommand", required=True)

    mesh_import = mesh_sub.add_parser("import", help="Import MeSH XML file.")
    mesh_import.add_argument("xml_path", help="Path to desc2026.xml.")
    mesh_import.add_argument("--dtd-path", default=None, help="Path to companion DTD file.")
    mesh_import.add_argument(
        "--db-path",
        default=None,
        help=f"Target DB path (default: {_DEFAULT_DB_PATH}).",
    )
    mesh_import.add_argument(
        "--progress-interval",
        type=int,
        default=5000,
        help="Progress reporting interval in descriptors (default: 5000).",
    )
    mesh_import.set_defaults(func=_cmd_import)

    mesh_resolve = mesh_sub.add_parser("resolve", help="Resolve term to descriptors via FTS5.")
    mesh_resolve.add_argument("term", help="Search term.")
    mesh_resolve.add_argument(
        "--db-path",
        default=None,
        help=f"DB path (default: {_DEFAULT_DB_PATH}).",
    )
    mesh_resolve.set_defaults(func=_cmd_resolve)

    mesh_expand = mesh_sub.add_parser("expand", help="Expand descriptor tree hierarchy.")
    mesh_expand.add_argument("descriptor_ui", help="Descriptor UI (e.g. D000001).")
    mesh_expand.add_argument(
        "--db-path",
        default=None,
        help=f"DB path (default: {_DEFAULT_DB_PATH}).",
    )
    mesh_expand.set_defaults(func=_cmd_expand)
