# Proposal: multi-project-mode

## Intent

paper-writer requires `Path.cwd()` as project root in 3 files at 4 call sites. The system conflates "source code repo" with "user paper project" — `validate_repo_initialized` checks for source directories (`cli/`, `harness/`, `validators/`), and `paper init` creates empty stubs of those directories to pass the gate. Users must clone the entire repo for each paper, duplicating engine code, tests, and skills.

## Scope

### In Scope
- Add `--project/-C` global flag to CLI with git-like ascending search for `outputs/state.yaml`
- Update `validate_repo_initialized` gate to check project dirs only (`templates/`, `outputs/`, `outputs/state.yaml`)
- Remove source-code stubs from `paper init` (`cli/`, `harness/`, `validators/`, `tests/`)
- Extend `harness/ports/assets.py` with project-local fallback
- Route `orchestrator.py` and `doctor.py` template/style lookups through asset resolver
- Fix `orchestrator_builder.py` and `bibtex_tidy.py` `Path.cwd()` fallbacks
- Update existing tests for new gate checks
- Add multi-project E2E tests

### Out of Scope
- `.paper-root` marker file (future enhancement for unambiguous detection)
- `uv tool install` packaging (works already, not a code change)
- Coverage tool installation (separate concern)
- Phase 6 real material validation
- Renaming `paper` CLI to something else

## Capabilities

### New Capabilities
- `project-resolution`: resolving project root via `--project` flag or ascending `state.yaml` search

### Modified Capabilities
- `repo-initialization-gate`: gate checks project structure, not source structure
- `asset-resolution`: dual waterfall (project-local → package fallback) instead of package-only
- `cli-entrypoint`: global `--project/-C` flag before subcommands
- `init-directory-creation`: lean scaffolding without source-code stubs

## Approach

Resolution priority: explicit flag → ascending innermost search → CWD fallback (backward compatible). Gate change removes source-code assertions. Asset resolver extends existing `importlib.resources` with project-local override. 8 BLOCKER items implemented sequentially, tests updated alongside.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `cli/paper/main.py` | Modified | Add `--project/-C` flag, resolve project root |
| `harness/services/gates.py` | Modified | `validate_repo_initialized` checks 3 entries, not 5 |
| `harness/adapters/filesystem_action_runner.py` | Modified | Remove 4 source stubs from init |
| `harness/ports/assets.py` | Modified | Add project-local fallback to asset resolution |
| `harness/services/orchestrator.py` | Modified | Route template lookup through asset resolver |
| `harness/services/doctor.py` | Modified | Route style/template lookups through asset resolver |
| `harness/services/orchestrator_builder.py` | Modified | Accept project_root from caller, remove Path.cwd() |
| `integrations/tools/bibtex_tidy.py` | Modified | Remove Path.cwd() fallback |
| `integrations/tools/zotero_import.py` | Modified | Default target_bib relative to project root |
| `skills/local/adapters.py` | Modified | Default paths relative to project root |
| `tests/` | Modified | Update gate tests, add project-resolution tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Existing gate tests break on new required_dirs | High | Update tests alongside B2, not after |
| Asset resolution differs between source tree and installed package | Medium | Add packaging contract test for both modes |
| Ascending search matches wrong project in nested dirs | Low | Innermost match stops immediately |
| `paper init` change breaks existing workflows | Low | CWD fallback unchanged, only stubs removed |

## Rollback Plan

All changes are in-tree, no schema migrations. Revert commits to restore old gate checks, init stubs, and Path.cwd() behavior. State files (`outputs/state.yaml`) are unaffected — same schema.

## Dependencies

- No external dependencies
- Requires understanding of existing gate system, asset resolver, and CLI structure (already explored)

## Success Criteria

- [ ] `paper -C /tmp/my-paper init` works from any directory
- [ ] `paper init` in empty dir creates only `templates/`, `outputs/`, `outputs/state.yaml`
- [ ] `paper init` does NOT create `cli/`, `harness/`, `validators/`, `tests/`
- [ ] `paper -C /tmp/my-paper init --preset nature` resolves preset from installed package
- [ ] Ascending search finds `outputs/state.yaml` from subdirectory
- [ ] All existing tests pass (updated, not broken)
- [ ] New multi-project E2E test covers: init → search → render from lean project dir
- [ ] `make verify` passes
