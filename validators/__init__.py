"""Domain validation rules for the paper-writer pipeline.

Modules:
  - refs.py          — bibliography metadata requirements (year, DOI/URL)
  - citations.py     — citation key consistency against bibliography
  - structure.py     — section presence and structure
  - reporting.py     — reporting checklist completeness
  - style.py         — prose style policy (passive voice, sentence length)

These are pure domain functions — no file I/O, no subprocess calls.
Tool wrappers in integrations/tools/ delegate to these for validation logic.
"""
