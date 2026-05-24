# paper-writer - Testing Strategy

Defines how `paper-writer` will be verified during the documentation-first phase and after implementation begins.

## Quick path

1. Current phase uses document/file audits because no test runner exists yet.
2. Implementation phase should add unit and integration tests around harness surfaces.
3. Verification claims must match the current maturity of the repository.

## Current Reality

At this stage, the repository has:
- documentation
- planned Python modules
- no runnable harness code yet
- no test command configured yet

Therefore, current verification is:
- file existence checks
- consistency audits
- schema drift checks
- cross-document contract review

## Future Test Layers

| Layer | Target |
|---|---|
| Unit | `state_manager.py`, gate evaluation helpers, adapter normalization |
| Integration | orchestrator + state manager + gates |
| Contract | docs-to-implementation shape consistency |
| End-to-end | `paper init`, `paper verify`, later `paper render` |

## Initial Priorities

1. state schema validation tests
2. transition-rule tests
3. gate reset tests
4. adapter result normalization tests
5. manifest emission tests

## Rules

- Do not claim runtime verification for modules that do not exist yet.
- Prefer contract tests early, executable workflow tests once the harness exists.
- Verification reports must distinguish document audit evidence from runnable test evidence.

## Audit Checklist

- [ ] Current docs do not overclaim executable coverage.
- [ ] Future tests map to real implementation surfaces.
- [ ] Contract tests are planned for state, gates, adapters, and manifest.
