"""External tool wrappers (per REPO_ARCHITECTURE.md §3).

Modules:
  - base.py                    — ToolWrapper port, ValidatorResult, ToolNotAvailableError
  - bibtex_tidy.py             — bibliography normalization (gate: bib_normalized)
  - refs_validator.py          — citation-to-bib consistency (gate: citations_resolved)
  - refs_metadata_validator.py — bib entry metadata rules (gate: refs_validated)
  - vale.py                    — prose style linting (gate: style_passed)
  - reporting_auditor.py       — reporting checklist audit (gate: reporting_passed)

Tool wrappers conform to the validator contract defined in VALIDATOR_CONTRACTS.md
and return ValidatorResult objects consumed by the gate system.
"""

from integrations.tools.base import ToolNotAvailableError, ToolWrapper, ValidatorResult
from integrations.tools.bibtex_tidy import BibliographyNormalizer
from integrations.tools.pandoc import PandocRenderer
from integrations.tools.refs_metadata_validator import RefsMetadataValidator
from integrations.tools.refs_validator import RefsValidator
from integrations.tools.reporting_auditor import ReportingAuditor
from integrations.tools.vale import StyleLinter
from integrations.tools.zotero_import import ZoteroImporter

__all__ = [
    "BibliographyNormalizer",
    "PandocRenderer",
    "RefsMetadataValidator",
    "RefsValidator",
    "ReportingAuditor",
    "StyleLinter",
    "ToolNotAvailableError",
    "ToolWrapper",
    "ValidatorResult",
    "ZoteroImporter",
]
