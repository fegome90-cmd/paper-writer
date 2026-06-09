# paper-writer

**Scientific manuscript pipeline: search, screen, draft, validate, render.**

```
paper init → search → screen → draft → validate → render → verify
```

`paper-writer` is a command-line tool that guides a scientific manuscript from
literature search through final delivery. It enforces editorial quality at every
stage via a fail-closed gate system — no stage can be entered until its
preconditions are met, and no artifact ships without passing validation.

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Pipeline Stages and Gates](#pipeline-stages-and-gates)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Testing](#testing)
- [Optional Integrations](#optional-integrations)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

- **Literature search** — Semantic Scholar, CrossRef, arXiv, OpenAlex, and
  Consensus APIs with deduplication and relevance scoring
- **Evidence screening** — Tier-based screening (Tier 1 / 2 / 3 / Discard) with
  configurable minimum tier
- **Citation chaining** — Expand corpus via Semantic Scholar forward/backward
  citation graphs
- **Structured drafting** — Outline and section-by-section drafting with
  cross-section context awareness
- **25+ validators** — Prose quality, claim detection, citation verification,
  ethics compliance, AI writing pattern detection, methodological gate
  (EQUATOR-derived checklists), and more
- **Fail-closed gates** — Every pipeline stage requires its precondition gates to
  pass; no skipping, no silent degradation
- **Multi-format rendering** — DOCX and PDF via Pandoc with custom CSL styles
  and reference document templates
- **Hexagonal architecture** — Domain logic has zero infrastructure dependencies;
  all I/O flows through typed ports and adapters
- **MeSH/DeCS thesaurus** — Biomedical concept normalization (optional, lazy-loaded)
- **Trifecta code graph** — Dead code detection and call-graph traceability
  (optional, external)

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | >= 3.10 | Tested through 3.13 |
| [uv](https://docs.astral.sh/uv/) | latest | Package manager (`pip` works too) |
| [Pandoc](https://pandoc.org/) | >= 3.0 | Required for `render`; optional otherwise |
| [Vale](https://vale.sh/) | latest | Optional, for `lint style` |

### API keys (optional)

Set environment variables for search providers that require them:

```bash
export SEMANTIC_SCHOLAR_API_KEY="..."   # Higher rate limits on S2
export CROSSREF_API_KEY="..."           # Polite pool on CrossRef
```

Without API keys, the pipeline still works using public-rate endpoints.

---

## Installation

### From source (development)

```bash
git clone https://github.com/fegome90-cmd/paper-writer.git
cd paper-writer
uv sync --dev
```

### As an end-user tool

```bash
uv tool install paper-writer
# or from a built wheel:
uv tool install ./dist/paper_writer-0.1.0-py3-none-any.whl
```

### Verify installation

```bash
paper --version
paper doctor
```

---

## Quick Start

```bash
# 1. Create a project
mkdir my-paper && cd my-paper
paper init

# 2. Search for literature
paper search --query "machine learning for drug discovery"

# 3. Screen results
paper screen

# 4. Draft the manuscript
paper draft outline
paper draft all              # drafts all sections in dependency order

# 5. Validate
paper lint bib
paper lint style
paper check refs
paper audit reporting

# 6. Render and deliver
paper render --format docx
paper verify
```

### Direct audits (no pipeline state required)

These commands run standalone on any manuscript file:

```bash
paper audit prose manuscript.md
paper audit claims manuscript.md
paper audit citations manuscript.md --offline
paper audit ethics manuscript.md
paper audit writing-quality manuscript.md
paper gate method manuscript.md --study-type rct
```

---

## CLI Reference

### Global options

| Flag | Description |
|---|---|
| `--version`, `-V` | Print version and exit |
| `--project`, `-C` | Project root directory (default: auto-detect by ascending search) |

### Pipeline commands

| Command | Description |
|---|---|
| `paper init` | Initialize project with state file and directory structure |
| `paper search` | Execute literature search across configured providers |
| `paper chain` | Expand corpus via Semantic Scholar citation chaining |
| `paper screen` | Screen search results into an evidence set |
| `paper export-bib` | Export screened papers to BibTeX |
| `paper draft outline` | Generate manuscript outline |
| `paper draft section <name>` | Draft a single section |
| `paper draft all` | Draft all sections in dependency order |
| `paper protocol` | Generate reproducibility protocol from pipeline metadata |
| `paper lint bib` | Lint and normalize `references.bib` |
| `paper lint style` | Lint prose against Vale style rules |
| `paper check refs` | Verify inline citations against bibliography |
| `paper audit reporting` | Audit against reporting checklists |
| `paper import bib <source>` | Import `.bib` from Zotero/Better BibTeX |
| `paper render` | Render final DOCX/PDF via Pandoc |
| `paper verify` | Run full final verification |
| `paper doctor` | Check environment and report tool availability |

### Direct audit commands

| Command | Description |
|---|---|
| `paper audit prose <file>` | Analyze scientific prose quality |
| `paper audit claims <file>` | Detect claim candidates |
| `paper audit citations <file>` | Verify citations against Crossref + Semantic Scholar |
| `paper audit ethics <file>` | Check AI disclosure compliance |
| `paper audit writing-quality <file>` | Detect AI-typical writing patterns |
| `paper audit factuality <file> --evidence <path>` | Check claim-evidence overlap |
| `paper audit tables <draft_dir>` | Validate required tables and figures |
| `paper audit quality-appraisal --evidence <path>` | Score study quality on 5 dimensions |
| `paper audit code-health` | Audit dead code via Trifecta graph |

### Gate commands

| Command | Description |
|---|---|
| `paper gate method <file> --study-type <type>` | Apply EQUATOR-derived checklist gate |

Supported study types: `rct`, `cohort`, `case_control`, `cross_sectional`,
`observational`, `systematic_review`, `meta_analysis`, `scoping_review`,
`literature_review`, `qualitative`, and more.

### Thesaurus commands

| Command | Description |
|---|---|
| `paper thesaurus import <file>` | Import MeSH/DeCS concepts from JSONL |
| `paper thesaurus search <query>` | Search loaded concepts |
| `paper thesaurus list` | List loaded concepts with pagination |
| `paper thesaurus audit` | Show thesaurus audit info |
| `paper thesaurus rebuild` | Rebuild database from JSONL |

### Code graph commands (requires Trifecta)

| Command | Description |
|---|---|
| `paper trace <symbol>` | Trace callers, callees, or call paths |
| `paper graph-overview` | Show graph health summary |

---

## Pipeline Stages and Gates

The manuscript progresses through ordered stages. Each stage has precondition
gates that **must** be `True` before entry. This is enforced at the domain level
— there is no bypass.

```
bootstrap → search → screen → outline → drafting → validating → rendering → rendered
```

### Required gates

| Gate | Set by |
|---|---|
| `repo_initialized` | `paper init` |
| `search_completed` | `paper search` |
| `screened_evidence` | `paper screen` |
| `outline_drafted` | `paper draft outline` |
| `sections_completed` | `paper draft section` (all sections) |
| `bib_normalized` | `paper lint bib` |
| `citations_resolved` | `paper check refs` |
| `refs_validated` | `paper check refs` |
| `style_passed` | `paper lint style` |
| `reporting_passed` | `paper audit reporting` |
| `render_passed` | `paper render` |
| `ready_for_delivery` | `paper verify` |

### Soft gates (warning-only, non-blocking)

| Gate | Set by |
|---|---|
| `citation_verified` | `paper audit citations` |
| `ethics_passed` | `paper audit ethics` |

---

## Architecture

`paper-writer` uses **hexagonal architecture** (ports and adapters) to keep
domain logic free of infrastructure concerns.

```
cli/paper/main.py          ← CLI entry point (argparse)
  │
  ▼
harness/services/
  ├── orchestrator.py       ← Pipeline stage orchestration
  ├── orchestrator_builder.py ← Dependency wiring
  ├── gates.py              ← Gate evaluation engine
  ├── state_manager.py      ← State persistence (YAML-backed)
  ├── assembler.py          ← Manuscript assembly
  └── doctor.py             ← Environment diagnostics
  │
  ▼
harness/domain/state.py     ← ManuscriptState (pure domain, no I/O)
  │
  ▼
harness/ports/              ← Abstract interfaces
  ├── action_runner.py
  ├── artifact_checker.py
  ├── state_repository.py
  ├── skill_adapter.py
  ├── tool_resolver.py
  └── tool_wrapper.py
  │
  ▼
harness/adapters/           ← Concrete implementations
  ├── yaml_repository.py
  ├── filesystem_action_runner.py
  ├── filesystem_artifact_checker.py
  └── local_tool_resolver.py
```

### Key packages

| Package | Purpose |
|---|---|
| `validators/` | 25+ domain validators (prose, claims, citations, ethics, ...) |
| `clients/` | External API clients (Semantic Scholar, CrossRef, arXiv, OpenAlex, Zotero) |
| `integrations/tools/` | Tool wrappers (Pandoc, Vale, BibTeX tidy, consensus) |
| `engine/` | Deduplication, formatting, artifact loading |
| `parsers/` | Manuscript parsing and source mapping |
| `rules/` | Validation rule definitions |
| `schemas/` | Shared data schemas |
| `skills/` | Pluggable skill adapters |
| `templates/` | Journal presets (Nature, Elsevier, Springer) |
| `styles/` | CSL citation styles, Vale prose rules |

---

## Configuration

### Project initialization

```bash
# Default (rapid mode)
paper init

# With a journal preset
paper init --preset nature

# Academic mode with search window
paper init --mode academic --search-window-start 2018 --search-window-end 2024
```

### Review modes

| Mode | Behavior |
|---|---|
| `rapid` | Fast validation with essential checks (default) |
| `academic` | Full evidence curation with extended search filters |

### Search filters

The `paper search` command supports fine-grained academic filters:

```bash
paper search \
  --query "systematic review of ML in healthcare" \
  --year-min 2020 \
  --year-max 2025 \
  --study-types rct "systematic review" \
  --human \
  --sample-size-min 50 \
  --sjr-max 2 \
  --exclude-preprints \
  --medical-mode
```

### Rendering options

```bash
# Default: DOCX + PDF
paper render

# Specific format with custom style
paper render --format docx --csl styles/csl/vancouver.csl

# With reference document template
paper render --format docx --reference-doc templates/nature.docx
```

### Environment variables

| Variable | Description |
|---|---|
| `SEMANTIC_SCHOLAR_API_KEY` | API key for Semantic Scholar (higher rate limits) |
| `CROSSREF_API_KEY` | API key for CrossRef (polite pool) |
| `PAPER_SCREEN_MIN_TIER` | Default minimum tier for `paper screen` |
| `MCP_TRIFECTA_MODE` | Set to `real` to enable Trifecta integration |

---

## Testing

```bash
# Run all tests
uv run pytest

# Unit + integration tests only (skip E2E)
uv run pytest tests/ -m "not e2e"

# E2E smoke tests (requires Pandoc)
uv run pytest tests/e2e/ -m e2e

# With coverage
uv run pytest --cov=. --cov-report=term-missing

# Lint + typecheck + test (full verify)
make verify
```

### Test markers

| Marker | Purpose |
|---|---|
| `e2e` | End-to-end smoke tests (subprocess, real I/O) |
| `integration` | Integration tests with real adapters |

### CI

GitHub Actions runs on every push and PR to `main`:

- **Lint** — `ruff check`
- **Typecheck** — `mypy` (strict mode)
- **Unit + integration tests** — Python 3.10, 3.11, 3.12, 3.13
- **E2E smoke tests** — With Pandoc installed

---

## Optional Integrations

### Trifecta (code traceability)

[Trifecta](https://github.com/fegome90-cmd/trifecta_dope) is an optional
external tool for code-graph analysis. It powers:

- `paper audit code-health` — find dead code / orphan methods
- `paper trace <symbol>` — find callers, callees, call paths
- `paper graph-overview` — show code graph health summary

**Not installed by default.** Enable with:

```bash
export MCP_TRIFECTA_MODE=real
paper audit code-health
```

### MeSH/DeCS Thesaurus (biomedical concepts)

The thesaurus module provides biomedical concept normalization against MeSH and
DeCS vocabularies. It is lazy-loaded and only required for medical-domain
projects.

Install separately:

```bash
cd skills/local/thesaurus && uv pip install -e .
```

---

## Documentation

| Document | Purpose |
|---|---|
| [REPO_ARCHITECTURE](docs/REPO_ARCHITECTURE.md) | Repository layout, dependency direction, runtime diagram |
| [HARNESS_AND_STATE_MACHINE](docs/HARNESS_AND_STATE_MACHINE.md) | Workflow stages, gates, state schema |
| [ORCHESTRATOR_SPEC](docs/ORCHESTRATOR_SPEC.md) | Orchestrator contract, failure policies |
| [GATE_SYSTEM](docs/GATE_SYSTEM.md) | Gate catalog, fail-closed rules, reset semantics |
| [STATE_MANAGER_SPEC](docs/STATE_MANAGER_SPEC.md) | State persistence, schema validation |
| [VALIDATOR_CONTRACTS](docs/VALIDATOR_CONTRACTS.md) | Validator inputs, outputs, severities |
| [SKILL_ADAPTERS_SPEC](docs/SKILL_ADAPTERS_SPEC.md) | Adapter provenance, command mapping |
| [TESTING_STRATEGY](docs/TESTING_STRATEGY.md) | Testing approach and coverage targets |
| [PRODUCTION_READINESS](docs/PRODUCTION_READINESS.md) | Operational criteria, degraded mode |
| [TECHNICAL_BOOTSTRAP](TECHNICAL_BOOTSTRAP.md) | Construction order, phase history |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make changes with tests
4. Run `make verify` — lint, typecheck, and all tests must pass
5. Open a pull request against `main`

### Code style

- **Formatter**: `ruff format` (100-char line length)
- **Linter**: `ruff check` with rules `E, F, I, N, UP, B, C4, RUF`
- **Types**: `mypy --strict` on all packages
- **Commits**: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, etc.)

---

## Troubleshooting

### `paper doctor` reports degraded mode

Run `paper doctor` to check which tools are available. Missing Pandoc or Vale
will be reported. Install them with your system package manager.

### `mypy` fails with package name error

The repo directory `paper-writer` contains a hyphen. Run mypy with explicit
package paths instead of `.`:

```bash
mypy harness/ cli/ validators/ integrations/ verification/ parsers/ engine/ rules/ schemas/ skills/
```

### Thesaurus commands fail with "module not installed"

The thesaurus is a lazy-loaded optional module. Install it separately:

```bash
cd skills/local/thesaurus && uv pip install -e .
```

### Trifecta commands show "not enabled"

Set the environment variable:

```bash
export MCP_TRIFECTA_MODE=real
```

### Pipeline blocked at a stage

Check which gates are not yet passed:

```bash
cat outputs/state.yaml
```

Run the commands that set the missing gates (see
[Pipeline Stages and Gates](#pipeline-stages-and-gates)).

---

## License

This project is licensed under the terms found in `pyproject.toml`.
