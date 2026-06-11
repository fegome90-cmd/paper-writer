"""Manifest loader and validator for thesaurus JSONL imports."""

import hashlib
from pathlib import Path
from typing import Any, cast


class ManifestError(Exception):
    """Raised when manifest validation fails."""


def load_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Load a manifest.json file.

    Args:
        manifest_path: Path to the manifest file.

    Returns:
        Parsed manifest dict.

    Raises:
        ManifestError: If file is missing or invalid JSON.
    """
    import json

    path = Path(manifest_path)
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")

    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        raise ManifestError(f"Invalid JSON in manifest: {e}") from e


def validate_manifest(manifest: dict[str, Any], jsonl_path: str | Path) -> None:
    """Validate manifest against the JSONL file.

    Checks:
    - sha256 matches file content
    - concept_count matches JSONL line count

    Args:
        manifest: Parsed manifest dict.
        jsonl_path: Path to the JSONL file.

    Raises:
        ManifestError: On validation failure.
    """
    jsonl_path = Path(jsonl_path)

    if not jsonl_path.exists():
        raise ManifestError(f"Source JSONL not found: {jsonl_path}")

    # Validate SHA256
    content = jsonl_path.read_bytes()
    actual_sha = hashlib.sha256(content).hexdigest()
    expected_sha = manifest.get("sha256", "")
    if actual_sha != expected_sha:
        raise ManifestError(f"SHA256 mismatch: expected {expected_sha}, got {actual_sha}")

    # Validate concept_count — count non-empty lines from the raw bytes already read
    actual_count = sum(1 for line in content.splitlines() if line.strip())
    expected_count = manifest.get("concept_count", -1)
    if actual_count != expected_count:
        raise ManifestError(
            f"concept_count mismatch: expected {expected_count}, got {actual_count}"
        )
