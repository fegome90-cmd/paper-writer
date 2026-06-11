class ThesaurusError(Exception):
    """Base class for thesaurus errors."""


class RebuildError(ThesaurusError):
    """Raised when a rebuild operation fails, ensuring atomic rollback."""
