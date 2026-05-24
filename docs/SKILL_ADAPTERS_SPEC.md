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

## Audit Checklist

- [ ] No orchestrator logic depends on physical skill folder layout.
- [ ] Each skill-backed command has an adapter contract.
- [ ] Adapter outputs are normalized and gate-aware.
