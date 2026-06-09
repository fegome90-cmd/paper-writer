"""Audit report writer for thesaurus store."""


def format_audit(store) -> str:
    """Format audit output as human-readable text.

    Args:
        store: SemanticStore instance.

    Returns:
        Formatted audit string.
    """
    info = store.audit()
    lines = [
        "Thesaurus Audit Report",
        "=" * 40,
        f"  Concept count:    {info['concept_count']}",
        f"  Last import:      {info['last_import']}",
        f"  Store profile:    {info['profile']}",
        f"  Manifest SHA256:  {info['manifest_sha256'] or 'N/A'}",
    ]
    return "\n".join(lines)
