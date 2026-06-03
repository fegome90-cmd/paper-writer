# Controlled Validation Readiness Criteria

> [!IMPORTANT]
> **Status**: Ready for controlled validation. This repository is not certified as fully "production-ready" for autonomous drafting. It is built as an evidence-first pipeline designed for human-in-the-loop controlled execution.

> [!NOTE]
> This document distinguishes between current code behavior, tested behavior from repository test files, and operational claims that were not re-executed in this audit pass.

## Operational Prerequisites

### External Tools

| Tool | Required for | Install | Degraded Mode |
|------|-------------|---------|---------------|
| Pandoc | Render (docx) | `brew install pandoc` | ❌ No fallback — render fails |
| pdflatex | Render (pdf) | `brew install --cask mactex-no-gui` | ✅ PDF skipped, docx only |
| Vale | Style linting (vale rules) | `brew install vale` | ✅ Built-in style checks only |
| bibtex-tidy | Bibliography normalization | `npm install -g bibtex-tidy` | ✅ Built-in BibTeX validation |

`paper doctor` currently checks for `pandoc`, `pdflatex`, `vale`, `bibtex-tidy`, `pdftotext`, and `pdfinfo`, plus internal capabilities for Vale styles, CSL styles, and journal presets (`harness/services/doctor.py`).

The previous version-specific `bibtex-tidy` claim is not restated here because that behavior was not part of the evidence set used in this audit pass.

### Check Commands

```bash
# Full environment check
paper doctor

# Verify all tests pass
make verify   # or: uv run ruff check . && uv run mypy ... && uv run pytest
```

## Pipeline Gates

Current code behavior uses stages from `ManuscriptState.STAGE_ORDER`:

`bootstrap -> search -> screen -> outline -> drafting -> validating -> rendering -> verified`

The gate and stage flow implemented by `harness/domain/state.py`, `harness/services/gates.py`, and `harness/services/orchestrator.py` is:

| Gate | Set by command | Stage effect in current code |
|------|----------------|------------------------------|
| `repo_initialized` | `paper init` | advances `bootstrap -> search` |
| `search_completed` | `paper search` | advances `search -> screen` |
| `screened_evidence` | `paper screen` | advances `screen -> outline` |
| `outline_drafted` | `paper draft outline` | advances `outline -> drafting` |
| `sections_completed` | `paper draft section <name>` | advances `drafting -> validating` only when all required sections exist |
| `bib_normalized` | `paper lint bib` or `paper import bib` | contributes to rendering preconditions; `import bib` does not advance stage |
| `citations_resolved` | `paper check refs` | contributes to rendering preconditions |
| `refs_validated` | `paper check refs` | contributes to rendering preconditions |
| `style_passed` | `paper lint style` | contributes to rendering preconditions |
| `reporting_passed` | `paper audit reporting` | when all rendering preconditions are true, advances `validating -> rendering` |
| `render_passed` | `paper render` | advances `rendering -> verified` |
| `ready_for_delivery` | `paper verify` | stays in `verified`; also emits `outputs/manifest.yaml` on success |

Soft gates declared in the domain model are `citation_verified` and `ethics_passed`. `validate_ready_for_delivery()` treats them as warnings rather than blockers.

## Degraded Mode Behavior

Current code behavior in `harness/services/doctor.py` and tested wrapper behavior in `tests/cli/test_doctor_and_degraded.py` support the following distinctions:

- **bibtex-tidy missing**: Built-in BibTeX parser + `validators.bibliography` domain rules
  - Emits `degraded_mode` warning (severity: warning)
  - Checks: brace balance, entry types, required fields, DOI format, year range, duplicates

- **Vale missing**: Built-in style checks
  - Emits `degraded_mode` warning (severity: warning)
  - Checks: passive voice, strong claims, forbidden phrases, informal language
  - Does NOT check: Vale rule packs (StrongClaims.yml, etc.)

- **pdflatex missing**: PDF render skipped
  - DOCX render still available (Pandoc only)
  - Emits `degraded_mode` warning in doctor report

- **Pandoc missing**: Render fails entirely
  - No fallback for DOCX generation
  - Must install Pandoc for any render output

## Render Verification

Tested wrapper behavior in `tests/integrations/test_pandoc.py` covers the following artifact checks:

1. **Size check**: Files < 500B trigger `render_artifact_too_small` warning
2. **DOCX integrity**: Must be valid ZIP containing `word/document.xml`
3. **PDF integrity**: Size check only (PDFs are not ZIP-based)

## CI Pipeline

Repository-documented CI expectations should be treated as requiring re-verification unless re-run in the target environment.

The current documentation set and README refer to a GitHub Actions pipeline that runs:

1. Lint (ruff)
2. Type check (mypy strict)
3. Unit + integration tests (excludes E2E)
4. Install Pandoc
5. E2E smoke tests (subprocess, real I/O)

Python matrix and current CI status were not re-executed in this audit pass and therefore require re-verification before being treated as operational status.

## Journal Presets

| Preset | Template | CSL | Reference doc |
|--------|----------|-----|---------------|
| nature | `templates/journals/nature/template.qmd` | vancouver | — |

Usage: `paper init --preset nature`

## Full Pipeline E2E

Test files in `tests/cli/test_paper_cli.py`, `tests/harness/test_orchestrator.py`, and `tests/e2e/test_smoke_e2e.py` document end-to-end and near-end-to-end coverage for the following workflow:

```
init → import bib → search → screen → draft outline →
draft sections (4) → check refs → lint bib → lint style →
audit reporting → render docx → verify
```

- **Tested behavior**: stage progression is asserted in orchestrator and CLI tests, and the smoke E2E test runs the CLI via subprocess.
- **Current code behavior**: the final stage name is `verified`, not `done`.
- **Requires re-verification**: prior fixed numeric claims about total tests, artifact sizes, or current CI green status.

## Exit Criteria for Phase 5

- [x] `paper doctor` reports all tools and capabilities
- [x] Degraded mode explicit in wrapper output (code: `degraded_mode`)
- [x] Full pipeline test coverage exists across CLI, harness, integration, and E2E layers
- [x] Repository documentation describes a CI pipeline: lint + typecheck + unit + E2E
- [x] Render artifact verification (size + DOCX ZIP integrity)
- [ ] Current aggregate test counts require re-verification
- [ ] Current lint/typecheck clean status requires re-verification
- [x] README.md and docs reflect real state
