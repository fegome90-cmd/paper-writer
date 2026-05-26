# Tasks — Bibtex-Tidy Hardening

This checklist tracks the physical execution steps for implementation and validation.

---

## 1. Toolchain Setup
- [x] Create `tools/node/package.json` with pinned version `1.12.0`.
- [ ] Generate and commit `tools/node/pnpm-lock.yaml`.
- [ ] Verify bootstrap works with:
    `cd tools/node && pnpm install --frozen-lockfile --ignore-scripts`

## 2. Integration Wrapper Hardening
- [ ] Refactor `integrations/tools/bibtex_tidy.py` to:
    - [ ] Implement `_resolve_executable()` supporting strict env override priority, local toolchain fallback, and conditional global PATH check.
    - [ ] Implement `_verify_version()` matching version exactly against `"1.12.0"`.
    - [ ] Refactor `run()` to implement backup collision prevention, timeout execution, and degraded built-in fallback reporting.

## 3. Test Coverage Addition
- [ ] Write unit/integration tests in `tests/integrations/test_bibtex_tidy.py` covering:
    - [ ] Test that invalid `BIBTEX_TIDY_BIN` fails fast and does not fallback.
    - [ ] Test that valid `BIBTEX_TIDY_BIN` wins over local toolchain.
    - [ ] Test that local toolchain is resolved when `BIBTEX_TIDY_BIN` is absent.
    - [ ] Test that global PATH is ignored unless `BIBTEX_TIDY_ALLOW_GLOBAL=true` is set.
    - [ ] Test that version mismatch prevents file modifications and fails.
    - [ ] Test that version command timeout/failure is handled correctly.
    - [ ] Test that subprocess failure restores original file from backup.
    - [ ] Test that backup collision policy fails fast if `.bak` already exists.
    - [ ] Test that unresolved binary produces degraded built-in validation result with explicit summary.

## 4. Quality Sweep
- [ ] Run `make verify` and confirm all tests, typecheckers, and linters pass cleanly.
