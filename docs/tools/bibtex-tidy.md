# bibtex-tidy

`bibtex-tidy` is the bibliography hygiene tool.
It keeps `references.bib` machine-friendly and reviewable.

## Quick path

1. Maintain one `references.bib` file as source of truth.
2. Run `bibtex-tidy` through `integrations/tools/bibtex_tidy.py`.
3. Save the cleaned result before render or verification.

## Role

| Topic | Decision |
|---|---|
| Purpose | Normalize, sort, and clean BibTeX entries |
| Integration | `integrations/tools/bibtex_tidy.py` |
| Current status | Planned, not installed yet |
| Phase | Phase 2 |

## How it will be used

- sort bibliography entries consistently
- detect duplicate entries
- normalize formatting before validation and render

## Inputs

- `references.bib`

## Outputs

- cleaned `references.bib`
- duplicate/formatting findings for the harness

## Rules

- The agent must not maintain references manually in the manuscript body.
- Bibliography cleanup happens before reference validation and render.
- Any destructive rewrite should be explicit and reproducible through the wrapper.

## Next step

Define whether the wrapper runs in check-only mode, fix mode, or both.
