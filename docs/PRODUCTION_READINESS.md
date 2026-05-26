# Production Readiness Criteria

## Operational Prerequisites

### External Tools

| Tool | Required for | Install | Degraded Mode |
|------|-------------|---------|---------------|
| Pandoc | Render (docx) | `brew install pandoc` | ❌ No fallback — render fails |
| pdflatex | Render (pdf) | `brew install --cask mactex-no-gui` | ✅ PDF skipped, docx only |
| Vale | Style linting (vale rules) | `brew install vale` | ✅ Built-in style checks only |
| bibtex-tidy | Bibliography normalization | `npm install -g bibtex-tidy` | ✅ Built-in BibTeX validation |

> **Version policy**: minimum-version check (>= 1.11.0). Any semver-compatible version at or above the minimum is accepted, regardless of source (local, env, global).

### Check Commands

```bash
# Full environment check
paper doctor

# Verify all tests pass
make verify   # or: uv run ruff check . && uv run mypy ... && uv run pytest
```

## Pipeline Gates

Each gate must pass before the next stage unlocks:

| Gate | Stage Before | Stage After | Validator |
|------|-------------|-------------|-----------|
| `repo_initialized` | bootstrap | search | FilesystemActionRunner.init |
| `bib_normalized` | search | screen | BibliographyNormalizer |
| `citations_resolved` | screen | drafting | CitationsValidator |
| `refs_validated` | drafting | validating | RefsMetadataValidator |
| `style_passed` | validating | validating | StyleLinter |
| `reporting_passed` | validating | rendering | ReportingAuditor |
| `render_passed` | rendering | done | PandocRenderer |

## Degraded Mode Behavior

When external tools are missing, the pipeline continues with built-in fallbacks:

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

After Pandoc produces output, artifacts are verified:

1. **Size check**: Files < 500B trigger `render_artifact_too_small` warning
2. **DOCX integrity**: Must be valid ZIP containing `word/document.xml`
3. **PDF integrity**: Size check only (PDFs are not ZIP-based)

## CI Pipeline

GitHub Actions CI runs on every push/PR to main:

1. Lint (ruff)
2. Type check (mypy strict)
3. Unit + integration tests (excludes E2E)
4. Install Pandoc
5. E2E smoke tests (subprocess, real I/O)

Matrix: Python 3.10, 3.11, 3.12, 3.13 on Ubuntu latest.

## Journal Presets

| Preset | Template | CSL | Reference doc |
|--------|----------|-----|---------------|
| nature | `templates/journals/nature/template.qmd` | vancouver | — |

Usage: `paper init --preset nature`

## Full Pipeline E2E

The complete pipeline has been verified end-to-end:

```
init → import bib → search → screen → draft outline →
draft sections (4) → check refs → lint bib → lint style →
audit reporting → render docx → verify
```

**Verified**: Stage transitions `bootstrap → search → screen → outline → drafting → validating → rendering → verified`.
All 12 gates True. Pandoc produces real DOCX (12KB+, Word 2007+).

E2E tests run as subprocess with real I/O — not mocked.

## Exit Criteria for Phase 5

- [x] `paper doctor` reports all tools and capabilities
- [x] Degraded mode explicit in wrapper output (code: `degraded_mode`)
- [x] Full E2E pipeline: init → render → verify (340 tests, 0 failed, 0 skipped)
- [x] CI pipeline: lint + typecheck + unit + E2E
- [x] Render artifact verification (size + DOCX ZIP integrity)
- [x] 340 tests passing (unit + integration + E2E + doctor)
- [x] mypy strict clean (75 source files), ruff clean
- [x] README.md and docs reflect real state
