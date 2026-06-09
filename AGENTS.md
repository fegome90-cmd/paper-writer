# AGENTS.md

Repository-level instructions for Codex in `/Users/felipe_gonzalez/Developer/paper-writer`.

## Purpose

- Keep repo-specific guidance SHORT, concrete, and verifiable.
- Treat code, Makefile targets, and maintained docs as the source of truth.

## Verified Commands

Verified in this repo on 2026-06-09:

- Setup dev env: `make init`
- Run tests: `make test`
- Lint: `make lint`
- Type-check: `make typecheck`
- Full verification: `make verify`
- Real-material validation: `make validate CASE=verification/local-data/<case>.local.yaml`
- CLI help from source: `python3 -m cli.paper.main --help`

## Working Rules

- Every technical claim needs traceable evidence or must be marked as a hypothesis.
- Method gates are fail-closed.
- Orchestrator work must go through ToolWrapper ports; do not bypass them with direct subprocess orchestration.
- Tool wrappers must return `ValidatorResult`.
- No change is complete without execution evidence from the relevant command.
- If docs and code disagree, trust the current code and Makefile first, then fix or flag the doc drift.
- Prefer the narrowest validation that proves the change; use `make verify` for cross-cutting work.

## Repo-Specific Guidance

- For CLI behavior and command surface, check `docs/tools/paper-cli.md` and `cli/paper/main.py`.
- For testing expectations and scope, check `docs/TESTING_STRATEGY.md`.
- For gate behavior, check `docs/GATE_SYSTEM.md`.
- For Trifecta usage, read `docs/trifecta-mcp-agent-guide.md` and use the exact tool needed (`callers`, `ast_hover`, etc.), not a generic one-tool fallback.
- Do not rely on stale bootstrap commands documented elsewhere unless they also exist in the current `Makefile` or codebase.

## Local Skills

- `skills/local/trifecta-mcp/SKILL.md`
- `skills/local/essay_crafter/SKILL.md`
- `.gemini/skills/autoresearch/SKILL.md`

## References

- `README.md`
- `Makefile`
- `pyproject.toml`
