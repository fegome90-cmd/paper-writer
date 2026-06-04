# paper-writer - Testing Strategy

Defines how `paper-writer` is verified across all layers of the system.

## Quick path

1. Tests run via `uv run pytest` (or `make test`).
2. Repository docs describe CI enforcement for `ruff check`, `mypy`, and `pytest`; current CI state was not re-run in this audit pass.
3. E2E tests run real subprocess I/O — not mocked.
4. Verification claims match the current maturity of the repository.

## Current State

The repository contains unit, integration, adapter, CLI, skill, and E2E coverage.
This audit pass did not re-run the suite, so fixed test counts are intentionally omitted.

| Metric | Value |
|--------|-------|
| Linter | Repository-documented: ruff |
| Type checker | Repository-documented: mypy |
| CI | Repository-documented: GitHub Actions with lint, typecheck, tests |

> **Requires re-verification**: current test counts, current CI pass/fail state, and current linter/typechecker cleanliness.

## Test Directory Structure

```text
tests/
  cli/             — CLI integration and exit-code matrix tests
  e2e/             — End-to-end subprocess tests (real I/O, real Pandoc)
  harness/         — State manager, gates, orchestrator, assembler tests
  integrations/    — Tool wrapper integration tests (Pandoc, bibtex-tidy, Zotero)
  skills/          — Skill adapter, scoring engine, and portability tests
  test_clients/    — API client unit tests (Crossref, Semantic Scholar, retry, resiliency)
  clients/         — Trifecta and hardening fidelity tests
```

This page is limited to the test files used as evidence in this audit pass. Other test directories may exist, but they were not part of the required evidence set here.

## Test Layers

### Unit Tests

Focused logic tests evidenced in this audit set include:

| Module | What is tested | Location |
|--------|---------------|----------|
| `harness/services/gates.py` | Gate evaluation and malformed validator handling | `tests/harness/test_gates.py` |
| `harness/domain/state.py` + `harness/services/orchestrator.py` | Stage invariants and transition behavior through orchestrator fixtures | `tests/harness/test_orchestrator.py` |
| `skills/local/adapters.py` | Search/screen/draft adapter behavior and "no state.yaml" invariant | `tests/skills/test_adapters.py` |

### API Client Tests

Unit tests for Crossref, Semantic Scholar, Trifecta, and shared utilities. All use dependency injection (DI) for sleep/clock — no monkeypatching.

| Module | What is tested | Location |
|--------|---------------|----------|
| `clients/crossref.py` | DOI lookup, title search, rate limiting, JSON/Unicode error handling, DOI URL encoding | `tests/test_clients/test_crossref.py` |
| `clients/semantic_scholar.py` | DOI lookup, title search, outage latch, year tiebreaker, DI-based error injection | `tests/test_clients/test_semantic_scholar.py` |
| `clients/_retry.py` | Exponential backoff, max retries, non-429 passthrough, on_retry callback | `tests/test_clients/test_retry.py` |
| `clients/_text_similarity.py` | Title normalization, SequenceMatcher ratio, threshold boundary cases | `tests/test_clients/test_text_similarity.py` |
| Client resiliency | Latch lifecycle, DI wiring, year tiebreaker, verify_doi end-to-end | `tests/test_clients/test_resiliency.py` |
| `clients/trifecta.py` | Response normalization, health checks, error handling | `tests/clients/test_trifecta.py` |

### Integration Tests

Component interaction — real adapters, real filesystem on `tmp_path`.

| Surface | What is tested | Location |
|---------|---------------|----------|
| Orchestrator + state manager + gates | Full stage transition flow | `tests/harness/test_orchestrator.py` |
| CLI request mapping | Argument-to-request translation, failure policy, render flag forwarding | `tests/cli/test_cli_request_mapping.py` |
| CLI workflow | End-to-end command flow, preset init, import bib, render flags, negative paths | `tests/cli/test_paper_cli.py` |
| Doctor and degraded mode | Tool reporting and degraded wrapper warnings | `tests/cli/test_doctor_and_degraded.py` |
| Pandoc wrapper | Availability, failures, multi-output behavior, CSL/reference-doc forwarding | `tests/integrations/test_pandoc.py` |
| Skill adapters | Search/screen/draft behavior with real adapter surfaces | `tests/skills/test_adapters.py` |

### Contract Tests

Some contract-like invariants are covered by the evidence set, but this audit does not restate broader architecture claims without direct support from the selected files.

| Invariant | Verification |
|-----------|-------------|
| Skill adapters do not write `outputs/state.yaml` | `tests/skills/test_adapters.py` |
| CLI request mapping preserves render args exactly | `tests/cli/test_cli_request_mapping.py` |

### End-to-End Tests

Full pipeline via subprocess — real CLI invocation, real I/O, and real Pandoc when available.

| Flow | What is verified | Location |
|------|-----------------|----------|
| `init → search → screen → draft → validate → render → verify` | Complete stage progression | `tests/e2e/test_smoke_e2e.py` |
| `paper init --preset nature` | Preset template scaffolding | `tests/e2e/test_smoke_e2e.py` |
| `paper render --format docx` | Pandoc produces a real DOCX artifact when Pandoc is available | `tests/e2e/test_smoke_e2e.py` |
| `paper doctor` | Environment check with degraded mode | `tests/e2e/test_smoke_e2e.py` |
| `paper import bib` | Bibliography import from external .bib | `tests/e2e/test_smoke_e2e.py` |

E2E tests are marked `pytestmark = pytest.mark.e2e` and run in CI with Pandoc installed.

### Alignment note

The render stage currently advances the orchestrator to `verified` on successful `paper render`, and `paper verify` remains a separate command that checks `ready_for_delivery` and emits `outputs/manifest.yaml`. Documentation that treats render as a terminal "done" stage is stale and should be considered corrected by the code-level model.

## Test Markers

| Marker | Usage | Purpose |
|--------|-------|---------|
| `@pytest.mark.e2e` | `tests/e2e/test_smoke_e2e.py` (module-level) | End-to-end tests with real subprocess I/O |
| `@pytest.mark.parametrize` | `tests/cli/`, `tests/harness/` | Parametrized test cases |

## CI Pipeline

Repository documentation currently describes the following CI flow:

1. **Lint**: `ruff check .`
2. **Type check**: `mypy harness/ cli/ validators/ integrations/ verification/ parsers/ engine/ rules/ schemas/ skills/`
3. **Unit + integration tests**: `pytest tests/ -m "not e2e" --tb=short`
4. **E2E smoke tests**: subprocess, real I/O (requires Pandoc installed)

Python matrix and current run status require re-verification.

> **Repository-documented scope note**: local and CI mypy scopes may differ. That claim was preserved as an operational note, but the current CI configuration was not re-executed in this audit pass.

## Local Verification

```bash
# Full verification (lint + typecheck + test)
make verify

# Individual layers
make test          # pytest
make lint          # ruff check + format check
make typecheck     # mypy (local scope)

# Controlled validation (local-only, real material)
make validate CASE=verification/local-data/<case>.local.yaml
```

## Rules

- Tests must be deterministic — no network calls in unit/integration layers.
- E2E tests may invoke real tools (Pandoc) but must not require a running server.
- Verification reports must distinguish automated test evidence from manual review evidence.
- New features must include tests at the appropriate layer before merge.

## Audit Checklist

- [ ] Current docs reflect a freshly re-verified test count.
- [x] This page now limits strong claims to the evidence set inspected in this audit.
- [ ] CI mypy scope matches documented scope after re-verification.
- [x] `@pytest.mark.e2e` is documented because it is present in `tests/e2e/test_smoke_e2e.py`.
- [ ] New tests continue to be added at the correct layer (unit / integration / e2e).
