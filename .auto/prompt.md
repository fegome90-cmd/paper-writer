# Autoresearch: paper CLI structural refactoring (PR1)

## Objective

Slim the 1201-line monolithic `cli/paper/main.py` into focused modules per SDD change `cli-structural-refactoring` (PR1 only). Pure structural extraction — argparse stays, no new dependencies, no Typer/Rich. Each iteration extracts one concern END-TO-END: create the target module, remove the code from `main.py`, re-wire imports, verify.

**Source of truth**: `openspec/changes/cli-modernization-typer-rich/{proposal,spec,design,tasks}.md`. Read `tasks.md` for the per-PR task list. This prompt governs EXECUTION discipline; the SDD docs govern WHAT.

## Metrics

- **Primary**: `main_py_lines` (lower is better) — lines in `cli/paper/main.py`. Baseline ~1218. Target < 100 by end of PR1.
- **Secondary**: `cli_module_count` (higher — more decomposition), `test_failures` (lower — must stay at baseline), `import_time_ms` (lower, < 50ms budget), `lint_errors_new` (new files only, must be 0).

## How to Run

`./.auto/measure.sh` — outputs `METRIC name=value` lines.

## PR1 Scope (from tasks.md P1.1–P1.11)

Extractions, each a complete iteration:
1. **project.py** — `resolve_project_root` + `MAX_ASCENDING_DEPTH` (ALREADY CREATED in P1.1, needs WIRING: remove from main.py)
2. **parser.py** — all argparse construction + `_get_version`
3. **commands/zotero.py** — 8 Zotero handlers + `_zotero_client` + `register_zotero`
4. **commands/thesaurus.py** — lazy import + `register_thesaurus`
5. **commands/mesh.py** — lazy import + `register_mesh` (dest="subcommand")
6. **commands/doctor.py** — `_cmd_doctor` with lazy imports + `--live`/`--live-search-probe` preservation
7. **dispatch.py** — `PipelineInvocation` + `PipelineSpec` + `PIPELINE_MAP` + `execute` + `_run_callback` + `_make_key` + `_inject_review_config` + `_print_summary`
8. **main.py slim** — <100 lines, re-export resolve_project_root/MAX_ASCENDING_DEPTH from project.py, `_get_version` from parser.py, KeyboardInterrupt → exit 130
9. **Monkeypatch migration** — `tests/cli/test_cli_request_mapping.py` + `test_paper_cli.py` targets → `cli.paper.dispatch.*`
10. **New PR1 tests** — cycle, reexport contract, dispatch completeness, audit:ethics single path, import:bib routing, import budget, thesaurus/mesh fallback install instructions

## PR1 Hard Constraints (per per-sprint state matrix)

- NO `errors.py`, `output.py`, `runtime.py` — those are PR2/PR3
- `project.py` keeps `SystemExit(1)` (migrates to UserInputError in PR2)
- NO `clean_cancel` metadata (PR3)
- NO `OutputConfig`, exit-code taxonomy 2/3 (PR2)
- `audit:ethics` MUST NOT enter PIPELINE_MAP (it's a Phase 0 callback — dead pipeline branch deleted)
- `_cmd_trace` already lives in `commands/graph.py` — no extraction needed
- `make test` / `make lint` / `make typecheck` must stay green (baseline: 1 pre-existing fail in `test_zotero_real.py` requiring local Zotero; 5 pre-existing lint errors in other files)

## Off Limits

- `harness/`, `clients/`, `validators/`, `engine/`, `parsers/`, `schemas/`, `rules/` — no domain changes
- `Orchestrator`/`OrchestratorRequest`/`OrchestratorResult` schema — unchanged
- Business logic of any handler — extraction only
- The 21 pre-existing uncommitted files in the working tree (NOT mine) — do not sweep into refactor commits

## Commit Discipline

Mirror prior autoresearch pattern: scoped commits with specific file paths (NOT `git add -A`). Each kept iteration = one extraction + its tests, committed with a conventional message. Never bundle the pre-existing dirty files.

## What's Been Tried

- P1.1: `cli/paper/project.py` CREATED (resolve_project_root + MAX_ASCENDING_DEPTH, SystemExit(1) preserved, only pathlib module-scope import). NOT yet wired into main.py — that is iteration 1 of this loop.
