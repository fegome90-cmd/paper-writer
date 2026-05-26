# Skills Vendoring Policy

This document defines the architecture, ownership, and maintenance policy for imported domain skills in `paper-writer`.

## Core Principle

Domain skills (such as `literature-search` and `academic-writer`) are **authoritative runtime components** of the local repository. They are versioned, tested, and shipped directly within the repository under the `skills/imported/` directory.

> [!IMPORTANT]
> **No Dynamic Fetching**: The installer and runtime environment must **never** clone, download, or fetch skills from external repositories during installation or execution. All skills are offline-first and self-contained.

## Architectural Tradeoffs

By vendorizing skills, we prioritize:
1. **Reproducibility**: The code, prompts, and templates used for search and writing are locked to the specific repository version.
2. **Determinism**: The CI pipeline and developers see the exact same logic. No dynamic updates can break the build or output quality.
3. **Offline Execution**: Installing and running the harness requires no internet access for resolving skill layers.

The cost is that updates from upstream sources (e.g., `examen_grado`) must be synced manually via Pull Requests.

## Manifest Configuration

Every imported skill must be declared in [MANIFEST.yaml](file:///Users/felipe_gonzalez/Developer/paper-writer/skills/imported/MANIFEST.yaml). The manifest tracks:
* `id` — Identificador de la skill.
* `local_path` — Ubicación en el repositorio.
* `source_repo` — Repositorio original (fuente histórica / upstream).
* `source_commit` — Commit hash exacto del upstream en el momento de la importación.
* `imported_at` — Fecha de importación del snapshot.
* `import_mode` — Establecido en `vendor_snapshot`.
* `modified_locally` — Indica si el código/documento fue adaptado para este repositorio.
* `runtime_authority` — Establecido en `local_repo` (la versión local es la que manda).
* `update_policy` — Establecido en `manual_pr_only`.
* `external_fetch_at_install` — Establecido en `false`.

## Upstream Synchronization and Updates

To update an imported skill from its historical upstream source, follow these steps:

1. **Compare versions**: Run a recursive `diff` between the local directory and the upstream path.
   ```bash
   diff -ur skills/imported/literature_search/ /Users/felipe_gonzalez/Developer/examen_grado/skills/literature-search/
   ```
2. **Apply Changes**: Copy the files manually or use `git merge-file` if resolving conflicts.
3. **Update Manifest**: Update the `source_commit`, `imported_at`, and `modified_locally` fields in `skills/imported/MANIFEST.yaml`.
4. **Run Verification**: Execute the verification tests to ensure that the updated skill conforms to the hexagonal contract.
   ```bash
   make verify
   ```
5. **Open Pull Request**: Commit the files and open a Pull Request. Never mix skill updates with functional changes to integration wrappers.
