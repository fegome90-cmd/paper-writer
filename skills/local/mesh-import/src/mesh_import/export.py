"""Mesh-to-JSONL export — converts mesh-import SQLite to thesaurus JSONL format."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_REQUIRED_TABLES = (
    "mesh_descriptor",
    "mesh_concept",
    "mesh_term",
    "mesh_descriptor_tree",
    "mesh_concept_relation",
)


def _check_tables(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ({})".format(
            ",".join("?" for _ in _REQUIRED_TABLES)
        ),
        _REQUIRED_TABLES,
    ).fetchall()
    found = {r[0] for r in rows}
    missing = set(_REQUIRED_TABLES) - found
    if missing:
        raise RuntimeError(f"Missing required tables: {', '.join(sorted(missing))}")


def _load_descriptors(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return conn.execute(
        "SELECT descriptor_ui, descriptor_name FROM mesh_descriptor ORDER BY descriptor_ui ASC"
    ).fetchall()


def _load_alt_labels(conn: sqlite3.Connection) -> dict[str, list[str]]:
    rows = conn.execute(
        """SELECT mc.descriptor_ui, mt.term_text
           FROM mesh_term mt
           JOIN mesh_concept mc ON mc.concept_ui = mt.concept_ui
           WHERE mt.is_preferred = 0 OR mc.is_preferred = 0
           ORDER BY mc.descriptor_ui, mt.term_text"""
    ).fetchall()
    labels: dict[str, list[str]] = {}
    for dui, text in rows:
        labels.setdefault(dui, []).append(text)
    return labels


def _load_concept_map(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT concept_ui, descriptor_ui FROM mesh_concept"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _load_relations(
    conn: sqlite3.Connection, concept_map: dict[str, str]
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    broader: dict[str, set[str]] = {}
    narrower: dict[str, set[str]] = {}
    related: dict[str, set[str]] = {}

    rows = conn.execute(
        """SELECT mc_src.descriptor_ui AS src_dui,
                  mc_tgt.descriptor_ui AS tgt_dui,
                  mcr.relation_type
           FROM mesh_concept_relation mcr
           JOIN mesh_concept mc_src ON mc_src.concept_ui = mcr.source_concept_ui
           JOIN mesh_concept mc_tgt ON mc_tgt.concept_ui = mcr.target_concept_ui"""
    ).fetchall()

    for src_dui, tgt_dui, rel_type in rows:
        if src_dui == tgt_dui:
            continue
        bucket = (
            broader if rel_type == "BRD" else narrower if rel_type == "NRW" else related
        )
        bucket.setdefault(src_dui, set()).add(tgt_dui)

    return broader, narrower, related


def _load_notation(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT descriptor_ui, tree_number FROM mesh_descriptor_tree ORDER BY descriptor_ui, tree_number ASC"
    ).fetchall()
    notation: dict[str, str] = {}
    for dui, tn in rows:
        if dui not in notation:
            notation[dui] = tn
    return notation


def _join_sorted(values: set[str] | None) -> str:
    if not values:
        return ""
    return "|".join(sorted(values))


def export_jsonl(db_path: str | Path, output_path: str | Path) -> dict:
    """Export all MeSH descriptors to JSONL + manifest.

    Returns: {"concept_count": int, "sha256": str, "output_path": str}
    Raises: FileNotFoundError if db_path doesn't exist
    Raises: RuntimeError if db_path exists but lacks expected tables
    """
    db_path = Path(db_path)
    output_path = Path(output_path)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        _check_tables(conn)

        descriptors = _load_descriptors(conn)
        alt_labels = _load_alt_labels(conn)
        concept_map = _load_concept_map(conn)
        broader, narrower, related = _load_relations(conn, concept_map)
        notation = _load_notation(conn)
    finally:
        conn.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    sha256 = hashlib.sha256()
    concept_count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for dui, name in descriptors:
            record = {
                "id": dui,
                "preferred_label": name,
                "alt_labels": list(dict.fromkeys(alt_labels.get(dui, []))),
                "broader": _join_sorted(broader.get(dui)),
                "narrower": _join_sorted(narrower.get(dui)),
                "related": _join_sorted(related.get(dui)),
                "notation": notation.get(dui, ""),
                "source": "mesh",
            }
            line = json.dumps(record, ensure_ascii=False, sort_keys=True)
            line_bytes = (line + "\n").encode("utf-8")
            sha256.update(line_bytes)
            f.write(line + "\n")
            concept_count += 1

    sha256_hex = sha256.hexdigest()

    manifest = {
        "source_file": output_path.name,
        "sha256": sha256_hex,
        "concept_count": concept_count,
        "source": "mesh",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1",
    }
    manifest_path = output_path.parent / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "concept_count": concept_count,
        "sha256": sha256_hex,
        "output_path": str(output_path),
    }


