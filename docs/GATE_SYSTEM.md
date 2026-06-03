# paper-writer - Gate System

Defines the workflow gates that block or allow stage progression.

## Quick path

1. Gate helpers live in `harness/services/gates.py`.
2. Required and soft gate names are declared in `harness/domain/state.py` via `ManuscriptState.REQUIRED_GATES` and `ManuscriptState.SOFT_GATES`.
3. The orchestrator evaluates gates after command execution and persists each evaluated gate as `True` for `pass`/`warn`, `False` for `fail`.

## Gate Result Contract

Observed shape from `GateResult` in `harness/services/gates.py`:

```yaml
gate: refs_validated
status: fail           # pass | warn | fail
blockers:
  - bibliography entries missing required identifiers
warnings: []
artifacts:
  - templates/references.bib
```

Required fields:
- `gate`
- `status`
- `blockers`
- `warnings`
- `artifacts`

Observed status semantics in `run_gate()` and `validate_validator_gate()`:
- `pass`: no blockers and no warnings
- `warn`: no blockers, but at least one warning
- `fail`: at least one blocker

Important nuance:
- `warn` is not a universal pipeline failure.
- In `Orchestrator.execute()`, an evaluated gate is persisted as satisfied when its status is `pass` or `warn`.
- Command-level failure still depends on command context, collected blockers, and `failure_policy`.

## Required Gates

These names are enforced by `ManuscriptState.REQUIRED_GATES`.

| Gate | Meaning grounded in code | Typical command / evaluation surface |
|---|---|---|
| `repo_initialized` | Required scaffold paths exist | `paper init` -> `validate_repo_initialized()` |
| `search_completed` | `outputs/search/search_plan.json` and `outputs/search/raw_results.json` exist | `paper search` -> `validate_search_completed()` |
| `screened_evidence` | `outputs/search/screened_evidence.json` exists | `paper screen` -> `validate_screened_evidence()` |
| `outline_drafted` | `outputs/drafts/outline.md` exists | `paper draft outline` -> `validate_outline_drafted()` |
| `sections_completed` | Required draft section files exist | `paper draft section` -> `validate_sections_completed()` |
| `bib_normalized` | Bibliography validation/import path succeeded; after `import_bib`, file existence is also checked | `lint_bib` wrapper; `import_bib` + `validate_bib_normalized()` |
| `citations_resolved` | Citation-resolution wrapper result for `check_refs` was accepted by gate evaluation | `check_refs` wrapper with gate override |
| `refs_validated` | Reference-metadata wrapper result for `check_refs_metadata` was accepted by gate evaluation | `check_refs_metadata` wrapper with gate override |
| `style_passed` | Style wrapper result was accepted by gate evaluation | `lint_style` wrapper |
| `reporting_passed` | Reporting wrapper result was accepted by gate evaluation | `audit_reporting` wrapper |
| `render_passed` | Render wrapper result was accepted, and if pass/warn then at least one render artifact exists | `render` wrapper + `validate_render_passed()` |
| `ready_for_delivery` | All required gates except itself are true; soft gates may still warn | `paper verify` -> `validate_ready_for_delivery()` |

Notes on interpretation:
- The gate names are real and enforced.
- Several gate meanings above are broader than a single helper because the orchestrator wires some of them through wrappers rather than pure artifact checks.
- This document does not claim that the semantic content of a gate is fully proven beyond what the helper/wrapper wiring actually checks.

Render policy for `render_passed`:
- `validate_render_passed()` only proves that at least one of `outputs/render/manuscript.docx` or `outputs/render/manuscript.pdf` exists.
- Whether render returns `pass`, `warn`, or `fail` before that artifact check depends on the registered render wrapper.
- Tests confirm `warn` can still count as success for stage transition.
- Mixed-format semantics are therefore partly wrapper behavior, not fully specified by the gate helper alone.

## Soft Gates

Soft gates are declared in `ManuscriptState.SOFT_GATES`.

| Gate | Observed behavior | Typical command / evaluation surface |
|---|---|---|
| `citation_verified` | Warning-only if absent/false during `validate_ready_for_delivery()`; dedicated soft helper also exists | soft gate path in `harness/services/gates.py` |
| `ethics_passed` | Warning-only if absent/false during `validate_ready_for_delivery()`; dedicated soft helper also exists | soft gate path in `harness/services/gates.py` |

Important nuance:
- The soft-gate names and warning behavior are real.
- The current orchestrator wiring shown in `harness/services/orchestrator.py` uses them through `validate_ready_for_delivery()` during `verify`.
- This doc does not assert a standalone orchestrator command currently runs `validate_citation_verify_gate()` or `validate_ethics_passed_gate()` directly.

## Fail-Closed Rules

Observed fail-closed behavior:
- Missing required files/directories in artifact-based gate checks produce `fail`.
- Missing wrapper/validator result input to `validate_validator_gate()` produces `fail`.
- `error` findings in wrapper-derived validator output force `fail`.
- `warning` findings can produce `warn` when blockers are absent.
- `paper verify` requires `render_passed=True` in orchestrator preconditions.
- `validate_ready_for_delivery()` treats soft gates as warnings, not blockers.

Avoid over-reading this section:
- There is no single universal warning/fail policy independent of command context.
- `draft_section` is a special case in the orchestrator: incomplete section state can leave gate blockers without making the command fail.

## Evaluation Order

Typical evaluation flow, assembled from `Orchestrator.execute()` and gate helpers:

1. Load and validate state
2. Validate command preconditions
3. Execute the command action
4. Run gate verification for that command
5. Persist gate booleans
6. Decide stage transition

This is a description of the current orchestrator flow, not an abstract contract that every future gate implementation must follow.

## Reset Rules

When a downstream-sensitive artifact changes, dependent gates reset.

Observed minimum reset policy from `ManuscriptState.reset_downstream_gates()`:
- editing draft sections resets `citations_resolved`, `style_passed`, `reporting_passed`, `render_passed`, `ready_for_delivery`
- editing bibliography resets `bib_normalized`, `refs_validated`, `render_passed`, `ready_for_delivery`

## Rules

- Gates are the authority for stage advancement.
- Gate helpers do not invoke external tools themselves; wrapper execution is initiated by the orchestrator.
- No command may advance stage if the orchestrator does not treat the relevant evaluated gates as satisfied.

## Audit Checklist

- [ ] Required gates listed here match `ManuscriptState.REQUIRED_GATES`
- [ ] Soft gates listed here match `ManuscriptState.SOFT_GATES`
- [ ] Claims about blocking behavior are limited to what code/tests currently show
