# Tasks: multi-project-mode

## Phase 1: Foundation — Project Resolution

- [x] 1.1 Create `resolve_project_root(explicit_path, cwd) -> Path` in `cli/paper/main.py` — flag → ascending innermost search (20 levels) → CWD fallback
- [x] 1.2 Add `get_project_asset(project_root, *path_parts) -> Path` to `harness/ports/assets.py` — project-local first, `get_asset_path()` fallback
- [x] 1.3 Add argparse parent parser with `--project/-C` flag in `cli/paper/main.py`, attach via `parents=[project_parser]` to main parser

## Phase 2: Core — Gate & Init

- [x] 2.1 Update `validate_repo_initialized` in `harness/services/gates.py` — `required_dirs = ["templates", "outputs"]`, add file-check loop for `["outputs/state.yaml"]` using `Path.is_file()` after dir loop (same pattern as `validate_render_completed`)
- [x] 2.2 Remove `"cli"`, `"harness"`, `"validators"`, `"tests"` from init dir list in `harness/adapters/filesystem_action_runner.py` (keep 6 project dirs)
- [x] 2.3 Replace both `Path.cwd()` calls in `cli/paper/main.py` with `resolve_project_root(args.project, Path.cwd())`

## Phase 3: Wiring — Asset Resolution & Downstream

- [x] 3.1 Route `orchestrator.py` lines 436, 456, 482 — replace direct `self.repo_path / "templates/..."` with `get_project_asset()` calls
- [x] 3.2 Route `doctor.py` lines 110, 132, 151 — replace `repo_path / "styles"/"templates"` with `get_project_asset()`, remove `_looks_like_project_root` heuristic (fallback handled by `get_project_asset` internally)
- [x] 3.3 Remove `Path.cwd()` fallback in `orchestrator_builder.py:59` — CLI always provides explicit `project_root`
- [x] 3.4 Remove `Path.cwd()` fallback in `bibtex_tidy.py:238` — use only `context["repo_path"]`
- [x] 3.5 Fix default `target_bib` in `zotero_import.py:127` — if path is absolute use as-is, else resolve relative to project root (not bare string)

## Phase 4: Testing — TDD Strict

- [x] 4.1 RED: Write parametrized unit tests for `resolve_project_root` — flag override, ascending hit, ascending miss, CWD fallback, invalid flag path (exit 1), symlink resolution via Path.resolve()
- [x] 4.2 RED: Write unit tests for `get_project_asset` — project-local hit, package fallback, both miss
- [x] 4.3 RED: Update `tests/harness/test_gates.py` — success with new entries, failure missing templates, failure missing state.yaml, source dirs absent still passes
- [x] 4.4 RED: Write test for init action — verify only 6 project dirs created, no `cli/`/`harness/`/`validators/`/`tests/`
- [x] 4.5 GREEN: Implement changes in Phases 1-3 to make all tests pass
- [x] 4.6 Integration: test full pipeline from lean project dir — `build_orchestrator_dependencies` with tmp_path containing only `outputs/`+`templates/`
- [x] 4.6b Integration: test `doctor` with lean project dir — verify assets resolve from package, not from missing local `styles/` dir
- [x] 4.7 E2E: `paper -C /tmp/test-paper init --preset nature` subprocess test — verify preset from package, lean structure
- [x] 4.8 E2E: ascending search test — create nested tmp_path, run from subdirectory, verify correct root

## Phase 5: Cleanup

- [x] 5.1 Verify `skills/local/adapters.py` defaults still resolve correctly through action runner (no change expected)
- [x] 5.2 Update `docs/MULTI_PROJECT_SPEC.md` — mark B1-B8 as implemented
- [x] 5.3 Run `make verify` — confirm 0 regressions
- [x] 5.4 Fix 6 pre-existing ruff errors (E501, F401, RUF059) discovered during Judgment Day
