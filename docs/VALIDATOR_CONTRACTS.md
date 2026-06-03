# paper-writer - Validator Contracts

Defines the canonical contract for all validators used by the harness.

## Quick path

1. Validators receive normalized inputs from the orchestrator.
2. Validators return structured findings, never raw tool text as business output.
3. Gates consume validator results to decide pass/warn/fail outcomes.

## Scope

This contract applies to:
- `validators/refs.py`
- `validators/citations.py`
- `validators/structure.py`
- `validators/reporting.py`
- `validators/style.py`
- `validators/citation_verify.py` — Crossref + Semantic Scholar citation verification
- `validators/claim_alignment.py` — claim-reference alignment
- `validators/ethics.py` — AI disclosure compliance
- `validators/writing_quality.py` — AI-typical writing detection
- any future validator integrated through the harness

## Canonical Input Contract

Conceptual shape:

```yaml
validator: refs
stage: validating
artifacts:
  manuscript_files:
    - outputs/drafts/introduction.md
  bibliography: templates/references.bib
context:
  state_file: outputs/state.yaml
  command: paper check refs
```

Required input fields:
- `validator`
- `stage`
- `artifacts`

## Canonical Output Contract

Conceptual shape:

```yaml
validator: refs
status: fail          # pass | warn | fail
summary: DOI missing in 2 entries
findings:
  - code: missing_identifier
    severity: error   # info | warning | error
    message: Entry lacks DOI, PMID, PMCID, arXiv ID, or URL
    artifact: templates/references.bib
    location: smith2024voice
    gate_effects:
      - refs_validated
artifacts_checked:
  - templates/references.bib
```

Required output fields:
- `validator`
- `status`
- `summary`
- `findings`
- `artifacts_checked`

## Severity Rules

| Severity | Meaning | Gate Impact |
|---|---|---|
| `info` | Useful note, no blocking effect | none by default |
| `warning` | Review needed, may block only if gate policy says so | gate-specific |
| `error` | Contract violation | blocks the affected gate |

## Gate Mapping

| Validator | Primary Gates |
|---|---|
| `refs` | `refs_validated` |
| `citations` | `citations_resolved` |
| `style` | `style_passed` |
| `reporting` | `reporting_passed` |
| `structure` | `reporting_passed` or future `structure_passed` |
| `citation_verify` | `citation_verified` (soft) |
| `claim_alignment` | `refs_validated` (extends existing) |
| `ethics` | `ethics_passed` (soft) |
| `writing_quality` | `style_passed` (extends existing) |

## Rules

- Validators do not mutate `outputs/state.yaml` directly.
- Validators do not emit final CLI copy.
- Validators do not parse raw subprocess text as final business output; wrappers normalize first.
- A validator may report multiple findings under `continue_on_error` collection.
- The harness decides final gate mutation from validator output.

## Audit Checklist

- [ ] Every validator has normalized inputs.
- [ ] Every validator returns `status`, `summary`, and `findings`.
- [ ] Gate effects are explicit per finding or validator class.
- [ ] No validator writes workflow state directly.
