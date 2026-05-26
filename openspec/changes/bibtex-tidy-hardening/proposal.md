# Proposal — Bibtex-Tidy Hardening

We will implement a local, pinned Node toolchain and refactor the `bibtex-tidy` integration wrapper to enforce strict path resolution, version validation, backup collision checks, and degraded fallback semantics.

## User Review Required

> [!IMPORTANT]
> **Priority Resolution Contract**:
> 1. If `BIBTEX_TIDY_BIN` is defined: Use this path exclusively. If invalid or not executable, **fail fast immediately** (no fallbacks).
> 2. If `BIBTEX_TIDY_BIN` is NOT defined: Use the local toolchain at `tools/node/node_modules/.bin/bibtex-tidy`.
> 3. If local is missing: Fall back to system `PATH` **only if** `BIBTEX_TIDY_ALLOW_GLOBAL=true`.
> 4. If nothing resolves: Fallback to built-in validation, reporting that external normalization was skipped.

> [!IMPORTANT]
> **Data Integrity Protection**:
> Before any modification in-place (`--modify`), the wrapper will verify if a backup copy `references.bib.bak` already exists. If it exists, it will **fail immediately** to prevent overwriting active recovery data.

---

## Open Questions

> [!NOTE]
> No outstanding questions. The integration scope is fully bounded by these documentation rules.

---

## Proposed Changes

### Toolchain
Create package metadata to control dependency resolution.

#### [NEW] [package.json](file:///Users/felipe_gonzalez/Developer/paper-writer/tools/node/package.json)
* Pinned dependency: `"bibtex-tidy": "1.12.0"`.

#### [NEW] [pnpm-lock.yaml](file:///Users/felipe_gonzalez/Developer/paper-writer/tools/node/pnpm-lock.yaml)
* Lockfile mapping transitives and checksums for the pinned tool version.

### Integrations
Refactor execution security in the wrapper tool.

#### [MODIFY] [bibtex_tidy.py](file:///Users/felipe_gonzalez/Developer/paper-writer/integrations/tools/bibtex_tidy.py)
* Add `_resolve_executable()` aligning with the new strict override-first resolution priority.
* Add `_verify_version()` validating output against `"1.12.0"`.
* Refactor `run()` to perform backup collision checks, timeout limits, and explicit degraded reporting if the tool is bypassed.

### Tests
Harden validator tests for all scenarios.

#### [MODIFY] [test_validators.py](file:///Users/felipe_gonzalez/Developer/paper-writer/tests/validators/test_validators.py)
* Add tests verifying the strict override priority, version mismatch failures, backup collision crashes, and degraded fallback states.

---

## Verification Plan

### Automated Tests
* Run `make verify` to ensure formatting, typing, and all tests pass.
* Run target integration tests specifically written for this hardening.
