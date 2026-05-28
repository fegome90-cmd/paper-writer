# paper-writer

A dedicated repository for automated scientific search, drafting, validation, and rendering.

## Current Status

The system is verified and ready for controlled validation.

Verification evidence:

- `pytest` — 435 passing (unit, integration, E2E)
- `ruff check .` — clean
- `mypy strict` — 0 issues in 82 source files
- Full pipeline E2E verified: `init → import → search → screen → draft → validate → render → verify`
- Pandoc produces real DOCX (12KB+, Word 2007+)

The repository has:

- a thin `paper` CLI (`cli/paper/main.py`)
- a hexagonal harness (`state_manager`, `gates`, `orchestrator`, `assembler`)
- domain validators (`validators/`) — pure functions, no I/O
  - `refs.py` — metadata completeness (year, DOI/URL)
  - `citations.py` — key consistency
  - `style.py` — passive voice, strong claims, forbidden phrases, informal language
  - `bibliography.py` — entry type, required fields, DOI format, year range, duplicates
  - `reporting.py` — study design, sample size, limitations
  - `structure.py` — required section presence
  - `preset.py` — journal preset schema validation
- tool wrappers (`integrations/tools/`) — Pandoc, bibtex-tidy, Vale, refs validation, Zotero import
- Vale style packs (`styles/vale/paper-writer/`) — strong claims, informal language, forbidden phrases, unbacked claims
- CSL citation styles (`styles/csl/`) — Vancouver, APA 7th
- journal presets (`templates/journals/nature/`) — template, preset.yaml, seeded references
- imported skills with provenance-tracked adapters:
  - `literature-search` — real scoring engine (dedup, tier classification, citation verify)
  - `academic-writer` — section structures from manifest derived from SKILL.md
- fail-closed gate system — no gate passes without evidence
- multi-output render (docx, pdf) with CSL and reference-doc support
- optional Zotero/Better BibTeX ingestion surface
- `paper doctor` — environment check with explicit degraded-mode reporting
- CI pipeline (`.github/workflows/ci.yml`) — lint, typecheck, unit + E2E tests

## Phase Status

### Completed

- **Phase 1** — Repository Base (hexagonal harness, CLI, state machine, gates)
- **Phase 2** — Harness and Verification (domain validators, Pandoc render, assembler)
- **Phase 3** — Domain Skill Integration (real imports, manifest-driven adapters)
- **Phase 4** — Editorial Gates and Hardening (style rules, bib normalization, ref validation, presets, multi-output render, Zotero)
- **Phase 5** — Controlled Validation Readiness (E2E smoke, CI, degraded mode, render verification, operational docs)

### Optional Next Phase

- **Phase 6** — Real Material Validation (opt-in, local-only, non-CI)
  - uses real source documents without committing them to the repository
  - runs from `verification/` manifests and local gitignored inputs
  - adds manual-review evidence on top of automated gates

## Quick Start

```bash
# Install dependencies
uv sync --dev

# Initialize a project
paper init

# Import bibliography
paper import bib references.bib

# Run pipeline
paper search
paper screen
paper draft outline
paper draft section introduction
paper draft section methods
paper draft section results
paper draft section discussion
paper check refs
paper lint bib
paper lint style
paper audit reporting
paper render --format docx

# Check environment
paper doctor

# Verify all
make verify
```

## Documentation

| Document | Purpose |
|----------|---------|
| `TECHNICAL_BOOTSTRAP.md` | Import plan, construction order, phase status |
| `AGENTS.md` | Operational rules for the agent |
| `docs/REPO_ARCHITECTURE.md` | Repository layout, dependency direction, runtime diagram |
| `docs/HARNESS_AND_STATE_MACHINE.md` | Workflow stages, gates, state schema |
| `docs/ORCHESTRATOR_SPEC.md` | Orchestrator contract, failure policies |
| `docs/SKILL_ADAPTERS_SPEC.md` | Adapter provenance, command mapping, wiring |
| `docs/GATE_SYSTEM.md` | Gate catalog, fail-closed rules, reset semantics |
| `docs/STATE_MANAGER_SPEC.md` | State persistence, schema validation |
| `docs/MANIFEST_SPEC.md` | Delivery manifest schema |
| `docs/VALIDATOR_CONTRACTS.md` | Validator inputs, outputs, severities |
| `docs/TESTING_STRATEGY.md` | Testing approach and coverage |
| `docs/PRODUCTION_READINESS.md` | Operational criteria, degraded mode, CI |
| `verification/REAL_MATERIAL_VALIDATION.md` | Local-only validation with real source material |

## Principle

The system is not an autonomous paper writer.
It is an agent constrained by editorial CI.
