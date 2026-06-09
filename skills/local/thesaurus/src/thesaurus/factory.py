"""Factory for creating SemanticStore instances based on profile."""

import os

from thesaurus.protocol import SemanticStore, StorageCapabilities


def create_store(db_path: str | None = None) -> SemanticStore:
    """Create a SemanticStore based on PAPER_THESAURUS_PROFILE env var.

    Args:
        db_path: Optional override for database file location.

    Returns:
        SemanticStore instance.

    Raises:
        ValueError: If profile is not 'lite' or unset.
    """
    profile = os.environ.get("PAPER_THESAURUS_PROFILE", "lite")

    if profile == "lite":
        from thesaurus.lite import LiteSemanticStore

        return LiteSemanticStore(db_path=db_path)
    elif profile == "full":
        raise ValueError(
            "Full profile (Postgres+pgvector) is not implemented yet. "
            "Use PAPER_THESAURUS_PROFILE=lite or unset the variable."
        )
    else:
        raise ValueError(f"Unknown thesaurus profile: {profile!r}. Valid: 'lite', 'full'.")
