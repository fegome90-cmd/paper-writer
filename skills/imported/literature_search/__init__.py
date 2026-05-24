"""Literature search skill — imported from examen_grado source.

**Source:** /Users/felipe_gonzalez/Developer/examen_grado/skills/literature-search/

**What was imported:**
- ``resources/scoring.py`` → vendored as ``skills.imported.literature_search.scoring``
  Contains: PaperMetrics, ScoringWeights, calculate_d_score, calculate_final_score,
  classify_tier, get_default_weights, deduplicate, verify_citation
- ``SKILL.md`` → vendored as ``skills/imported/literature-search/resources/SKILL.md``
  Agent instructions for 5-phase systematic review (search, rank, export, synthesize)
- ``resources/*.md`` → vendored as ``skills/imported/literature-search/resources/``
  Protocol documentation (search-protocol, ranking-criteria, critical-appraisal,
  synthesis-protocol, citation-format, examples)

**What was NOT imported:**
- ``benchmark_dedup.py`` — benchmark script, not library code
- ``autoresearch.*`` — experiment tooling
- ``resources/tests/`` — vendored separately under ``tests/skills/test_scoring.py``
- ``_ctx/``, ``.atl/``, ``.pi/``, ``.mypy_cache/`` — tool artifacts

**Adapter usage:**
The adapter in ``skills.local.adapters`` imports scoring functions directly:
``deduplicate``, ``classify_tier``, ``ScoringWeights``, ``PaperMetrics``.
The adapter does NOT call external APIs — it applies scoring to results
provided by an external agent that follows the SKILL.md protocol.
"""

from skills.imported.literature_search.scoring import (  # noqa: F401
    PaperMetrics,
    ScoringWeights,
    calculate_d_score,
    calculate_final_score,
    classify_tier,
    deduplicate,
    get_default_weights,
    verify_citation,
)
