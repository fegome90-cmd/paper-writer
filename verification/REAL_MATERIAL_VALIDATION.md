# Real Material Validation

## Purpose

This phase validates `paper-writer` with **real external material** while keeping the repository clean, reproducible, and safe to share.

It exists **outside the normal CI path**. CI remains responsible for unit, integration, and smoke validation. Real-material validation is an **opt-in operational phase** for higher-confidence manual and semi-automated checks.

## Rules

1. Do **not** commit PDFs, downloaded papers, private bibliographies, or rendered artifacts generated from real material.
2. Store local inputs only under `verification/local-data/`.
3. Store temporary run outputs only under `verification/reports/` or a temp directory.
4. Track only:
   - documentation
   - manifest templates
   - runner conventions
   - acceptance criteria
5. If a case contains private or licensed material, keep it local and gitignored.

## Phase Position

- **Phase 5** proved the platform is production-ready at the engineering level.
- **Phase 6** is for **evidence with real material**, not for core architecture.

This phase should not block normal development unless the team explicitly promotes a real-material case into a release gate.

## Directory Contract

```text
verification/
  REAL_MATERIAL_VALIDATION.md
  manifest.example.yaml
  local-data/
    .gitkeep
    *.local.yaml         # optional local manifests, gitignored
    *.pdf                # local-only source files, gitignored
  reports/
    .gitkeep
```

## Execution Model

A validation case is driven by a manifest. The manifest defines:
- case id
- source material path
- bibliography source
- preset
- commands to run
- expected degraded-mode allowances
- required manual review points

## Suggested Flow

1. `paper doctor`
2. `paper init --preset <preset>`
3. import a real `.bib` if available
4. run the drafting / validation / render commands required by the case
5. review produced artifacts
6. record a short verdict (`pass`, `pass_with_degraded_mode`, `manual_review_required`, `fail`)

## Verdict Levels

### `pass`
All automated checks passed and manual review found no blocking issue.

### `pass_with_degraded_mode`
The case completed, but with an allowed degraded dependency state (for example, no Vale binary or no LaTeX for PDF).

### `manual_review_required`
Automation completed, but citation styling, formatting, figures, or narrative quality still require human review before acceptance.

### `fail`
The case did not satisfy the operational acceptance criteria.

## Manual Review Checklist

At minimum, review:
- bibliography imported correctly
- inline citations resolved to real keys
- CSL output looks correct
- DOCX opens correctly in Word/LibreOffice
- section structure is preserved
- no fabricated references appear
- degraded-mode warnings are acceptable for the purpose of the run

## Case 01 — Attention Is All You Need

Suggested local source file:
- `/Users/felipe_gonzalez/Downloads/attention-is-all-you-need.pdf`

Why this case is useful:
- public, stable, widely cited paper
- good fit for bibliography, citation, and render validation
- no need to commit the PDF into the repository

## What This Phase Is Not

- not a replacement for CI
- not a place to commit third-party PDFs
- not a guarantee of publication-quality writing
- not a license to bypass the harness or gate system

## Acceptance for the Phase Itself

This phase is considered established when:
- the repository contains this documentation and manifest template
- local material can be referenced without being committed
- at least one real-material case can be described and executed reproducibly
- the verdict taxonomy is explicit
