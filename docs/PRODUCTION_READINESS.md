# Controlled Validation Readiness Criteria

> [!IMPORTANT]
> **Status**: Repository evidence supports controlled validation workflows. Live operational status still requires re-verification in the target environment.

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

The domain model also declares `citation_verified` and `ethics_passed` as soft gates. In `validate_ready_for_delivery()`, missing soft gates produce warnings rather than blockers.

## API Client Resiliency

The `clients/` package (Crossref, Semantic Scholar, Trifecta) implements defense-in-depth error handling:

| Mechanism | Behavior | Evidence |
|-----------|----------|----------|
| Retry with backoff | HTTP 429 → 2s, 4s, 8s exponential backoff, max 3 retries | `clients/_retry.py`, `tests/test_clients/test_retry.py` |
| Outage latch | Semantic Scholar 5xx → 10-minute latch, skips further requests | `clients/semantic_scholar.py`, `tests/test_clients/test_resiliency.py` |
| Error model | All public methods return `found=False` on error — never raise | `tests/test_clients/test_crossref.py`, `tests/test_clients/test_semantic_scholar.py` |
| JSON/Unicode safety | `_get()` catches `JSONDecodeError`/`UnicodeDecodeError` before they reach callers | `clients/crossref.py`, `clients/semantic_scholar.py` |
| URL safety | DOI URLs are percent-encoded (`urllib.parse.quote`) | `tests/test_clients/test_crossref.py` |
| Logging discipline | All `except Exception:` blocks log before returning — no silent swallowing | Code review verified |
| DI for testability | Semantic Scholar accepts `_sleep`/`_clock` constructor args | `tests/test_clients/test_semantic_scholar.py` |

**Test coverage**: 92 tests across `tests/test_clients/` and `tests/clients/`, all using DI (no monkeypatching).

## Degraded Mode Behavior

Current code behavior in `harness/services/doctor.py` and tested wrapper behavior in `tests/cli/test_doctor_and_degraded.py` support the following distinctions:

- **`bibtex-tidy` missing**:
  - `paper doctor` reports the tool as missing and degraded mode active.
  - Wrapper tests confirm a `degraded_mode` finding is emitted instead of hard-crashing.

- **`vale` missing**:
  - `paper doctor` reports the tool as missing and degraded mode active.
  - Wrapper tests confirm a `degraded_mode` finding is emitted instead of hard-crashing.

- **`pdflatex` missing**:
  - `paper doctor` reports degraded mode.
  - Render tests cover mixed outcomes where DOCX can succeed while PDF fails, yielding warnings rather than an all-or-nothing crash.

- **`pandoc` missing**:
  - Render cannot proceed; wrapper tests expect `ToolNotAvailableError` when Pandoc is absent.
  - No fallback renderer is evidenced in the audited files.

## Render Verification

The audited evidence supports these render-verification claims:

1. `tests/integrations/test_pandoc.py` verifies that tiny mocked render artifacts produce `render_artifact_*` findings.
2. `tests/e2e/test_smoke_e2e.py` verifies that a real DOCX artifact, when Pandoc is available, is a ZIP containing `word/document.xml`.
3. This audit does not restate broader PDF integrity guarantees beyond the wrapper and E2E behavior exercised in those tests.

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

The audited CLI and E2E tests cover `paper init --preset nature` as the currently evidenced preset flow.

## Full Pipeline E2E

Test files in `tests/cli/test_paper_cli.py`, `tests/harness/test_orchestrator.py`, and `tests/e2e/test_smoke_e2e.py` document end-to-end and near-end-to-end coverage for the core workflow from initialization through render and verify.

```
init → import/search/screen → draft outline/sections →
validation commands → render → verify
```

- **Tested behavior**: stage progression is asserted in orchestrator and CLI tests, and the smoke E2E test runs the CLI via subprocess.
- **Current code behavior**: the final stage name is `rendered`; `paper verify` keeps the stage at `rendered` and sets the final delivery gate `ready_for_delivery`.
- **Requires re-verification**: prior fixed numeric claims about total tests, artifact sizes, or current CI green status.

## Exit Criteria for Phase 5

- [x] `paper doctor` reports all tools and capabilities
- [x] Degraded mode explicit in wrapper output (code: `degraded_mode`)
- [x] Full pipeline test coverage exists across CLI, harness, integration, and E2E layers
- [x] Repository documentation describes a CI pipeline: lint + typecheck + unit + E2E
- [x] Render artifact verification (size + DOCX ZIP integrity)
- [ ] Current aggregate test counts require re-verification
- [ ] Current lint/typecheck clean status requires re-verification
- [x] This document now limits strong claims to code, tests, and workflow files audited here
