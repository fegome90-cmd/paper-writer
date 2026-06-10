# Preexisting Issues Found During Autoresearch

> **Created**: 2026-06-09
> **Updated**: 2026-06-09
> **Source**: Autoresearch bug hunt sessions (#484-#509)
> **Status**: All items resolved or archived

## ✅ RESOLVED

| Item | Resolution | Experiment |
|------|-----------|------------|
| Type Safety (119 mypy in science-bundle) | Archived — imported skill code, high regression risk | #500-#501 |
| Validator None guards | Fixed — 4 validators get `if manuscript is None: return []` | Commit 1357eb30 |
| .get None pattern sweep | Fixed — 21 replacements in 4 files | Commit 1357eb30 |
| Zotero SafeRedirectHandler | Fixed — strips API key on cross-domain redirects | #508-#509 |
| Consensus R1 (schema validation) | Fixed — validates QueryResult required fields | #506-#507 |
| Consensus R2 (rate limiting) | Fixed — retry_with_backoff on 429 | #502-#503 |
| Consensus R3 (422 parsing) | Fixed — HTTPValidationError detail array | #504-#505 |
| Consensus R4 (capability query) | Fixed — supported_filters property on ABC | #502-#503 |
| PRE-1 (thesaurus import) | Already resolved — lazy import with try/except | Issue log updated |

## ❌ BLOCKED

| Item | Blocker |
|------|---------|
| Consensus R5 (real API test) | Requires CONSENSUS_API_KEY |
| science-bundle mypy strict | Recommend excluding from strict checking |

## Type Safety — `skills/local/science-bundle/`

**Severity**: LOW — imported skill code, not core pipeline
**Files affected**: 10 files, 119 mypy errors
**Pattern**: Missing type annotations on functions, untyped calls

| File | Errors | Pattern |
|------|--------|---------|
| `europepmc_api.py` | 28 | `no-untyped-def`, `no-untyped-call`, `no-any-return` |
| `pubmed_api.py` | ~20 | Same pattern |
| `openalex_cli.py` | ~15 | Unresolved import (`science_skills.scienceskillscommon`), `no-any-return` |
| `search_by_dates.py` | ~10 | `no-untyped-def` |
| `search_by_doi.py` | ~5 | `no-untyped-def` |
| `search_arxiv.py` | ~10 | `no-untyped-def` |
| `download_paper.py` | ~10 | `no-untyped-def` |
| `download_paper_source.py` | ~10 | `no-untyped-def` |
| `http_client.py` | ~5 | `no-untyped-def` |
| `cli_script_template.py` | ~6 | `no-untyped-def` |

**Fix approach**: Add type annotations to all public functions. Batch fix per file.

## Defensive Gaps — Validator `.validate(None)` Crashes

**Severity**: LOW — orchestrator never passes None
**Files affected**: Multiple validators under `validators/`
**Pattern**: `validate()` methods crash with `AttributeError` when passed `None`

| Validator | Crash | Protected by caller |
|-----------|-------|-------------------|
| `ProseValidator.validate(None)` | `manuscript.sentences` → AttributeError | Yes (orchestrator passes Manuscript) |
| `EthicsValidator.validate(None)` | Same pattern | Yes |
| `MethodGateValidator.validate(None)` | Same pattern | Yes |
| `WritingQualityValidator` | Same pattern | Yes |

**Fix approach**: Add `if manuscript is None: return []` guard at top of each `validate()`.

## Zotero WIP — Partial Changes in Stash (CONSUMED)

**Severity**: N/A — stash was consumed, cherry-picked safe fixes only
**What was in the WIP**:
- `SafeRedirectHandler` for cross-domain API key leakage (security)
- `opener` instead of `urlopen` (required by SafeRedirectHandler)
- `_parse_bib` loop fix (already done differently via `_remove_entries_by_keys`)
- Orchestrator `save_state()` on failure path (partially addressed)
- Stage guard: `current_stage == "validating"` for lint→rendering transition

**Remaining from WIP**:
- `SafeRedirectHandler` — strips Zotero API key on cross-domain redirects
- `OpenerDirector.open` test patching (tests patched `urlopen`, need `opener`)
- Orchestrator `save_state()` on gate failure mid-transaction
- `current_stage` guard in `_get_next_stage` for lint commands

## Pattern: `.get(key, [])` vs `.get(key) or []`

**Severity**: MEDIUM — crashes on None values from real APIs
**Status**: FIXED in clients (crossref, openalex, S2, zotero) and harness
**Remaining instances** (lower risk — internal data, not API responses):

- `cli/paper/commands/audit.py:386` — `evidence_data.get("evidence", [])`
- `cli/paper/commands/graph.py:74` — `data.get("path", [])`
- `harness/services/verify_artifacts.py` — 7 instances with `.get(..., [])`
- `validators/` — ~30 instances with `.get(..., [])`
- `skills/imported/` — ~10 instances
- `engine/formatter.py` — 4 instances

These are lower risk because they process data from our own pipeline (not external APIs), but the pattern is fragile. Consider a systematic `or []` / `or {}` sweep.

## Deferred Autoresearch Ideas (from ideas backlog)

- **R1**: Response schema validation — validate API responses against QueryResult spec
- **R2**: Rate limiting — parse Retry-After header on 429, backoff strategy
- **R3**: 422 Validation Error — spec defines HTTPValidationError, parse detail array
- **R4**: Provider capability query — method to check which filters a provider supports
- **R5**: Integration test with real API — extend smoke test to cover filter params
