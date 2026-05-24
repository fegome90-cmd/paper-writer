"""Academic writer skill — imported from examen_grado source.

**Source:** /Users/felipe_gonzalez/Developer/examen_grado/skills/academic-writer/

**What was imported:**
- ``SKILL.md`` → vendored as ``skills/imported/academic-writer/SKILL.md``
  A **prompt collection** for Q1 journal sections (Abstract through Conclusion).
  Contains 7 section prompts with {placeholders}, writing guidelines, and
  CARS model structure. NOT executable code — prompts are copied into an LLM.

**What was NOT imported:**
- No Python code exists in the source skill. The entire skill is one SKILL.md file.
- No resources directory, no library, no CLI.

**Adapter usage:**
The adapter in ``skills.local.adapters`` reads the SKILL.md to extract section
structures (introduction uses CARS model, methods follows CONSORT, etc.) and
generates section skeletons. The adapter does NOT call an LLM — it produces
structured templates whose content follows the tone/structure defined in the
prompts. For real content generation, the SKILL.md prompts should be used
directly with an LLM.
"""
