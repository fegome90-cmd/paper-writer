# paper-writer — Project Context

## Overview

Automated scientific paper pipeline: literature search, screening, drafting, validation, and multi-format rendering. The system is NOT an autonomous paper writer — it is an agent constrained by editorial CI (fail-closed gates). Every claim must have traceable evidence or be marked as hypothesis.

## Tech Stack

- **Language**: Python 3.10+
- **Package manager**: uv
- **CLI**: argparse (`paper` command via `cli/paper/main.py`)
- **Entry point**: `paper = cli.paper.main:main` (pyproject.toml)
- **Linting**: ruff (line-length 100, rules: E/F/I/N/UP/B/C4/RUF)
- **Type checking**: mypy (strict, `ignore_missing_imports=true`)
- **Testing**: pytest 8+ (markers: `e2e`, `integration`)
- **Rendering**: Pandoc (external tool, DOCX/PDF)
- **Style linting**: Vale (via `styles/vale/`)
- **External integrations**: Semantic Scholar, Crossref, arXiv, OpenAlex, Zotero, Consensus
- **Optional**: Trifecta (code traceability graph, `MCP_TRIFECTA_MODE=off` by default)

## Project Structure

```
cli/paper/            # Thin CLI entry point and command handlers
  commands/           # audit.py, gate.py, graph.py (direct CLI commands)
harness/              # Core orchestration engine (hexagonal architecture)
  domain/             # ManuscriptState (state machine, stage ordering, required gates)
  ports/              # Abstract interfaces (ActionRunner, ArtifactChecker, SkillAdapter, ToolWrapper, etc.)
  adapters/           # Concrete adapters (filesystem, YAML state, local tool resolver)
  services/           # Orchestrator, StateManager, Gates, Assembler, Doctor
validators/           # Domain validators (prose, claims, citations, ethics, style, method gate, etc.)
integrations/tools/   # Tool wrappers (Pandoc, Vale, Zotero, Consensus, bibtex-tidy, etc.)
clients/              # External API clients (Semantic Scholar, Crossref, arXiv, OpenAlex, Trifecta)
engine/               # Deduplication, formatting, loading
parsers/              # Manuscript parsing, source maps
rules/                # YAML rule definitions (prose, claims, ethics, method gate, writing quality)
schemas/              # JSON schemas (claim audit, finding, method gate, prose audit)
skills/               # Skill adapters and bundles
  imported/           # Vendored skills (academic_writer, literature_search)
  local/              # Local skills (essay_crafter, science-bundle, thesaurus, trifecta-mcp)
templates/            # Manuscript templates (QMD, BibTeX) and journal presets (Nature, Elsevier, Springer)
styles/               # Vale style rules and CSL citation styles
verification/         # Real material validation (local-only, Phase 6)
tests/                # 100+ test files organized by domain (cli, harness, validators, e2e, etc.)
docs/                 # Architecture and spec documents
```

## Development Commands

```bash
# Install
uv sync --dev

# Run tests
uv run pytest                          # All tests
uv run pytest tests/harness/           # Specific module
uv run pytest -m e2e                   # End-to-end tests only

# Lint
uv run ruff check .
uv run ruff format --check .

# Type check (IMPORTANT: do NOT run `mypy .`)
uv run mypy harness/ cli/ validators/ integrations/ verification/ parsers/ engine/ rules/ schemas/ skills/

# Full verification (lint + typecheck + test)
make verify

# One-time repository bootstrap (security, branch rules, environments)
make setup-github

# After a real PR has completed CI, enforce exact required checks
make setup-github-checks

# Smoke test the CLI
uv run paper --help
uv run paper doctor
```

## Key Conventions

### Architecture: Hexagonal (Ports & Adapters)
- **Domain** (`harness/domain/`) has zero infrastructure dependencies
- **Ports** (`harness/ports/`) are abstract interfaces (ABCs)
- **Adapters** (`harness/adapters/`, `integrations/tools/`) implement ports
- The **Orchestrator** depends only on ports, never on concrete implementations
- All tool wrappers return `ValidatorResult`; all skill adapters return `SkillResult`
- Status values are always one of: `pass`, `warn`, `fail`

### State Machine
- Pipeline stages: `bootstrap -> search -> screen -> outline -> drafting -> validating -> rendering -> rendered`
- 12 required gates (e.g. `repo_initialized`, `search_completed`, `style_passed`, `ready_for_delivery`)
- Gates are **fail-closed**: a missing gate blocks progression
- State persisted as `outputs/state.yaml`

### CLI Pattern
- Orchestrated commands (`init`, `search`, `screen`, `draft`, `render`, etc.) go through the Orchestrator
- Direct commands (`audit prose`, `audit claims`, `gate method`, `doctor`, `trace`, etc.) bypass the Orchestrator
- Project root resolved by: `--project/-C` flag > ascending search for `outputs/state.yaml` > CWD

### Coding Style
- PEP 8 with type annotations on all function signatures
- `@dataclass` for DTOs; `@dataclass(frozen=True)` for immutable data where possible
- No `print()` in library code — use `logging` module
- Files should stay under 800 lines; functions under 50 lines

## Gotchas

1. **Never run `mypy .`** — the repo directory name `paper-writer` contains a hyphen, which mypy rejects. Use explicit package list (see typecheck command above).

2. **Thesaurus is lazy-imported** — `skills/local/thesaurus/` is excluded from `setuptools.packages.find`. It has its own `pyproject.toml` and `uv.lock`. Import errors are caught at CLI startup and produce a graceful "not installed" message.

3. **Trifecta is optional** — `MCP_TRIFECTA_MODE=off` by default. Commands like `paper audit code-health` and `paper trace` show "not enabled" unless the env var is set to `real`.

4. **`_scratch/` and `tools/` are excluded from ruff** — these are scratch space and external tooling, not part of the main codebase.

5. **`.envrc` may contain local secrets** and is gitignored. Create .envrc locally from .env values; never commit secrets.

6. **Test organization mirrors source** — `tests/` has subdirectories matching source modules (`tests/cli/`, `tests/harness/`, `tests/validators/`, etc.). The `tests/harness/mocks.py` file contains shared test doubles.

7. **`outputs/` runtime artifacts are ignored** — only `outputs/review_config.yaml` is tracked as project configuration.

8. **Journal presets** — stored in `templates/journals/<name>/preset.yaml`. Use `paper init --preset nature` to load a preset.

9. **Pipeline state is YAML-based** — `harness/adapters/yaml_repository.py` reads/writes `outputs/state.yaml`. The `StateManager` service mediates all state access.

10. **Gates have soft and hard checks** — soft checks produce warnings but don't block; hard checks block stage progression. See `harness/services/gates.py` and `docs/GATE_SYSTEM.md`.
