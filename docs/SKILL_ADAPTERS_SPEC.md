# paper-writer - Skill Adapters Specification

Defines how imported and local skills are invoked through normalized adapters.

## Quick path

1. The orchestrator never reads skill folders ad hoc.
2. Commands call skill adapters through a stable contract.
3. Adapters translate workflow requests into skill-specific execution.

## Scope

Applies to:
- `skills/imported/*`
- `skills/local/*`
- future adapter modules that bridge skills into the harness

## Why Adapters Exist

Skills are reusable knowledge surfaces.
The harness needs executable contracts.
Adapters provide the missing bridge.

## Canonical Request Contract

```yaml
adapter: literature-search
command: paper search
stage: search
inputs:
  query: voice disorders adolescent singers
  output_dir: outputs/search
context:
  state_file: outputs/state.yaml
```

Required fields:
- `adapter`
- `command`
- `stage`
- `inputs`

## Canonical Result Contract

```yaml
adapter: literature-search
status: pass
summary: Search artifacts created successfully
artifacts:
  - outputs/search/search_plan.json
  - outputs/search/raw_results.json
gate_changes:
  search_completed: true
warnings: []
```

Required fields:
- `adapter`
- `status`
- `summary`
- `artifacts`
- `gate_changes`
- `warnings`

## Command Mapping

| Command | Expected Adapter Surface |
|---|---|
| `paper search` | search/evidence adapter |
| `paper screen` | screening adapter |
| `paper draft outline` | outline/drafting adapter |
| `paper draft section <name>` | section drafting adapter |
| `paper audit reporting` | reporting-audit adapter |

## Rules

- Adapters isolate skill-specific folder structure from the orchestrator.
- Adapters must return normalized results.
- Adapters may call imported or local skills, but the orchestrator only sees the adapter contract.
- Skill adapters do not write workflow state directly; they return `gate_changes` for the orchestrator/state manager to apply.

## Implemented Adapters

### Provenance

| Skill | Source Path | What Was Imported | What Was Adapted |
|---|---|---|---|
| literature-search | `/Users/felipe_gonzalez/Developer/examen_grado/skills/literature-search/` | `resources/scoring.py` vendored as `skills/imported/literature_search/scoring.py` (340+ lines: PaperMetrics, ScoringWeights, deduplicate, classify_tier, calculate_final_score, verify_citation). 6 resource `.md` files vendored. 56 tests vendored. | `search.py` wraps scoring engine for dedup+scoring+tier pipeline. Does NOT call external APIs — an agent following `SKILL.md` must collect papers. |
| academic-writer | `/Users/felipe_gonzalez/Developer/examen_grado/skills/academic-writer/` | `SKILL.md` vendored as `skills/imported/academic_writer/SKILL.md` (prompt collection only — 7 section prompts for Q1 journals). | `drafting.py` extracts section structures (CARS model, CONSORT flow) from prompts. Generates section skeletons, NOT LLM content. For real writing, use the SKILL.md prompts with an LLM. |

**What was NOT imported:**
- `benchmark_dedup.py` — benchmark script
- `autoresearch.*` — experiment tooling
- `_ctx/`, `.atl/`, `.pi/`, `.mypy_cache/` — tool artifacts
- No Python code exists in academic-writer source (it's purely a prompt collection)

### LiteratureSearchAdapter

- **Location**: `skills/local/adapters.py`
- **Wraps**: `skills/imported/literature_search/search.py` using real `scoring.py` engine
- **Adapter name**: `literature-search`

| Command | Input Contract | Output Contract | Gate Change |
|---|---|---|---|
| `search` | `query: str`, `output_dir: str`, `raw_papers: list[dict] | None`, `weights_phase: str` (default `balanced`) | `artifacts`: `[search_plan.json]` (plan only if no papers) or `[search_plan.json, raw_results.json]` (with scored papers), `status: pass` | `search_completed: true` |
| `screen` | `search_dir: str`, `output_dir: str`, `min_tier: str` (default `Tier 3`) | `artifacts`: `[screened_evidence.json]` (filtered by real tier classification), `status: pass` | `screened_evidence: true` |

Error handling: unknown commands return `SkillResult(status="fail")` with error summary and warnings.

### AcademicWriterAdapter

- **Location**: `skills/local/adapters.py`
- **Wraps**: `skills/imported/academic_writer/drafting.py` consuming `sections_manifest.json` (derived from SKILL.md)
- **Adapter name**: `academic-writer`
- **Manifest chain**: SKILL.md (vendored) → sections_manifest.json (derived artifact) → drafting.py (runtime consumer)

| Command | Input Contract | Output Contract | Gate Change |
|---|---|---|---|
| `draft_outline` | `evidence_path: str` (default `outputs/search/screened_evidence.json`), `output_dir: str`, `bib_path: str` | `artifacts`: `[outline.md]`, `status: pass` | `outline_drafted: true` |
| `draft_section` | `section_name: str`, `outline_path: str`, `evidence_path: str`, `bib_path: str`, `output_dir: str` | `artifacts`: `[{section_name}.md]`, `status: pass` | `sections_completed: true` |

Error handling: unknown commands return `SkillResult(status="fail")` with error summary and warnings.

### Adapter Wiring

The invocation path is:

```text
CLI (cli/paper/main.py)
  → harness.ports.action_runner.ActionRunner (filesystem adapter)
    → skills.local.adapters.LiteratureSearchAdapter / AcademicWriterAdapter
      → skills.imported.*.Skill (concrete skill logic)
        → returns SkillResult (normalized)
```

- The CLI remains thin and routes to `ActionRunner`.
- `ActionRunner` delegates to adapter instances registered by command name.
- Adapters translate normalized inputs into skill-specific method calls.
- Skills return raw dicts; adapters wrap them in `SkillResult` with gate changes.
- The orchestrator applies `gate_changes` through `StateManager`, never directly by skills.

## Audit Checklist

- [x] No orchestrator logic depends on physical skill folder layout.
- [x] Each skill-backed command has an adapter contract.
- [x] Adapter outputs are normalized and gate-aware.
