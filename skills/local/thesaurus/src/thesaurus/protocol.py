"""SemanticStore ABC and StorageCapabilities."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StorageCapabilities:
    """Declare store capabilities for feature gating."""

    vector_search: bool = False
    full_text: bool = True


class SemanticStore(ABC):
    """Abstract base class for biomedical concept stores."""

    @abstractmethod
    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Return matching concepts with match_type metadata.

        Returns list of dicts with keys: id, preferred_label, match_type, notation.
        match_type priority: preferred_label > synonym > entry > related > tree_number.
        """
        ...

    @abstractmethod
    def add_concept(self, concept: dict) -> None:
        """Insert or replace a single concept."""
        ...

    @abstractmethod
    def list_concepts(self, offset: int = 0, limit: int = 50) -> list[dict]:
        """List concepts with pagination."""
        ...

    @abstractmethod
    def import_concepts(self, concepts: list[dict]) -> int:
        """Import pre-validated concept dicts.

        Uses INSERT OR REPLACE for duplicate IDs.
        Transactional: on any failure, full rollback.
        Updates meta table last_import timestamp.
        """
        ...

    @abstractmethod
    def audit(self) -> dict:
        """Return audit info: concept_count, last_import, profile, manifest_sha256."""
        ...

    @abstractmethod
    def stats(self) -> dict:
        """Return stats: total_concepts, fts5_enabled, db_size_bytes."""
        ...

    @abstractmethod
    def rebuild(self) -> None:
        """Delete DB, run migration, re-import from JSONL. Idempotent."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> StorageCapabilities:
        """Store capabilities."""
        ...

    @property
    @abstractmethod
    def concept_count(self) -> int:
        """Current number of concepts in the store."""
        ...
