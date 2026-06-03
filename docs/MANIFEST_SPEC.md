# paper-writer - Manifest Specification

Defines the contract for `outputs/manifest.yaml`.

## Quick path

1. The manifest is emitted only after final verification succeeds.
2. It summarizes delivery readiness and provenance.
3. It is a delivery artifact, not a working-state file.

## Emission Rule

`outputs/manifest.yaml` is emitted by the orchestrator during `paper verify` only when:
- `render_passed: true`
- final gate checks succeed
- `ready_for_delivery` is set to `true`

## Canonical Shape

```yaml
schema_version: 1.1
project: paper-writer
status: ready_for_delivery
generated_at: 2026-05-24T14:00:00Z
stage: rendered
gate_snapshot:
  repo_initialized: true
  search_completed: true
  screened_evidence: true
  outline_drafted: true
  sections_completed: true
  bib_normalized: true
  citations_resolved: true
  refs_validated: true
  style_passed: true
  reporting_passed: true
  render_passed: true
  ready_for_delivery: true
artifacts:
  manuscript:
    - outputs/render/manuscript.docx
    - outputs/render/manuscript.pdf
  bibliography: templates/references.bib
verdict: pass
notes: []
```

## Required Fields

- `schema_version`
- `project`
- `status`
- `generated_at`
- `stage`
- `gate_snapshot`
- `artifacts`
- `verdict`

## Rules

- The manifest does not replace `outputs/state.yaml`.
- The manifest is immutable audit output for a completed verification point.
- If verification fails, the manifest must not claim delivery readiness.
- A new successful verification may replace a previous manifest with a new snapshot.
- Schema 1.1: stage field changed from `verified` to `rendered`. Legacy manifests with `stage: verified` are from schema 1.0.

## Audit Checklist

- [ ] Manifest is emitted only from `paper verify`.
- [ ] Gate snapshot matches the state at verification time.
- [ ] Deliverable artifact paths are explicit.
- [ ] Failed verification does not emit a misleading ready manifest.
