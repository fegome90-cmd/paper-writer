# paper-writer - Gate System

Defines the workflow gates that block or allow stage progression.

## Quick path

1. Gates are evaluated by `harness/gates.py`.
2. Gates consume validator and wrapper results.
3. The system fails closed when a required gate is not satisfied.

## Gate Result Contract

Conceptual shape:

```yaml
gate: refs_validated
status: fail           # pass | warn | fail
blockers:
  - bibliography entries missing required identifiers
warnings: []
artifacts:
  - templates/references.bib
```

Required fields:
- `gate`
- `status`
- `blockers`
- `warnings`
- `artifacts`

## Gate Catalog

| Gate | Meaning | Typical Source |
|---|---|---|
| `repo_initialized` | Base repo scaffold exists | `paper init` |
| `search_completed` | Search artifacts exist | search skill adapter |
| `screened_evidence` | Screened evidence exists and identifiers were checked | search/screen adapter |
| `outline_drafted` | Outline exists and uses evidence keys | drafting adapter |
| `sections_completed` | Required manuscript sections exist | drafting adapter |
| `bib_normalized` | Bibliography was cleaned/normalized | bibliography tool wrapper |
| `citations_resolved` | Inline citations map to bibliography keys | citations validator |
| `refs_validated` | References satisfy metadata rules | refs validator |
| `style_passed` | Style policy passes | Vale/style validator |
| `reporting_passed` | Reporting/structure rules pass | reporting/structure validators |
| `render_passed` | Render completed successfully | Pandoc wrapper |
| `ready_for_delivery` | Final verification and manifest succeeded | `paper verify` |

## Fail-Closed Rules

- Missing required dependencies -> gate fails.
- Missing required artifacts -> gate fails.
- Error-severity findings on required validators -> gate fails.
- A warning-only result may still fail if the gate policy explicitly says so.

## Evaluation Order

1. Dependency checks
2. Artifact existence checks
3. Validator/tool result checks
4. Gate status consolidation
5. Stage advancement decision

## Reset Rules

When a downstream-sensitive artifact changes, dependent gates reset.

Minimum reset policy:
- editing draft sections resets `citations_resolved`, `style_passed`, `reporting_passed`, `render_passed`, `ready_for_delivery`
- editing bibliography resets `bib_normalized`, `refs_validated`, `render_passed`, `ready_for_delivery`

## Rules

- Gates are the authority for stage advancement.
- Gates do not run tools by themselves; they evaluate normalized results.
- No command may advance stage if required gates are failed or unknown.

## Audit Checklist

- [ ] Every workflow stage has explicit required gates.
- [ ] Reset rules are documented for mutable artifacts.
- [ ] Dependency failure is treated as a blocker, not a warning.
