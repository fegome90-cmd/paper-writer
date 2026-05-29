# paper-writer - Testing Strategy

Defines how `paper-writer` is verified across all layers of the system.

## Quick path

1. Tests run via `uv run pytest` (or `make test`).
2. CI enforces `ruff check`, `mypy strict`, and `pytest` on every push.
3. E2E tests run real subprocess I/O — not mocked.
4. Verification claims match the current maturity of the repository.

## Current State

**~520 tests passing** across unit, integration, contract, and E2E layers.

| Metric | Value |
|--------|-------|
| Linter | ruff clean |
| Type checker | mypy strict, 0 issues |
| CI | GitHub Actions (lint + typecheck + unit + E2E) |

> **Note**: Test count changes with every commit. Run `uv run pytest --collect-only -q | tail -1` for current count. Do not hardcode a specific number here — it drifts immediately.

## Test Directory Structure

```text
tests/
  adapters/        — Adapter layer tests (YAML repository, filesystem adapters)
  cli/             — CLI integration and exit-code matrix tests
  e2e/             — End-to-end subprocess tests (real I/O, real Pandoc)
  fixtures/        — Shared test fixtures
  harness/         — State manager, gates, orchestrator, assembler tests
  integrations/    — Tool wrapper integration tests (Pandoc, bibtex-tidy, Zotero)
  skills/          — Skill adapter, scoring engine, and portability tests
  validators/      — Domain validator tests (refs, citations, style, bib, structure)
  verification/    — Real material validation runner tests
  test_packaging_contract.py — Package install asset resolution contract
```

## Test Layers

### Unit Tests

Domain logic in isolation — no I/O, no subprocesses.

| Module | What is tested | Location |
|--------|---------------|----------|
| `validators/refs.py` | DOI/URL metadata completeness | `tests/validators/test_validators.py` |
| `validators/citations.py` | Citation key consistency | `tests/validators/test_validators.py` |
| `validators/style.py` | Passive voice, strong claims, forbidden phrases | `tests/validators/test_validators.py` |
| `validators/bibliography.py` | Entry types, required fields, DOI format, year range, duplicates | `tests/validators/test_validators.py` |
| `validators/reporting.py` | Study design, sample size, limitations | `tests/validators/test_validators.py` |
| `validators/structure.py` | Required section presence | `tests/validators/test_validators.py` |
| `validators/preset.py` | Journal preset schema validation | `tests/validators/test_validators.py` |
| `harness/services/state_manager.py` | State transitions, schema validation, gate reset | `tests/harness/test_state_manager.py` |
| `harness/services/gates.py` | Gate evaluation, precondition checks | `tests/harness/test_gates.py` |
| `skills/imported/literature_search/scoring.py` | Scoring engine, dedup, tier classification (56 tests) | `tests/skills/test_scoring.py` |
| `skills/local/adapters.py` | Adapter normalization, SkillResult contract | `tests/skills/test_adapters.py` |

### Integration Tests

Component interaction — real adapters, real filesystem on `tmp_path`.

| Surface | What is tested | Location |
|---------|---------------|----------|
| Orchestrator + state manager + gates | Full stage transition flow | `tests/harness/test_orchestrator.py` |
| Orchestrator builder dependency wiring | Dependency assembly | `tests/harness/test_orchestrator_builder.py` |
| FilesystemActionRunner + skill adapters | Search/screen/draft with real scoring | `tests/harness/test_orchestrator.py` |
| Tool wrappers (Pandoc, bibtex-tidy, Vale) | Real tool invocation on temp dirs | `tests/integrations/test_pandoc.py`, `tests/integrations/test_bibtex_tidy_hardening.py` |
| Zotero import | .bib file ingestion | `tests/integrations/test_zotero_import.py` |
| CLI subprocess | Request mapping and exit codes | `tests/cli/test_cli_request_mapping.py`, `tests/cli/test_cli_exit_code_matrix.py` |
| Adapters (YAML repo, filesystem) | Persistence and path resolution | `tests/adapters/test_yaml_repository.py`, `tests/adapters/test_filesystem_adapters.py` |

### Contract Tests

Architectural invariants — dependency direction, port compliance.

| Invariant | Verification |
|-----------|-------------|
| `harness/` never imports from `skills/` | `tests/skills/test_portability.py` |
| `skills/imported/` never imports from `harness/` | `tests/skills/test_portability.py` |
| No absolute user paths in vendored skills | `tests/skills/test_portability.py` |
| Adapter outputs are normalized `SkillResult` | `tests/skills/test_adapters.py` |
| Asset resolution from package install | `tests/harness/test_asset_resolution.py` |

### End-to-End Tests

Full pipeline via subprocess — real CLI invocation, real I/O, real Pandoc.

| Flow | What is verified | Location |
|------|-----------------|----------|
| `init → search → screen → draft → validate → render → verify` | Complete stage progression | `tests/e2e/test_smoke_e2e.py` |
| `paper init --preset nature` | Preset template scaffolding | `tests/e2e/test_smoke_e2e.py` |
| `paper render --format docx` | Pandoc produces real DOCX (12KB+) | `tests/e2e/test_smoke_e2e.py` |
| `paper doctor` | Environment check with degraded mode | `tests/e2e/test_smoke_e2e.py` |
| `paper import bib` | Bibliography import from external .bib | `tests/e2e/test_smoke_e2e.py` |

E2E tests are marked `pytestmark = pytest.mark.e2e` and run in CI with Pandoc installed.

## Test Markers

| Marker | Usage | Purpose |
|--------|-------|---------|
| `@pytest.mark.e2e` | `tests/e2e/test_smoke_e2e.py` (module-level) | End-to-end tests with real subprocess I/O |
| `@pytest.mark.integration` | `tests/harness/test_orchestrator_builder.py` (1 test) | Integration test with real dependency wiring |
| `@pytest.mark.parametrize` | `tests/cli/`, `tests/harness/` | Parametrized test cases |

## CI Pipeline

GitHub Actions runs on every push/PR to `main`:

1. **Lint**: `ruff check .` + `ruff format --check .`
2. **Type check**: `mypy harness/ cli/ validators/ integrations/ tests/ skills/` (strict mode)
3. **Unit + integration tests**: `pytest tests/ -m "not e2e" --tb=short`
4. **E2E smoke tests**: subprocess, real I/O (requires Pandoc installed)

Matrix: Python 3.10, 3.11, 3.12, 3.13 on Ubuntu latest.

> **Note**: Local `make typecheck` runs `mypy harness cli validators integrations verification` (without `tests/` and `skills/`). CI includes broader scope.

## Local Verification

```bash
# Full verification (lint + typecheck + test)
make verify

# Individual layers
make test          # pytest
make lint          # ruff check + format check
make typecheck     # mypy strict (local scope)

# Controlled validation (local-only, real material)
make validate CASE=verification/local-data/<case>.local.yaml
```

## Rules

- Tests must be deterministic — no network calls in unit/integration layers.
- E2E tests may invoke real tools (Pandoc) but must not require a running server.
- Verification reports must distinguish automated test evidence from manual review evidence.
- New features must include tests at the appropriate layer before merge.

## Audit Checklist

- [ ] Current docs reflect real test count (verify with `pytest --collect-only`).
- [ ] Test directories match actual filesystem layout.
- [ ] CI mypy scope matches documented scope.
- [ ] Test markers are documented only if actually used.
- [ ] New tests are added at the correct layer (unit / integration / e2e).
