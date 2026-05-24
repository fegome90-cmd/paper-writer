"""Academic writer skill — imported from examen_grado source.

**Source:** /Users/felipe_gonzalez/Developer/examen_grado/skills/academic-writer/

**What was imported:**
- ``SKILL.md`` → vendored as ``skills/imported/academic_writer/SKILL.md``
  A **prompt collection** for Q1 journal sections (Abstract through Conclusion).
  Contains 7 section prompts with {placeholders}, writing guidelines, and
  CARS model structure. NOT executable code — prompts are copied into an LLM.

**What was derived:**
- ``sections_manifest.json`` → extracted from SKILL.md by manual audit.
  Machine-readable structure (models, subsections, tone, rules) for each section.
  ``drafting.py`` reads this at runtime — no section data is hardcoded.

**What was NOT imported:**
- No Python code exists in the source skill. The entire skill is one SKILL.md file.
- No resources directory, no library, no CLI.

**Adapter usage:**
The adapter in ``skills.local.adapters`` calls ``drafting.py``, which reads
``sections_manifest.json`` (derived from SKILL.md) to get section structure.
For real content generation, use the SKILL.md prompts directly with an LLM.
"""
