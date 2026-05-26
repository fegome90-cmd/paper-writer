# Specification — Bibtex-Tidy Hardening

This specification defines the strict execution contract, error handling, version enforcement, and safety guarantees for the `bibtex-tidy` integration wrapper in `paper-writer`.

---

## 1. Strict Executable Resolution Priority

The wrapper must resolve the path to the executable in a strictly prioritized order.

### Scenario 1.1: Environment Variable Override (`BIBTEX_TIDY_BIN`) Wins First
*   **Given**: The environment variable `BIBTEX_TIDY_BIN` is set to `/custom/bin/bibtex-tidy`.
*   **And**: The file at that custom path is executable.
*   **When**: The normalizer runs.
*   **Then**: The wrapper resolves the executable to `/custom/bin/bibtex-tidy`, bypassing any local toolchain.

### Scenario 1.2: Invalid Environment Override Fails Fast (No Fallback)
*   **Given**: `BIBTEX_TIDY_BIN` is set to a path that does not exist or is not executable.
*   **When**: The normalizer runs.
*   **Then**: The execution fails immediately with a descriptive error. It must **NOT** fall back to the local toolchain or system PATH.

### Scenario 1.3: Local Toolchain (Fallback when ENV Override absent)
*   **Given**: `BIBTEX_TIDY_BIN` is NOT defined.
*   **And**: A file exists at `tools/node/node_modules/.bin/bibtex-tidy` and is executable.
*   **When**: The normalizer runs.
*   **Then**: The wrapper resolves the executable to `tools/node/node_modules/.bin/bibtex-tidy`.

### Scenario 1.4: Global PATH Fallback Disabled by Default
*   **Given**: `BIBTEX_TIDY_BIN` is NOT defined.
*   **And**: The local toolchain is missing.
*   **And**: `BIBTEX_TIDY_ALLOW_GLOBAL` is NOT set to `"true"`.
*   **When**: The normalizer runs.
*   **Then**: The wrapper resolves no executable and falls back to degraded built-in validation (see Section 3).

### Scenario 1.5: Global PATH Fallback Allowed Explicitly
*   **Given**: `BIBTEX_TIDY_BIN` is NOT defined.
*   **And**: The local toolchain is missing.
*   **And**: `BIBTEX_TIDY_ALLOW_GLOBAL` is set to `"true"`.
*   **And**: `bibtex-tidy` exists in the system `PATH`.
*   **When**: The normalizer runs.
*   **Then**: The wrapper resolves the executable using the global PATH.

---

## 2. Version Enforcement Criterias

### Scenario 2.1: Version Match (1.12.0)
*   **Given**: The resolved executable is run with `--version`.
*   **And**: The stdout outputs `v1.12.0` or `1.12.0`.
*   **When**: The normalizer runs.
*   **Then**: Version check succeeds, and execution continues.

### Scenario 2.2: Version Mismatch (Fail Fast)
*   **Given**: The resolved executable is run with `--version`.
*   **And**: The output is different from `1.12.0` (e.g. `1.10.0` or version command fails/timeouts).
*   **When**: The normalizer runs.
*   **Then**: Validation fails with a clear mismatch error. The main `.bib` file is not modified.

---

## 3. Degraded Fallback Semantics

### Scenario 3.1: No Executable Resolved (Explicit Skip)
*   **Given**: No executable path could be resolved under the priority rules of Section 1.
*   **When**: The normalizer runs.
*   **Then**: It executes the built-in regex-based validator.
*   **And**: The result summary must explicitly state: `"normalization skipped / builtin validation used"`.
*   **And**: The gate status is evaluated based on built-in parser results, but the artifact checklist does NOT claim `bibtex-tidy` ran.

---

## 4. Data Integrity & Collision Protection

### Scenario 4.1: Backup Collision Prevention
*   **Given**: A backup file already exists at `templates/references.bib.bak`.
*   **When**: The validation starts.
*   **Then**: The validation fails immediately with a collision error. It must **NOT** modify the original file nor overwrite the existing backup.

### Scenario 4.2: Execution Fails (Restore Backup)
*   **Given**: No backup collision exists.
*   **And**: The backup `templates/references.bib.bak` is successfully created.
*   **When**: The `bibtex-tidy` process exits with code != 0, or is terminated by timeout.
*   **Then**: The original file at `templates/references.bib` is restored from the backup `templates/references.bib.bak`.
*   **And**: The temporary backup is deleted.
*   **And**: The validator returns a `fail` status.

### Scenario 4.3: Execution Succeeds (Clean Backup)
*   **Given**: The `bibtex-tidy` process exits with code 0.
*   **When**: Execution completes successfully.
*   **Then**: The temporary backup `templates/references.bib.bak` is safely deleted.
*   **And**: The validator returns a `pass` status.
