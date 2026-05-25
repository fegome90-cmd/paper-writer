# paper-writer

A dedicated repository for automated scientific search, drafting, validation, and rendering.

## Current Status

Phases 1–4 are complete and verified.

Verification evidence:

- `pytest` — 265 passing
- `ruff check .` — clean
- `mypy strict` — 0 issues in 69 source files

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

## Phase Status

### Completed

- **Phase 1** — Repository Base (hexagonal harness, CLI, state machine, gates)
- **Phase 2** — Harness and Verification (domain validators, Pandoc render, assembler)
- **Phase 3** — Domain Skill Integration (real imports, manifest-driven adapters)
- **Phase 4** — Editorial Gates and Hardening (style rules, bib normalization, ref validation, presets, multi-output render, Zotero)

### Next

- **Phase 5** — Production Readiness

  Focus areas:
  - CLI command wiring for all validators
  - Vale configuration auto-detection
  - Full end-to-end integration tests
  - CI pipeline (GitHub Actions)
  - Documentation finalization

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

## Principle

The system is not an autonomous paper writer.
It is an agent constrained by editorial CI.
