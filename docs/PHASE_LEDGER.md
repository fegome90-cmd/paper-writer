# Phase Ledger

This document tracks the verified state, commit lineage, and history of the `paper-writer` project phases. It serves as the single source of truth to prevent context drift and avoid re-executing or regressing completed phases.

## Summary of Completed Phases

| Phase | State | Key Commits | Evidence | Decision / Status |
|-------|-------|-------------|----------|-------------------|
| **Phase 1** | Closed | `961e33b`, `2b35386` | CLI base structure, hexagonal harness ports | Merged. Stable. |
| **Phase 2** | Closed | `0e784bb`, `2a7eb34` | Hardened `bibtex-tidy` local toolchain and integration tests | Merged. Stable. |
| **Phase 3** | Closed | `ccb2afe` | Skills vendoring policy, imported manifest, portability tests | Closed. Verified 100% pure (no harness leak). |
| **Phase 4** | Closed | `e85f345`, `9d294ae`, `5dba6e0` | CLI dependency wiring refactoring, `orchestrator_builder.py` | Present in history. Do not reopen. |
| **Phase 5** | Closed | `a5910f3`, `59c806f`, `4056612` | Production readiness, degraded mode verification, docs | Present in history. Do not reopen. |
| **Phase 6** | Active | `241150a`, `0eb1e4d`, `6c89657` | Real material validation runner, PDF metadata extraction, test suite | Under validation/audit. |

---

## Phase Details

### Phase 3 — Skills Vendoring
*   **Target Commit:** [ccb2afe](file:///Users/felipe_gonzalez/Developer/paper-writer/tests/skills/test_portability.py)
*   **Status:** Closed
*   **Verification & Evidence:**
    *   Vendor policy documented in [docs/SKILLS_VENDORING.md](file:///Users/felipe_gonzalez/Developer/paper-writer/docs/SKILLS_VENDORING.md).
    *   Manifest tracking configured in [skills/imported/MANIFEST.yaml](file:///Users/felipe_gonzalez/Developer/paper-writer/skills/imported/MANIFEST.yaml).
    *   Automated portability checks implemented in [tests/skills/test_portability.py](file:///Users/felipe_gonzalez/Developer/paper-writer/tests/skills/test_portability.py) to check for absolute paths, `/Users/` references, or cross-talk between external workspaces.
*   **Historical Note:** This commit was audited and verified to be 100% pure. It only introduces the skills documentation, manifests, relocated skills, and portability tests. No runtime CLI mapping or harness wiring leaked into this commit.

### Phase 4 — CLI & Builder wiring
*   **Key Commits:** 
    *   `e85f345` (CLI dependency wiring refactored to `orchestrator_builder.py`).
    *   `9d294ae` (bibtex-tidy version allowlist replaced with minimum-version policy).
    *   `b4ad2f5` (Historical mixed commit containing both bibtex-tidy hardening logic and the initial `--raw-papers` CLI changes + `mock_candidates.json` fixture).
*   **Status:** Closed (integrated in history)
*   **Decision:** The mixed commit `b4ad2f5` is accepted as-is in the project lineage. We will **not** attempt to rewrite history or rebase this commit to maintain branch stability. 
*   **Riesgos Residuales:** The CLI implementation of `--raw-papers` lives in `b4ad2f5` which is mixed with tool wrappers validation. This is documented and accepted. No active drift detected.

### Phase 5 — Production Readiness
*   **Key Commits:** `313be2f`, `a5910f3`, `59c806f`, `4056612`
*   **Status:** Closed (integrated in history)
*   **Verification & Evidence:**
    *   [docs/PRODUCTION_READINESS.md](file:///Users/felipe_gonzalez/Developer/paper-writer/docs/PRODUCTION_READINESS.md) updated with degraded mode specifications.
    *   `make verify` clean with all E2E pipeline tests verified locally.

### Phase 6 — Real Material Validation (Active)
*   **Key Commits:** `241150a`, `0eb1e4d`, `6c89657`
*   **Status:** Under validation
*   **Scope:**
    *   Execution of the real validation runner [verification/run_real_validation.py](file:///Users/felipe_gonzalez/Developer/paper-writer/verification/run_real_validation.py).
    *   Supports reading a manifest case, extracting text and metadata from a local PDF, auto-generating a `.bib` entry, setting up an isolated temporary workspace, and running the CLI pipeline offline.
    *   Includes manual review checklists to verify formatting and citation quality.
