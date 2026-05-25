# paper-writer

A dedicated repository for automated scientific search, drafting, validation, and rendering.

## Current Status

Phases 1–3 are complete and verified.

Verification evidence:

- `pytest` — 216 passing
- `ruff check .` — clean
- `mypy strict` — 0 issues in 65 source files

The repository has:

- a thin `paper` CLI (`cli/paper/main.py`)
- a hexagonal harness (`state_manager`, `gates`, `orchestrator`, `assembler`)
- domain validators (`validators/`) — pure functions, no I/O
- tool wrappers (`integrations/tools/`) — Pandoc render, bibtex-tidy, vale, refs validation
- imported skills with provenance-tracked adapters:
  - `literature-search` — real scoring engine (dedup, tier classification, citation verify)
  - `academic-writer` — section structures from manifest derived from SKILL.md
- fail-closed gate system — no gate passes without evidence
- assembled draft-to-render flow using `outputs/drafts/manuscript.md`

## Phase Status

### Completed

- **Phase 1** — Repository Base (hexagonal harness, CLI, state machine, gates)
- **Phase 2** — Harness and Verification (domain validators, Pandoc render, assembler)
- **Phase 3** — Domain Skill Integration (real imports, manifest-driven adapters)

### Next

- **Phase 4** — Editorial Gates and Hardening

Immediate Phase 4 focus:

- Vale rules for style gate
- `.bib` normalization step
- Reference validation wiring
- Zotero/Better BibTeX integration
- Journal presets
- Multi-output render (docx/pdf)

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
