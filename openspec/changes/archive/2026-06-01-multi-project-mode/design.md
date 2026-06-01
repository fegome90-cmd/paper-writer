# Design: multi-project-mode

## Technical Approach

Add a project-root resolution layer between CLI argparse and orchestrator construction. The resolution algorithm (explicit flag → ascending search → CWD fallback) runs once at CLI entry, producing a single `project_root: Path` passed downstream. All downstream components (`orchestrator_builder`, `action_runner`, `gates`) already accept `project_root` as a parameter — no interface changes needed below the CLI layer. The gate check and init scaffolding are tightened to remove source-code assumptions. Asset resolver gets a project-local override function.

## Architecture Decisions

### Decision: Global flag via argparse parent parser

**Choice**: Add `--project/-C` to a parent parser shared by all subcommands via `parents=[project_parser]`.
**Alternatives**: (1) `PAPER_PROJECT` env var — hidden, not discoverable. (2) Per-subcommand flag — repetitive, error-prone.
**Rationale**: argparse parent parsers propagate global flags to all subcommands without duplication. Same pattern as `git -C`.

### Decision: Innermost match for ascending search

**Choice**: Return immediately on first `outputs/state.yaml` found ascending from CWD. Use `Path.resolve()` on each candidate to resolve symlinks before checking existence.
**Alternatives**: (1) Outermost match — surprising when nested projects exist. (2) `.paper-root` marker file — adds complexity, deferred. (3) No symlink resolution — vulnerable to symlink injection.
**Rationale**: Matches git behavior (innermost `.git`). Symlink resolution prevents an attacker from placing a symlink at an ancestor that points outside the user's tree. `Path.resolve()` is sufficient — no need for `Path.lstat()` since we resolve before matching.

### Decision: Asset waterfall as a new function, not replacing existing

**Choice**: Add `get_project_asset(project_root, *path_parts) -> Path` alongside existing `get_asset_path()`.
**Alternatives**: Modify `get_asset_path()` to accept optional `project_root` — breaks callers that don't have it.
**Rationale**: Existing `get_asset_path()` is used in tests and doctor.py without project context. New function coexists. Callers opt-in when they have a project root.

### Decision: Gate check uses files, not just dirs

**Choice**: `validate_repo_initialized` checks `templates/` (dir), `outputs/` (dir), `outputs/state.yaml` (file).
**Alternatives**: Check only directories — misses case where init failed partway.
**Rationale**: `state.yaml` is the real signal that init completed. Dirs alone could be left over from a failed init.

### Decision: No `.git`-like marker file for v1

**Choice**: Use `outputs/state.yaml` as the sole project marker.
**Alternatives**: Add `.paper-root` marker — more robust but adds scope.
**Rationale**: `state.yaml` already exists and is the SSOT. Marker file is an enhancement, not a requirement. Deferred.

## Data Flow

```
CLI parse args
     │
     ▼
resolve_project_root(flag, cwd)
     │
     ├── flag provided? → validate path, return it
     ├── ascending search finds state.yaml? → return innermost match
     └── fallback → return cwd
     │
     ▼
project_root: Path
     │
     ├──→ build_orchestrator_dependencies(project_root)
     │         ├── YamlFileStateRepository(project_root / "outputs" / "state.yaml")
     │         ├── FilesystemArtifactChecker(project_root)
     │         └── FilesystemActionRunner(project_root)
     │
     ├──→ doctor: check_internal_capabilities(project_root)
     │         ├── project_root / "styles" / "vale" / ...  (first)
     │         └── get_vale_styles_dir() / ...              (fallback)
     │
     └──→ init: create dirs under project_root only
               templates/, outputs/, outputs/search/, ...
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `cli/paper/main.py` | Modify | Add parent parser with `--project/-C`. Replace both `Path.cwd()` with `resolve_project_root()`. Pass resolved path to builder and doctor. |
| `harness/services/gates.py` | Modify | `validate_repo_initialized`: change `required_dirs` to `["templates", "outputs"]`, add `state.yaml` file check. |
| `harness/adapters/filesystem_action_runner.py` | Modify | Remove `"cli"`, `"harness"`, `"validators"`, `"tests"` from init dir list. |
| `harness/ports/assets.py` | Modify | Add `get_project_asset(project_root, *path_parts)` function with waterfall logic. |
| `harness/services/orchestrator.py` | Modify | Lines 436, 456, 482: route template/bib lookups through `get_project_asset()` when project root available. |
| `harness/services/doctor.py` | Modify | Lines 110, 132, 151: use `get_project_asset()` instead of direct `repo_path / ...` construction. Remove `_looks_like_project_root` heuristic — `get_project_asset()` handles fallback internally. |
| `harness/services/orchestrator_builder.py` | Modify | Remove `Path.cwd()` fallback — CLI always provides explicit `project_root`. |
| `integrations/tools/bibtex_tidy.py` | Modify | Line 238: remove `Path.cwd()` fallback, use `context["repo_path"]` only. |
| `integrations/tools/zotero_import.py` | Modify | Line 127: resolve `target_bib` using `Path(target_bib) if Path(target_bib).is_absolute() else project_root / target_bib`, not bare relative string. |
| `skills/local/adapters.py` | Modify | Default paths use project-root-relative strings (already correct — resolved by action runner). No code change, just verify. |
| `tests/harness/test_gates.py` | Modify | Update `test_validate_repo_initialized_success` and `_fail` to use new required entries. |
| `tests/harness/test_orchestrator.py` | Modify | Update init test expectations (no cli/harness/validators dirs). |
| `tests/e2e/test_smoke_e2e.py` | Modify | Add multi-project E2E test: init in temp dir, verify lean structure, run full pipeline. |
| `docs/MULTI_PROJECT_SPEC.md` | Modify | Mark BLOCKER items as implemented after each. |

## Interfaces / Contracts

### New: `resolve_project_root()`

```python
# In cli/paper/main.py (or extracted to harness/ports/project.py)
def resolve_project_root(explicit_path: Path | None, cwd: Path) -> Path:
    """Resolve project root. Priority: flag → ascending search → CWD.
    
    Ascending search resolves symlinks via Path.resolve() before
    checking for outputs/state.yaml to prevent symlink injection.
    """
```

### New: `get_project_asset()`

```python
# In harness/ports/assets.py
def get_project_asset(project_root: Path, *path_parts: str) -> Path:
    """Resolve asset with project-local → package waterfall.

    1. project_root / path_parts → if exists, return it
    2. get_asset_path(*path_parts) → fallback to package
    """
```

### Modified: `validate_repo_initialized()`

```python
# harness/services/gates.py — current vs new
required_dirs = ["templates", "outputs"]  # was: ["cli", "harness", "validators", "templates", "outputs"]
required_files = ["outputs/state.yaml"]   # new addition

# Implementation: add a second loop after dir checks for file existence.
# Uses checker.get_full_path_str() + Path.is_file(), same pattern as
# validate_render_completed checks for output artifacts.
```

### Modified: init directory list

```python
# harness/adapters/filesystem_action_runner.py — current vs new
dirs = [
    "templates", "outputs",
    "outputs/search", "outputs/drafts", "outputs/render", "outputs/logs",
]
# removed: "cli", "harness", "validators", "tests"
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `resolve_project_root()` — flag, ascending, CWD fallback, edge cases | Parametrized pytest with tmp_path hierarchy |
| Unit | `get_project_asset()` — project-local hit, package fallback, both miss | Mock package root, use tmp_path for project |
| Unit | `validate_repo_initialized` — new required entries, missing templates, missing state.yaml | Update existing `InMemoryArtifactChecker` tests |
| Unit | Init dir creation — only project dirs created, no source stubs | Assert dirs exist/not-exist after init action |
| Integration | Full pipeline from lean project dir — init → render via `build_orchestrator_dependencies` | tmp_path with only outputs/templates, run orchestrator |
| E2E | `paper -C /tmp/paper init --preset nature` from outside project | Subprocess test, verify preset copied from package |
| E2E | Ascending search from subdirectory | Create nested tmp_path, verify correct root resolved |

## Migration / Rollout

No migration required. Backward compatible: existing users in source tree get CWD fallback. Gate check change is additive (removes requirements, doesn't add new ones). Init output changes silently — no `cli/`/`harness/` stubs created.

One known breakage: any script that asserts `cli/` or `harness/` exist after `paper init` will fail. This is intentional — those stubs were never meant to be used.

## Open Questions

None. All decisions resolved during exploration and proposal phases.
