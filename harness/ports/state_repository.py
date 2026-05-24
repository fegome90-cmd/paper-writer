from abc import ABC, abstractmethod

from harness.domain.state import ManuscriptState


class StateRepositoryError(Exception):
    """Raised for serialization and persistence issues in the repository."""

    pass


class StateRepository(ABC):
    """Abstract port defining persistence contract for ManuscriptState."""

    @abstractmethod
    def exists(self) -> bool:
        """Returns True if the persisted state exists."""
        pass

    @abstractmethod
    def load(self) -> ManuscriptState:
        """Loads and returns the ManuscriptState from persistence."""
        pass

    @abstractmethod
    def save(self, state: ManuscriptState) -> None:
        """Persists the ManuscriptState to storage."""
        pass
