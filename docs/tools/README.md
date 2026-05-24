# Tooling Reference

This folder defines how each tool in `paper-writer` is expected to be used.

## Quick path

1. Use `/Users/felipe_gonzalez/Developer/paper-writer/docs/REPO_ARCHITECTURE.md` to understand where each tool fits.
2. Use one document per tool before implementing wrappers or commands.
3. Keep the CLI thin: operational rules belong in the harness and integrations.

## Tool set

- `paper-cli.md` — internal command surface and responsibilities
- `pandoc.md` — render backend and citation processing
- `vale.md` — scientific style linting
- `bibtex-tidy.md` — `.bib` hygiene and formatting
- `reference-validator.md` — primary reference metadata validation
- `refchecker.md` — secondary / fallback reference checking

## Rule

These docs define **usage contracts**, not implementation code.
The wrappers under `integrations/tools/` must conform to them.
