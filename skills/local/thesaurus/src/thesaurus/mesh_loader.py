"""JSONL loader — parses MeSH/DeCS concept files into domain dicts."""

import json
from pathlib import Path
from typing import Any


def load_jsonl(file_path: str | Path) -> list[dict[str, Any]]:
    """Parse a JSONL file into a list of concept dicts.

    Each line must be valid JSON with at least 'id' and 'preferred_label' fields.
    Raises ValueError with line number on any malformed record.

    Args:
        file_path: Path to the JSONL file.

    Returns:
        List of concept dicts.

    Raises:
        ValueError: On malformed JSON or missing required fields.
    """
    path = Path(file_path)
    concepts = []

    with open(path, encoding="utf-8-sig") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed JSON on line {line_num}: {e}") from e

            # Validate required fields
            if "id" not in record:
                raise ValueError(f"Missing required field 'id' on line {line_num}")
            if "preferred_label" not in record:
                raise ValueError(f"Missing required field 'preferred_label' on line {line_num}")

            # Normalize alt_labels to JSON string for storage
            alt_labels = record.get("alt_labels", [])
            if isinstance(alt_labels, list):
                record["alt_labels"] = json.dumps(alt_labels)
            else:
                record["alt_labels"] = json.dumps([])

            concepts.append(record)

    return concepts


def validate_jsonl_readable(file_path: str | Path) -> None:
    """Lightweight structural check on a JSONL file.

    Reads first 2 lines to verify structure. Does NOT read the full file.
    Raises ValueError on structural issues.

    Args:
        file_path: Path to the JSONL file.

    Raises:
        ValueError: On structural issues (empty file, malformed lines).
    """
    path = Path(file_path)
    lines = []

    with open(path, encoding="utf-8-sig") as f:
        for i, line in enumerate(f):
            lines.append(line.strip())
            if i >= 1:
                break

    non_blank = [line for line in lines if line]
    if not non_blank:
        raise ValueError("JSONL file is empty (no non-blank lines)")

    # Validate each read line is valid JSON
    for i, line in enumerate(lines):
        if line:
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Line {i + 1} is not valid JSON: {e}") from e
