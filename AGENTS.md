# AGENTS.md

Repository-level instructions for Codex in `/Users/felipe_gonzalez/Developer/paper-writer`.

## Purpose

- Keep repo-specific guidance SHORT, concrete, and verifiable.
- Treat code, Makefile targets, and maintained docs as the source of truth.

## Verified Commands

Verified in this repo on 2026-06-11:

- Setup dev env: `make init`
- Run tests: `make test`
- Lint: `make lint`
- Type-check: `make typecheck` (or `uv run mypy harness/ cli/ validators/ integrations/ verification/ parsers/ engine/ rules/ schemas/ skills/`)
- Full verification: `make verify`
- Real-material validation: `make validate CASE=verification/local-data/<case>.local.yaml`
- CLI help: `uv run paper --help` or `uv run paper doctor`
- One-time GitHub bootstrap: `make setup-github`
- Enforce required checks: `make setup-github-checks`

## Working Rules

- Every technical claim needs traceable evidence or must be marked as a hypothesis.
- Method gates are fail-closed.
- Orchestrator work must go through ToolWrapper ports; do not bypass them with direct subprocess orchestration.
- Tool wrappers must return `ValidatorResult`.
- No change is complete without execution evidence from the relevant command.
- If docs and code disagree, trust the current code and Makefile first, then fix or flag the doc drift.
- Prefer the narrowest validation that proves the change; use `make verify` for cross-cutting work.

## Gotchas

1. **Never run `mypy .`** — the repo directory name `paper-writer` contains a hyphen. Use explicit package list. Sub-projects (thesaurus, mesh-import, science-bundle) are excluded from root mypy via `pyproject.toml`.
2. **Thesaurus and mesh-import are separate packages** — each has its own `pyproject.toml`. Install with `uv pip install -e skills/local/thesaurus` before running their tests.
3. **Ruff excludes** — `_scratch/`, `tools/`, and sub-project dirs are excluded from root ruff. Scripts have per-file E501 ignore. Sub-project lint runs with `--config pyproject.toml` from root.
4. **Test markers** — `@pytest.mark.e2e` for Pandoc/render tests, `@pytest.mark.integration` for real adapters. Core tests run with `-m "not e2e"`.
5. **`outputs/` runtime artifacts are ignored** — only `outputs/review_config.yaml` is tracked.
6. **`.envrc` may contain local secrets** — never commit. Track only `.envrc.example`.

## Repo-Specific Guidance

- For CLI behavior and command surface, check `docs/tools/paper-cli.md` and `cli/paper/main.py`.
- For testing expectations and scope, check `docs/TESTING_STRATEGY.md`.
- For gate behavior, check `docs/GATE_SYSTEM.md`.
- For Trifecta usage, read `docs/trifecta-mcp-agent-guide.md` and use the exact tool needed (`callers`, `ast_hover`, etc.), not a generic one-tool fallback.
- Do not rely on stale bootstrap commands documented elsewhere unless they also exist in the current `Makefile` or codebase.
- For full project context, see `CLAUDE.md` (architecture, state machine, coding style, and all gotchas).

## CI/CD

- 7-job CI pipeline: quality, tests-core (3.10/3.12/3.13), local-skills, offline-e2e, build-smoke
- Security: dependency audit (pip-audit), CodeQL, dependency-review on PRs
- Live smoke: manual-only Zotero tests via `live-smoke.yml`
- Release: tag-based (`v*.*.*`) with wheel verification and GitHub Release
- All GitHub Actions pinned to immutable SHA references

## Local Skills

- `skills/local/trifecta-mcp/SKILL.md`
- `skills/local/essay_crafter/SKILL.md`
- `.gemini/skills/autoresearch/SKILL.md`

## References

- `README.md`
- `Makefile`
- `pyproject.toml`
