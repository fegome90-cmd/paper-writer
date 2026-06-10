"""Audit report writer for thesaurus store."""


def format_audit(store) -> str:
    """Format audit output as human-readable text.

    Args:
        store: SemanticStore instance.

    Returns:
        Formatted audit string.
    """
    info = store.audit()
    source = info.get("source", "")
    source_label = {
        "synthetic": "synthetic (sample data — NOT production vocabulary)",
        "mesh": "MeSH (production vocabulary)",
        "decs": "DeCS (production vocabulary)",
        "local": "local custom vocabulary",
    }.get(source, source or "unknown")
    lines = [
        "Thesaurus Audit Report",
        "=" * 40,
        f"  Concept count:    {info['concept_count']}",
        f"  Last import:      {info['last_import']}",
        f"  Store profile:    {info['profile']}",
        f"  Vocabulary source:{source_label}",
        f"  Manifest SHA256:  {info['manifest_sha256'] or 'N/A'}",
    ]
    return "\n".join(lines)
