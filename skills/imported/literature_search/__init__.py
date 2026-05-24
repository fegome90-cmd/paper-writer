"""Literature search skill — Phase 3 MVP.

Simplified skill that generates structured search artifacts from a query.
In production, this would call PubMed, Semantic Scholar, or similar APIs.
"""

from skills.imported.literature_search.search import LiteratureSearchSkill

__all__ = ["LiteratureSearchSkill"]
