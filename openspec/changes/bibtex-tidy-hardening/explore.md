# SDD Exploration — Bibtex-Tidy Hardening

## Purpose
Examine the integration of the external `bibtex-tidy` tool and define a reproducible, secure, and offline installation and execution strategy.

---

## 1. Analysis of Installation Alternatives

*   **`uv`**: PyPI/Python only. Since `bibtex-tidy` is a Node.js tool, it is completely out of scope for `uv`.
*   **`npx` / `pnpm dlx`**: Downloads code dynamically from the NPM registry on every run. This exposes the pipeline to supply-chain attacks (malware injection or typosquatting in real time), introduces latency, and violates the offline execution capability.
*   **Global install (`pnpm add -g`)**: External to the repository. Does not guarantee that different development machines or CI pipelines run the same version, violating reproducibility.
*   **Local Toolchain (`package.json` + lockfile)**: Commits a locked version dependency to the repository. Runs offline using `node_modules` structure after bootstrap. Highly reproducible and secure.

---

## 2. Execution Vulnerabilities in Existing Adapter

*   **PATH contamination**: Invocations of `"bibtex-tidy"` in `subprocess.run` search the global `PATH` by default. This makes the harness susceptible to running unexpected binaries if the system PATH is polluted.
*   **Destructive modification**: The `--modify` parameter edits the source bibliography file in-place. If the tool fails or crashes mid-way, it could corrupt the `.bib` file.
*   **No version enforcement**: No verification is made on the actual version running, allowing drift in output formatting rules.

---

## 3. Recommended Approach

1.  Create a local toolchain in `tools/node/` with `package.json` pinning `bibtex-tidy` to `1.12.0`.
2.  Refactor `BibliographyNormalizer` in `integrations/tools/bibtex_tidy.py` to resolve the executable path securely:
    - `BIBTEX_TIDY_BIN` first if explicitly set, failing fast if invalid.
    - then local toolchain.
    - then global PATH only when `BIBTEX_TIDY_ALLOW_GLOBAL=true`.
3.  Implement a strict version verification step (`--version` matches `1.12.0`).
4.  Copy the original `.bib` file to a temporary backup (`.bib.bak`) before running, restoring it on execution failure to prevent corruption.

> [!NOTE]
> The authoritative execution contract is defined in spec.md; this exploration is rationale only.
