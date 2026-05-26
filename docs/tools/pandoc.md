# Pandoc

Pandoc is the phase-1 render backend.
It is the first real external tool in the stack because it already exists on the machine.

## Quick path

1. Prepare a manuscript source (`.md` or `.qmd`).
2. Render through the Pandoc wrapper under `integrations/tools/pandoc.py`.
3. Save outputs under `outputs/render/`.

## Role

| Topic | Decision |
|---|---|
| Purpose | Render academic documents and process citations |
| Integration | `integrations/tools/pandoc.py` |
| Current status | Installed locally |
| Phase | Phase 1 |

## How it will be used

- Render manuscript drafts to `.docx` first.
- Later render to `.pdf` once the style pipeline is stable.
- Use bibliography files as source of truth for references.
- Do not allow hand-written bibliography sections.

## Inputs

- manuscript source
- `references.bib`
- optional CSL file under `styles/csl/`

## Outputs

- rendered documents under `outputs/render/`
- normalized wrapper result for success/failure reporting

## Rules

- Pandoc is called through the wrapper, never directly from the CLI.
- Missing bibliography or broken citation keys should fail the render gate.
- If Quarto is added later, Pandoc remains the lowest-level backend.
- At least one requested output format must succeed (`render_passed`).
- Mixed requests can return warning on partial success (example: docx OK, pdf fail).
- If all requested formats fail, render status is failure.
- If optional paths (`--csl`, `--reference-doc`) are provided but missing, the wrapper emits warnings (no silent ignore).

## Next step

Create the wrapper API first, then decide the exact command templates.
