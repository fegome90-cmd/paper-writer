# paper-writer - Testing Strategy

Defines how `paper-writer` is verified across all layers of the system.

## Quick path

1. Tests run via `uv run pytest` (or `make test`).
2. CI enforces `ruff check`, `mypy strict`, and `pytest` on every push.
3. E2E tests run real subprocess I/O — not mocked.
4. Verification claims match the current maturity of the repository.

## Current State

**435 tests passing** across 5 layers:

| Metric | Value |
|--------|-------|
| Total tests | 435 |
| Source files (mypy strict) | 82 |
| Linter | ruff clean |
| Type checker | mypy strict, 0 issues |
| CI | GitHub Actions (lint + typecheck + unit + E2E) |

## Test Layers

### Unit Tests

Target domain logic in isolation — no I/O, no subprocesses.

| Module | What is tested | Location |
|--------|---------------|----------|
| `validators/refs.py` | DOI/URL metadata completeness | `tests/unit/validators/` |
| `validators/citations.py` | Citation key consistency | `tests/unit/validators/` |
| `validators/style.py` | Passive voice, strong claims, forbidden phrases | `tests/unit/validators/` |
| `validators/bibliography.py` | Entry types, required fields, DOI format, year range, duplicates | `tests/unit/validators/` |
| `validators/reporting.py` | Study design, sample size, limitations | `tests/unit/validators/` |
| `validators/structure.py` | Required section presence | `tests/unit/validators/` |
| `validators/preset.py` | Journal preset schema validation | `tests/unit/validators/` |
| `harness/services/state_manager.py` | State transitions, schema validation, gate reset | `tests/unit/harness/` |
| `harness/services/gates.py` | Gate evaluation, precondition checks | `tests/unit/harness/` |
| `skills/imported/literature_search/scoring.py` | Scoring engine, dedup, tier classification (56 tests) | `tests/skills/` |
| `skills/local/adapters.py` | Adapter normalization, SkillResult contract | `tests/skills/` |

### Integration Tests

Target component interaction — real adapters, real filesystem on `tmp_path`.

| Surface | What is tested | Location |
|---------|---------------|----------|
| Orchestrator + state manager + gates | Full stage transition flow | `tests/integration/` |
| FilesystemActionRunner + skill adapters | Search/screen/draft with real scoring | `tests/integration/` |
| Tool wrappers (Pandoc, bibtex-tidy, Vale) | Real tool invocation on temp dirs | `tests/integration/` |
| Zotero import | .bib file ingestion | `tests/integration/` |

### Contract Tests

Verify architectural invariants — dependency direction, port compliance.

| Invariant | Verification |
|-----------|-------------|
| `harness/` never imports from `skills/` | `tests/skills/test_portability.py` |
| `skills/imported/` never imports from `harness/` | `tests/skills/test_portability.py` |
| No absolute user paths in vendored skills | `tests/skills/test_portability.py` |
| Adapter outputs are normalized `SkillResult` | `tests/skills/` |

### End-to-End Tests

Full pipeline via subprocess — real CLI invocation, real I/O, real Pandoc.

| Flow | What is verified |
|------|-----------------|
| `init → search → screen → draft → validate → render → verify` | Complete stage progression |
| `paper init --preset nature` | Preset template scaffolding |
| `paper render --format docx` | Pandoc produces real DOCX (12KB+) |
| `paper doctor` | Environment check with degraded mode |
| `paper import bib` | Bibliography import from external .bib |

E2E tests are marked `@pytest.mark.e2e` and run in CI with Pandoc installed.

### Smoke Tests

Target-specific real artifact generation — not full pipeline.

| Surface | Verified |
|---------|----------|
| DOCX render output | ZIP integrity (`word/document.xml` present), size > 500B |
| PDF render output | Size check (PDFs are not ZIP-based) |
| Bibliography import | File copy + normalization |
| Preset fallback | Package-bundled assets resolve correctly |

## CI Pipeline

GitHub Actions runs on every push/PR to `main`:

1. **Lint**: `ruff check .` + `ruff format --check .`
2. **Type check**: `mypy harness/ cli/ validators/ integrations/ verification/` (strict mode)
3. **Unit + integration tests**: `pytest` (excludes E2E)
4. **Install Pandoc**: required for E2E tests
5. **E2E smoke tests**: subprocess, real I/O

Matrix: Python 3.10, 3.11, 3.12, 3.13 on Ubuntu latest.

## Test Markers

| Marker | Purpose |
|--------|---------|
| `@pytest.mark.e2e` | End-to-end tests with real subprocess I/O |
| `@pytest.mark.integration` | Integration tests with real adapters on `tmp_path` |

## Local Verification

```bash
# Full verification (lint + typecheck + test)
make verify

# Individual layers
make test          # pytest
make lint          # ruff check + format check
make typecheck     # mypy strict

# Controlled validation (local-only, real material)
make validate CASE=verification/local-data/<case>.local.yaml
```

## Rules

- Tests must be deterministic — no network calls in unit/integration layers.
- E2E tests may invoke real tools (Pandoc) but must not require a running server.
- Verification reports must distinguish automated test evidence from manual review evidence.
- New features must include tests at the appropriate layer before merge.

## Audit Checklist

- [x] Current docs reflect real test count and coverage.
- [x] Test layers map to real implementation surfaces.
- [x] Contract tests enforce architectural invariants.
- [x] CI pipeline runs lint + typecheck + tests on every push.
- [x] E2E tests use real subprocess I/O, not mocks.
