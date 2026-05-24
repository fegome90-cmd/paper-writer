# paper-writer

A dedicated repository for automated scientific search, drafting, validation, and rendering.

## Current Status

This repository starts with a minimal constitutional configuration.

See:

- `TECHNICAL_BOOTSTRAP.md` — what to import, what to clone, and how to start
- `AGENTS.md` — minimum operational rules for the agent
- `docs/REPO_ARCHITECTURE.md` — repository layout, wrapper boundaries, and runtime diagram
- `docs/HARNESS_AND_STATE_MACHINE.md` — authoritative workflow stages, gates, and state schema
- `docs/ORCHESTRATOR_SPEC.md` — orchestrator contract, execution model, and failure policies
- `docs/tools/README.md` — per-tool usage contracts and integration expectations
- `docs/VALIDATOR_CONTRACTS.md` — normalized validator inputs, outputs, severities, and gate impacts
- `docs/GATE_SYSTEM.md` — gate catalog, fail-closed rules, and reset semantics
- `docs/STATE_MANAGER_SPEC.md` — state persistence, schema validation, and transition rules
- `docs/MANIFEST_SPEC.md` — delivery manifest schema and emission contract
- `docs/SKILL_ADAPTERS_SPEC.md` — normalized adapters for imported and local skills
- `docs/TESTING_STRATEGY.md` — documentation-phase audits and future executable tests
- `docs/ENVIRONMENT_AND_INSTALL.md` — MVP dependency policy and installation staging

## Intended First Scope

Build the base first:

- initialize git and repository structure
- define a small `paper` CLI
- create `harness/`, `validators/`, and `outputs/state.yaml`
- add verification gates and tests

Only after the base works:

- import `literature-search`
- import `academic-writer`
- integrate bibliography, validation, and render workflows

## Principle

The system is not an autonomous paper writer.
The system is an agent constrained by editorial CI.
