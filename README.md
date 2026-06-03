# paper-writer

A dedicated repository for automated scientific search, drafting, validation, and rendering.

## Current Status

Repository evidence supports controlled validation workflows. Live operational status still requires re-verification in the target environment.

### Installation

```bash
# From source (development)
git clone <repo-url> && cd paper-writer
uv sync --dev

# As a tool (end-user)
uv tool install paper-writer
# or from a built wheel:
uv tool install ./dist/paper_writer-0.1.0-py3-none-any.whl

# Verify
paper --help
paper doctor
```

### Optional: Trifecta Integration (code traceability, dead code detection)

paper-writer can use [Trifecta](https://github.com/fegome90-cmd/trifecta_dope)
as an **optional external dependency** to power these commands:

- `paper audit code-health` — find dead code / orphan methods
- `paper trace <symbol>` — find callers, callees, call paths
- `paper graph-overview` — show code graph health summary

**Trifecta is NOT required.** By default, `MCP_TRIFECTA_MODE=off` and these
commands show a "Trifecta not enabled" message. Install Trifecta only if you
need code-traceability features.

**Install Trifecta** (separate repo, not bundled with paper-writer):

```bash
# Clone the Trifecta repository
git clone https://github.com/fegome90-cmd/trifecta_dope.git
cd trifecta_dope

# Install (editable or as tool)
uv sync
# or: uv tool install .

# Verify Trifecta is on PATH
which trifecta
trifecta --help
```

**Enable Trifecta in paper-writer**:

```bash
# Per-command
MCP_TRIFECTA_MODE=real paper audit code-health

# Or export for the session
export MCP_TRIFECTA_MODE=real
paper audit code-health
```

See `docs/integration/TRIFECTA_NEXT_STEPS.md` for the integration plan
and `docs/integration/trifecta-bench-results.md` for benchmark results.

### Quick Start

```bash
# Create a new paper project
mkdir my-paper && cd my-paper
paper init

# Or use --project/-C to run from anywhere
paper -C /path/to/my-paper init

# Full pipeline
paper search && paper screen
paper draft outline
paper draft section introduction
paper draft section methods
paper draft section results
paper draft section discussion

# Validate
paper audit prose outputs/drafts/introduction.md
paper audit claims outputs/drafts/introduction.md
paper audit citations outputs/drafts/manuscript.md --offline
paper audit ethics outputs/drafts/manuscript.md
paper audit writing-quality outputs/drafts/manuscript.md
paper gate method outputs/drafts/introduction.md --study-type rct
```

### Verification Evidence

- Repository-audited command surface includes orchestrated commands such as `init`, `search`, `screen`, `draft`, `lint`, `check refs`, `audit reporting`, `import bib`, `render`, `verify`, plus direct commands such as `doctor`, `audit prose`, `audit claims`, and `gate method`.
- Test files in `tests/cli/`, `tests/harness/`, `tests/integrations/`, `tests/skills/`, and `tests/e2e/` provide repository evidence for CLI mapping, orchestrator flow, degraded mode, Pandoc wrapper behavior, adapter behavior, and subprocess smoke coverage.
- Full pipeline coverage is documented in tests for `init -> import bib -> search -> screen -> draft -> validate -> render -> verify`.
- `tests/e2e/test_smoke_e2e.py` verifies real DOCX generation when Pandoc is available.
- Current aggregate test counts, current CI status, and current lint/typecheck cleanliness require re-verification before being treated as live status.

The repository has:

- a thin `paper` CLI in `cli/paper/main.py`
- a harness centered on `harness/domain/state.py`, `harness/services/gates.py`, `harness/services/orchestrator.py`, and `harness/services/orchestrator_builder.py`
- orchestrated workflow commands for `init`, `search`, `screen`, `draft`, `lint`, `check refs`, `audit reporting`, `import bib`, `render`, and `verify`
- direct CLI commands for `doctor`, `audit prose`, `audit claims`, `audit citations`, `audit ethics`, `audit writing-quality`, `audit code-health`, `gate method`, `trace`, and `graph-overview`
- fail-closed required gates plus soft warning-only gates in the manuscript state model
- render argument forwarding for multi-format output plus optional `--csl` and `--reference-doc`
- `paper doctor` environment reporting with explicit degraded-mode output
- repository-documented CI in `.github/workflows/ci.yml`; current run status still requires re-verification

## Phase Status

Repository-documented phase history. Preserved here as project context; not re-verified in this audit pass.

### Completed

- **Phase 1** — Repository Base (hexagonal harness, CLI, state machine, gates)
- **Phase 2** — Harness and Verification (domain validators, Pandoc render, assembler)
- **Phase 3** — Domain Skill Integration (real imports, manifest-driven adapters)
- **Phase 4** — Editorial Gates and Hardening (style rules, bib normalization, ref validation, presets, multi-output render, Zotero)
- **Phase 5** — Controlled Validation Readiness (E2E smoke, CI, degraded mode, render verification, operational docs)

### Optional Next Phase

- **Phase 6** — Real Material Validation (opt-in, local-only, non-CI)
  - uses real source documents without committing them to the repository
  - runs from `verification/` manifests and local gitignored inputs
  - adds manual-review evidence on top of automated gates

## Quick Start

```bash
# Install dependencies
uv sync --dev

# Initialize a project
paper init

# Import bibliography
paper import bib references.bib

# Optional direct audits
paper audit prose outputs/drafts/introduction.md
paper audit claims outputs/drafts/introduction.md
paper audit citations outputs/drafts/manuscript.md --offline
paper audit ethics outputs/drafts/manuscript.md
paper audit writing-quality outputs/drafts/manuscript.md
paper gate method outputs/drafts/introduction.md --study-type rct

# Run pipeline
paper search
paper screen
paper draft outline
paper draft section introduction
paper draft section methods
paper draft section results
paper draft section discussion
paper check refs
paper lint bib
paper lint style
paper audit reporting
paper render --format docx
paper verify

# Check environment
paper doctor

# Verify all
make verify
```

## Documentation

| Document | Purpose |
|----------|---------|
| `TECHNICAL_BOOTSTRAP.md` | Import plan, construction order, phase status |
| `AGENTS.md` | Operational rules for the agent |
| `docs/REPO_ARCHITECTURE.md` | Repository layout, dependency direction, runtime diagram |
| `docs/HARNESS_AND_STATE_MACHINE.md` | Workflow stages, gates, state schema |
| `docs/ORCHESTRATOR_SPEC.md` | Orchestrator contract, failure policies |
| `docs/SKILL_ADAPTERS_SPEC.md` | Adapter provenance, command mapping, wiring |
| `docs/GATE_SYSTEM.md` | Gate catalog, fail-closed rules, reset semantics |
| `docs/STATE_MANAGER_SPEC.md` | State persistence, schema validation |
| `docs/MANIFEST_SPEC.md` | Delivery manifest schema |
| `docs/VALIDATOR_CONTRACTS.md` | Validator inputs, outputs, severities |
| `docs/TESTING_STRATEGY.md` | Testing approach and coverage |
| `docs/PRODUCTION_READINESS.md` | Operational criteria, degraded mode, CI |
| `verification/REAL_MATERIAL_VALIDATION.md` | Local-only validation with real source material |

## Principle

The system is not an autonomous paper writer.
It is an agent constrained by editorial CI.
