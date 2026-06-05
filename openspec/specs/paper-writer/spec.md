# Specs: multi-project-mode

## NEW: project-resolution Specification

### Purpose

Defines how the CLI resolves which directory is the "project root" — the directory containing a paper's outputs, templates, and state.

### Requirements

#### REQ-PR-01: Project root resolution priority

The CLI SHALL resolve `project_root` using this priority chain:
1. Explicit `--project/-C` flag value
2. Ascending search for `outputs/state.yaml` from CWD (innermost match, like git)
3. `Path.cwd()` fallback

##### Scenario: Explicit flag overrides everything
- GIVEN a directory `/tmp/my-paper` containing `outputs/state.yaml`
- WHEN user runs `paper -C /tmp/my-paper search` from `/home/user`
- THEN `project_root` SHALL be `/tmp/my-paper`

##### Scenario: Ascending search finds project from subdirectory
- GIVEN `/tmp/my-paper/outputs/state.yaml` exists
- WHEN user runs `paper search` from `/tmp/my-paper/src/`
- THEN `project_root` SHALL be `/tmp/my-paper`

##### Scenario: CWD fallback for new projects
- GIVEN CWD is `/tmp/new-paper/` (no `outputs/state.yaml` anywhere above)
- WHEN user runs `paper init`
- THEN `project_root` SHALL be `/tmp/new-paper/`

##### Scenario: Ascending search stops at innermost match
- GIVEN `/home/user/paper-a/outputs/state.yaml` exists AND user is in `/home/user/paper-a/notes/`
- WHEN user runs `paper search`
- THEN `project_root` SHALL be `/home/user/paper-a` (stops at first match)

#### REQ-PR-02: Ascending search safety bounds

The ascending search SHALL be bounded to 20 parent directories. The search SHALL resolve symlinks via `Path.resolve()` before checking for `outputs/state.yaml` to prevent symlink injection attacks. If the filesystem root is reached, CWD fallback SHALL apply.

##### Scenario: Deeply nested directory
- GIVEN user is 50 levels deep in a directory tree with no `state.yaml` above
- WHEN ascending search runs
- THEN search SHALL stop after 20 levels and use CWD fallback

##### Scenario: Symlink in ancestor directory
- GIVEN an ancestor directory contains a symlink `outputs/state.yaml` pointing to a file outside the user's project
- WHEN ascending search resolves the path
- THEN `Path.resolve()` SHALL resolve the symlink and the resolved path SHALL still be within the user's directory tree

#### REQ-PR-03: Explicit flag validation

When `--project` flag is provided, the CLI SHALL validate the path exists and is a directory. Invalid paths SHALL produce an error with exit code 1.

##### Scenario: Non-existent project path
- GIVEN `--project /nonexistent/path`
- WHEN CLI starts
- THEN error message SHALL say "Project path does not exist: /nonexistent/path"
- AND exit code SHALL be 1

---

## MODIFIED: repo-initialization-gate

### Requirement: validate_repo_initialized

(currently checks: `["cli", "harness", "validators", "templates", "outputs"]`)

The gate SHALL verify that a project directory contains the minimum structure for paper-writer operation. It SHALL check for `templates/`, `outputs/`, and `outputs/state.yaml` only. Source-code directories (`cli/`, `harness/`, `validators/`, `tests/`) SHALL NOT be required.

(Previously: checked 5 directories including source-code dirs cli, harness, validators)

#### Scenario: Fresh project passes gate
- GIVEN a directory with `templates/`, `outputs/`, and `outputs/state.yaml`
- WHEN `validate_repo_initialized` runs
- THEN gate SHALL pass

#### Scenario: Missing templates fails gate
- GIVEN a directory with `outputs/` and `outputs/state.yaml` but no `templates/`
- WHEN `validate_repo_initialized` runs
- THEN gate SHALL fail with blocker "templates directory missing"

#### Scenario: Source-code dirs absent does not affect gate
- GIVEN a project with `templates/`, `outputs/`, `outputs/state.yaml` but no `cli/`, `harness/`, or `validators/`
- WHEN `validate_repo_initialized` runs
- THEN gate SHALL pass

---

## MODIFIED: asset-resolution

### Requirement: Asset path resolution

(currently: package-only via `importlib.resources`)

The system SHALL resolve assets (templates, styles, presets, skills resources) using a waterfall:
1. Project-local path: `{project_root}/{asset_path}` — if exists, use this
2. Package-bundled path: resolved via `importlib.resources` — fallback

(Previously: package-only resolution, no project-local fallback)

#### Scenario: Project has custom template
- GIVEN project at `/tmp/my-paper` with `/tmp/my-paper/templates/manuscript.qmd`
- WHEN asset resolver looks for `templates/manuscript.qmd`
- THEN SHALL return `/tmp/my-paper/templates/manuscript.qmd`

#### Scenario: Project missing asset, package has it
- GIVEN project at `/tmp/my-paper` with no `templates/journals/nature/`
- AND installed package has `templates/journals/nature/`
- WHEN asset resolver looks for `templates/journals/nature/preset.yaml`
- THEN SHALL return the package-bundled path

#### Scenario: Neither project nor package has asset
- GIVEN project has no `templates/journals/nonexistent/` and package doesn't either
- WHEN asset resolver looks for it
- THEN SHALL return the package-bundled path (which won't exist — caller checks)

---

## MODIFIED: cli-entrypoint

### Requirement: Global project flag

(currently: no global flags, subcommands only)

The CLI SHALL accept an optional `--project/-C` global flag before any subcommand. When provided, it SHALL set `project_root` to the given path, overriding CWD-based resolution.

(Previously: no global flags, `project_root = Path.cwd()` hardcoded)

#### Scenario: Flag before subcommand
- GIVEN user runs `paper -C /tmp/my-paper init --preset nature`
- THEN `project_root` SHALL be `/tmp/my-paper`
- AND `paper init --preset nature` SHALL execute normally

#### Scenario: No flag, CWD is project
- GIVEN CWD contains `outputs/state.yaml`
- WHEN user runs `paper search` (no `--project` flag)
- THEN `project_root` SHALL be CWD (backward compatible)

#### Scenario: Flag with orchestrator subcommands
- GIVEN valid project at `/tmp/my-paper`
- WHEN user runs `paper -C /tmp/my-paper <orchestrator-subcommand>` (init, search, screen, draft, lint, check, audit reporting, import, render, verify)
- THEN all orchestrator subcommands SHALL resolve paths relative to `/tmp/my-paper`

> **Note**: Phase 0 commands (`audit prose`, `audit claims`, `gate method`) operate on explicit file paths, not project root. The `--project` flag does not affect them.

---

## MODIFIED: init-directory-creation

### Requirement: paper init directory scaffolding

(currently: creates 10 dirs including `cli/`, `harness/`, `validators/`, `tests/`)

`paper init` SHALL create only project-necessary directories: `templates/`, `outputs/`, `outputs/search/`, `outputs/drafts/`, `outputs/render/`, `outputs/logs/`. Source-code directories (`cli/`, `harness/`, `validators/`, `tests/`) SHALL NOT be created.

(Previously: created cli/, harness/, validators/, tests/ stubs to pass gate)

#### Scenario: Init creates lean project
- GIVEN empty directory `/tmp/new-paper`
- WHEN `paper init` runs
- THEN directories created SHALL be: `templates/`, `outputs/`, `outputs/search/`, `outputs/drafts/`, `outputs/render/`, `outputs/logs/`
- AND `cli/`, `harness/`, `validators/`, `tests/` SHALL NOT exist

#### Scenario: Init with preset from installed package
- GIVEN empty directory `/tmp/new-paper` and package has `nature` preset
- WHEN `paper -C /tmp/new-paper init --preset nature` runs
- THEN `templates/manuscript.qmd` SHALL be copied from package preset
- AND `templates/references.bib` SHALL be copied from package preset
- AND `templates/preset.yaml` SHALL be copied from package preset

#### Scenario: Doctor resolves assets from installed package
- GIVEN project at `/tmp/my-paper` with no `styles/` or `templates/journals/` directories
- WHEN `paper -C /tmp/my-paper doctor` runs
- THEN Vale styles SHALL be resolved from installed package via `get_project_asset()`
- AND CSL styles SHALL be resolved from installed package
- AND journal presets SHALL be resolved from installed package

---

## MODIFIED: cli-search-provider-compatibility

### Requirement: CLI search query forwarding

The CLI MUST accept an optional `--query` flag for `paper search`. When the user omits `--query`, the CLI MUST still preserve the existing no-argument workflow by forwarding a deterministic non-empty default query to the orchestrator.

(Previously: `paper search` forwarded no query, causing provider-backed search to fail on empty-query validation.)

#### Scenario: Explicit query is forwarded
- GIVEN the user runs `paper search --query "voice disorders"`
- WHEN the CLI builds the orchestrator request
- THEN `request.args["query"]` MUST equal `"voice disorders"`

#### Scenario: No query still produces a non-empty request
- GIVEN the user runs `paper search`
- WHEN the CLI builds the orchestrator request
- THEN `request.args["query"]` MUST be present
- AND it MUST be non-empty

### Requirement: CLI search backward-compatible execution

The system MUST keep `paper search` operational in fixture/provider mode when the user does not supply `--raw-papers`.

(Previously: provider-backed search received `""`, failed validation, and never wrote `search_plan.json`.)

#### Scenario: No-arg search creates required artifacts
- GIVEN an initialized project
- WHEN the user runs `paper search`
- THEN the command MUST exit with code `0`
- AND `outputs/latest/search/search_plan.json` MUST exist
- AND `outputs/latest/search/raw_results.json` MUST exist

### Requirement: Chain CLI subprocess test environment

CLI E2E subprocess tests MUST pass the repository `PYTHONPATH` when invoking `python -m cli.paper.main` from a temporary project directory.

(Previously: `test_cli_chain_with_custom_args` invoked the module without `PYTHONPATH`, producing `ModuleNotFoundError`.)

#### Scenario: Chain subprocess inherits module path
- GIVEN a temp project outside the repo root
- WHEN the E2E test invokes `python -m cli.paper.main chain`
- THEN the subprocess MUST receive `PYTHONPATH=<repo_root>`
- AND the command MUST be able to import `cli.paper.main`
