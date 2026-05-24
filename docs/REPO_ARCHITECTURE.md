# paper-writer - Repository Architecture

## Purpose

Define where the CLI lives, where external tools are integrated, where imported skills are stored, and how the end-to-end workflow runs.

This document is intentionally practical.
It defines the repository shape needed to build the base first, before integrating domain-specific writing workflows.

## Architectural Principle

The repository has four layers:

1. **CLI layer** — the entrypoint the agent or user runs
2. **Harness layer** — workflow control, state machine, gate enforcement
3. **Integration layer** — wrappers around external tools and imported skills
4. **Artifact layer** — templates, outputs, logs, manifests, rendered documents

The CLI does not contain business logic.
The harness does not call system binaries directly.
Tool wrappers and skill wrappers isolate that behavior.

## Placement Decisions

## 1. CLI

The project CLI lives under:

```text
cli/paper/
```

Recommended files:

```text
cli/paper/
  __init__.py
  main.py
  commands/
    init.py
    verify.py
    search.py
    draft.py
    render.py
```

Responsibility:

- parse arguments
- route commands to harness actions
- print user-facing status
- never embed workflow rules directly

## 2. Harness

The harness lives under:

```text
harness/
```

Recommended files:

```text
harness/
  __init__.py
  state_manager.py
  gates.py
  orchestrator.py
```

Responsibility:

- load and update `outputs/state.yaml`
- validate and serialize stage/gate transitions
- decide whether a command is allowed to run
- aggregate results from validators, tools, and skills
- produce pass/fail delivery decisions and final manifest artifacts

## 3. External Tool Wrappers

External tools should NOT be scattered across the CLI or harness.
They should be wrapped under:

```text
integrations/tools/
```

Recommended files:

```text
integrations/tools/
  pandoc.py
  vale.py
  bibtex_tidy.py
  refs_validator.py
```

Responsibility:

- check if a CLI exists in PATH
- build commands consistently
- normalize stdout/stderr/results into structured Python responses
- fail closed when a required dependency is missing

Important rule:

- tools are **installed**, not cloned, by default
- clone a tool only if package install is not sufficient or reproducibility requires vendoring

## 4. Imported and Local Skills

Skills should be split into two groups:

```text
skills/imported/
skills/local/
```

### `skills/imported/`

Use this for skills vendored from external repos. Each imported skill reflects its real source:

```text
skills/imported/
  academic_writer/
    __init__.py            # Docstring documenting source + what was imported
    SKILL.md               # Vendored from source (prompt collection — no Python code)
    drafting.py            # Adapted from SKILL.md: section structure extraction
  literature_search/
    __init__.py            # Re-exports from scoring.py
    scoring.py             # Vendored verbatim from source (340+ lines, real scoring engine)
    search.py              # Wraps scoring engine for dedup+scoring+tier pipeline
    resources/
      __init__.py
      SKILL.md             # Vendored: 5-phase systematic review agent instructions
      search-protocol.md   # Vendored: database strategies, API usage
      ranking-criteria.md  # Vendored: scoring A-E formula, tiers
      critical-appraisal.md  # Vendored: RoB assessment
      synthesis-protocol.md  # Vendored: Phase 5 claim verification
      citation-format.md   # Vendored: APA 7th & Vancouver
      examples.md          # Vendored: worked examples
```

**Source paths:**
- literature-search: `/Users/felipe_gonzalez/Developer/examen_grado/skills/literature-search/`
- academic-writer: `/Users/felipe_gonzalez/Developer/examen_grado/skills/academic-writer/`

**What `scoring.py` contains (REAL imported code):**
- `PaperMetrics` — frozen dataclass with all scoring dimensions
- `ScoringWeights` — configurable weights (sum to 1.0)
- `calculate_d_score()` — methodological quality composite
- `calculate_final_score()` — weighted A-E score
- `classify_tier()` — maps score to Tier 1/2/3/Discard
- `get_default_weights()` — phase-specific presets
- `deduplicate()` — DOI/PMID/title similarity dedup with stop-word filtering
- `verify_citation()` — CrossRef/PubMed API verification

**What `drafting.py` adapts (NOT copied verbatim):**
- Source SKILL.md is a prompt collection with 7 section prompts
- No Python code in source — `drafting.py` extracts section structures
  (CARS model for intro, CONSORT for methods, APA 7th for results)
- Generates section skeletons, NOT LLM content
- For real writing, the SKILL.md prompts must be used with an LLM

Each imported skill is a self-contained module with no dependency on `harness/` or `cli/`.

### `skills/local/`

Use this for repo-native adapters and orchestration surfaces:

```text
skills/local/
  __init__.py
  adapters.py            # LiteratureSearchAdapter, AcademicWriterAdapter
```

`skills/local/adapters.py` bridges imported skills into the `harness.ports.skill_adapter.SkillAdapter` contract. It imports from:
- `harness.ports.skill_adapter` (the port interface)
- `skills.imported.academic_writer.drafting` (the concrete skill)
- `skills.imported.literature_search.search` (the concrete skill)

### Dependency Direction (enforced)

```text
harness/  ← imports from nowhere in skills/
skills/local/ ← imports from harness/ports/ and skills/imported/
skills/imported/ ← imports from nowhere in harness/ or skills/local/
cli/ ← imports from skills/local/ and harness/
```

Verified by: `grep -rn "^from skills" harness/` → empty, `grep -rn "^from harness" skills/imported/` → empty.

## 5. Vendored External Repositories

If an external repository truly needs to be cloned for reference or assets, place it under:

```text
vendor/
```

Example:

```text
vendor/
  scientific-agent-skills/
  medsci-skills/
```

Rules:

- vendor repos are read-only reference surfaces
- runtime code must not depend on the full vendor tree unless explicitly justified
- prefer extracting only what is needed into `skills/local/` or docs

## 6. Validators

Custom validators live under:

```text
validators/
```

Recommended files:

```text
validators/
  refs.py
  citations.py
  structure.py
  reporting.py
  style.py
```

Responsibility:

- citation key consistency
- `.bib` minimum metadata requirements
- section presence and structure
- reporting checklist completeness
- strong-claim and language policy checks

## 7. Templates and Styles

Place templates here:

```text
templates/
```

Place style and citation assets here:

```text
styles/
  vale/
  csl/
```

Recommended structure:

```text
templates/
  manuscript.qmd
  references.bib
  journals/

styles/
  vale/
    paper-writer/
  csl/
    vancouver.csl
    apa.csl
```

## 8. Outputs and State

Generated artifacts live under:

```text
outputs/
```

This folder should contain both workflow state and produced artifacts.

Recommended structure:

```text
outputs/
  state.yaml
  manifest.yaml
  search/
  drafts/
  render/
  logs/
```

`outputs/state.yaml` is the minimum workflow source of truth.

## 9. Tests

Tests should mirror the system shape:

```text
tests/
  cli/
  harness/
  validators/
  integrations/
```

This keeps failures attributable to a single layer.

## Runtime Diagram

```mermaid
flowchart TD
    U[User or Agent] --> C[paper CLI]
    C --> H[Harness]
    H --> S[outputs/state.yaml]
    H --> V[Validators]
    H --> T[Tool Wrappers]
    H --> K[Skill Wrappers]

    T --> P[pandoc]
    T --> VA[vale]
    T --> B[bibtex-tidy]
    T --> R[reference-validator or refchecker]

    K --> LS[skills/imported/literature_search]
    K --> AW[skills/imported/academic_writer]
    K --> LA[skills/local/reporting-audit]
    K --> CP[skills/local/citation-pipeline]

    V --> O[outputs]
    P --> O
    VA --> O
    B --> O
    R --> O
    LS --> O
    AW --> O
    LA --> O
    CP --> O

    H --> G{All gates pass?}
    G -->|Yes| D[Deliverable Ready]
    G -->|No| F[Fail Closed]
```

## Repository Layout Diagram

```text
paper-writer/
  AGENTS.md
  README.md
  TECHNICAL_BOOTSTRAP.md
  cli/
    paper/
  harness/
  integrations/
    tools/
  validators/
  skills/
    imported/
    local/
  vendor/
  templates/
  styles/
    vale/
    csl/
  outputs/
    state.yaml
  tests/
  docs/
```

## Clone vs Install Policy

| Surface | Default policy | Destination |
|---|---|---|
| `pandoc`, `vale`, `bibtex-tidy`, validators | install | system / venv / package manager |
| imported project skills | copy or subtree-import | `skills/imported/` |
| new repo-native skills | create locally | `skills/local/` |
| external reference repos | clone only if needed | `vendor/` |

## Initial Base Build Order

1. create `cli/paper/`
2. create `harness/state_manager.py`, `harness/gates.py`, and `harness/orchestrator.py`
3. create `integrations/tools/`
4. create `validators/`
5. create `outputs/state.yaml` with the authoritative nested `gates:` schema
6. create `tests/cli/`, `tests/harness/`, `tests/validators/`
7. only after that import `skills/imported/`

## Design Constraints

- The CLI must remain thin.
- The harness owns workflow truth.
- Wrappers own external side effects.
- Skills are invoked through adapters, not ad hoc path reads from commands.
- Outputs must stay inside this repository.
- The system must fail closed if a required dependency or gate is missing.
