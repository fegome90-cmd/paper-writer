# Data Flow — Artifact Lifecycle & Pipeline Data Path

> Generated from codebase exploration on 2026-06-19.

## 1. End-to-End Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              paper CLI (main.py)                                │
│                          parse → dispatch → execute                             │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
              Phase 0 callback                     PIPELINE_MAP dispatch
              (func(args))                         (spec.resolve(args))
                    │                                     │
                    ▼                                     ▼
          ┌─────────────────┐              ┌──────────────────────────┐
          │  Validator/Tool  │              │   Orchestrator.execute() │
          │  (direct call)   │              │                          │
          └────────┬────────┘              └────────────┬─────────────┘
                   │                                    │
                   │                          ┌─────────┴─────────┐
                   │                          │  1. PREPARE PHASE  │
                   │                          │  Load state.yaml   │
                   │                          │  Validate stage     │
                   │                          └─────────┬─────────┘
                   │                                    │
                   │                          ┌─────────┴─────────┐
                   │                          │  2. APPLY PHASE    │
                   │                          │  ActionRunner      │
                   │                          │  .run_action(cmd)  │
                   │                          └─────────┬─────────┘
                   │                                    │
                   │                    ┌───────────────┴───────────────┐
                   │                    │                               │
                   │           ┌────────┴────────┐           ┌────────┴────────┐
                   │           │ SkillAdapter     │           │ ToolWrapper      │
                   │           │ (search/draft)   │           │ (lint/render)    │
                   │           └────────┬────────┘           └────────┬────────┘
                   │                    │                               │
                   │           ┌────────┴────────┐           ┌────────┴────────┐
                   │           │ Clients/Tools    │           │ External Tools  │
                   │           │ (Consensus, S2,  │           │ (Pandoc, Vale,  │
                   │           │  Zotero, etc.)   │           │  bibtex-tidy)   │
                   │           └────────┬────────┘           └────────┬────────┘
                   │                    │                               │
                   │                    ▼                               ▼
                   │           ┌──────────────────────────────────────────────┐
                   │           │           outputs/runs/{run_id}/             │
                   │           │  search/  drafts/  render/  verify/  logs/  │
                   │           └──────────────────────┬───────────────────────┘
                   │                                  │
                   │                    ┌─────────────┴─────────────┐
                   │                    │  3. VERIFY PHASE           │
                   │                    │  Gate verification         │
                   │                    │  State update              │
                   │                    │  Stage transition          │
                   │                    └─────────────┬─────────────┘
                   │                                  │
                   │                    ┌─────────────┴─────────────┐
                   │                    │  outputs/state.yaml        │
                   │                    │  outputs/manifest.yaml     │
                   │                    │  outputs/latest → symlink  │
                   │                    └───────────────────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │  stdout / JSON   │
          │  (exit code 0-3) │
          └─────────────────┘
```

## 2. Artifact Lifecycle Table

| Artifact | Created By | Read By | Regenerable |
|----------|-----------|---------|-------------|
| `outputs/state.yaml` | `Orchestrator` (via `StateManager`) | `Orchestrator`, `StateManager`, all gate validators | **No** — contains runtime state; `init` creates from scratch only |
| `outputs/review_config.yaml` | `FilesystemActionRunner.init()` | `dispatch.py` (on every pipeline command), `FilesystemActionRunner` (review config fields) | **Yes** — re-created by `paper init --mode <mode>` |
| `outputs/.run_id` | `FilesystemActionRunner.init()` | `FilesystemActionRunner.run_id` property | **Yes** — re-created by `init`; updated on search/chain |
| `outputs/runs/{run_id}/run.yaml` | `FilesystemActionRunner._write_run_yaml()` | `FilesystemActionRunner._complete_run()`, `_fail_run()`, `_mark_run_blocked()` | **Yes** — created per run |
| `outputs/latest` (symlink) | `FilesystemActionRunner._resolve_run()` | All downstream commands (screen, draft, render, etc.) | **Yes** — always points to most recent run |
| `outputs/latest/search/raw_results.json` | `LiteratureSearchAdapter.search()` | `screen`, `chain`, `export_bib`, `verify_artifacts` | **Yes** — re-run `paper search` |
| `outputs/latest/search/screened_evidence.json` | `LiteratureSearchAdapter.screen()` | `draft_outline`, `draft_section`, `draft_all`, `verify_artifacts`, `audit_factuality`, `audit_quality_appraisal`, `protocol` | **Yes** — re-run `paper screen` |
| `outputs/latest/search/search_plan.json` | `LiteratureSearchAdapter.search()` | `verify_artifacts` (search_manifest) | **Yes** — re-run `paper search` |
| `outputs/latest/drafts/outline.md` | `AcademicWriterAdapter.draft_outline()` | `draft_section`, `audit_reporting` | **Yes** — re-run `paper draft outline` |
| `outputs/latest/drafts/{section}.md` | `AcademicWriterAdapter.draft_section()` | `assembler`, `audit_*` (manuscript-based), `verify_artifacts` | **Yes** — re-run `paper draft section <name>` |
| `outputs/latest/drafts/manuscript.md` | `assemble_manuscript()` (assembler) | `PandocRenderer`, `audit_*` (manuscript-based) | **Yes** — re-assembled on render |
| `outputs/latest/render/manuscript.docx` | `PandocRenderer` | `emit_manifest`, gate verification | **Yes** — re-run `paper render --format docx` |
| `outputs/latest/render/manuscript.pdf` | `PandocRenderer` (via tectonic) | `emit_manifest`, gate verification | **Yes** — re-run `paper render --format pdf` |
| `outputs/latest/verify/search_manifest.yaml` | `_generate_search_manifest()` | `verify` gate check | **Yes** — re-run `paper verify` |
| `outputs/latest/verify/evidence_matrix.csv` | `_generate_evidence_matrix()` | `verify` gate check | **Yes** — re-run `paper verify` |
| `outputs/latest/verify/included_excluded_ledger.yaml` | `_generate_included_excluded_ledger()` | `verify` gate check | **Yes** — re-run `paper verify` |
| `outputs/latest/verify/claim_citation_audit.yaml` | `_generate_claim_citation_audit()` | `verify` gate check | **Yes** — re-run `paper verify` |
| `outputs/manifest.yaml` | `FilesystemActionRunner.emit_manifest()` | User, CI/CD, delivery verification | **Yes** — re-run `paper verify` |
| `templates/references.bib` | `init`, `import_bib`, `zotero_sync`, `export_bib` | `check_refs`, `lint_bib`, `verify_artifacts`, draft adapters | **Yes** — re-import from Zotero or re-export |
| `templates/manuscript.qmd` | `init` (from preset or package default) | `PandocRenderer` (fallback if no manuscript.md) | **Yes** — re-run `paper init` |
| `outputs/latest/logs/*.yaml` | `FilesystemActionRunner.write_command_log()` | Debugging, audit trail | **Yes** — created per command |

## 3. State Machine Transitions

```
                    ┌──────────────┐
                    │  bootstrap   │
                    │  (init)      │
                    └──────┬───────┘
                           │ repo_initialized=True
                           ▼
                    ┌──────────────┐
                    │    search    │
                    │  (search)    │
                    └──────┬───────┘
                           │ search_completed=True
                           ▼
                    ┌──────────────┐
                    │    screen    │
                    │  (screen)    │
                    └──────┬───────┘
                           │ screened_evidence=True
                           ▼
                    ┌──────────────┐
                    │   outline    │
                    │ (draft outline)
                    └──────┬───────┘
                           │ outline_drafted=True
                           ▼
                    ┌──────────────┐
                    │   drafting   │
                    │ (draft section/all)
                    └──────┬───────┘
                           │ sections_completed=True
                           ▼
                    ┌──────────────┐
                    │  validating  │
                    │ (lint, check,│
                    │  audit)      │
                    └──────┬───────┘
                           │ bib_imported + bib_normalized + citations_resolved +
                           │ refs_validated + style_passed + reporting_passed
                           ▼
                    ┌──────────────┐
                    │  rendering   │
                    │  (render)    │
                    └──────┬───────┘
                           │ render_passed=True
                           ▼
                    ┌──────────────┐
                    │   rendered   │
                    │  (verify)    │
                    └──────────────┘
```

## 4. Downstream Gate Reset Cascade

When an upstream artifact is modified, dependent gates are reset:

```
bib modified (import_bib, zotero_sync):
  bib_imported → False
  bib_normalized → False
  citations_resolved → False
  refs_validated → False
  render_passed → False
  ready_for_delivery → False
  citation_verified → False

draft modified (draft_section, draft_all):
  citations_resolved → False
  style_passed → False
  reporting_passed → False
  render_passed → False
  ready_for_delivery → False
  citation_verified → False
  ethics_passed → False

search modified (search, chain):
  screened_evidence → False
  outline_drafted → False
  sections_completed → False
  citations_resolved → False
  style_passed → False
  reporting_passed → False
  render_passed → False
  ready_for_delivery → False
  citation_verified → False
  ethics_passed → False
```

## 5. Run Lineage

```
outputs/
├── state.yaml                  # Global pipeline state
├── manifest.yaml               # Final delivery manifest
├── review_config.yaml          # Review mode config (tracked)
├── .run_id                     # Current run identifier
├── latest → runs/{run_id}/     # Symlink to current run
└── runs/
    ├── {run_id_1}/             # First search run
    │   ├── run.yaml            # Run metadata (status, artifacts, timestamps)
    │   ├── search/
    │   │   ├── search_plan.json
    │   │   ├── raw_results.json
    │   │   └── screened_evidence.json
    │   ├── drafts/
    │   │   ├── outline.md
    │   │   ├── introduction.md
    │   │   ├── methods.md
    │   │   ├── results.md
    │   │   ├── discussion.md
    │   │   ├── abstract.md
    │   │   ├── conclusion.md
    │   │   └── manuscript.md   # Assembled from sections
    │   ├── render/
    │   │   ├── manuscript.docx
    │   │   └── manuscript.pdf
    │   ├── verify/
    │   │   ├── search_manifest.yaml
    │   │   ├── evidence_matrix.csv
    │   │   ├── included_excluded_ledger.yaml
    │   │   └── claim_citation_audit.yaml
    │   └── logs/
    │       ├── search_{ts}.yaml
    │       ├── lint_bib_{ts}.yaml
    │       ├── render_{ts}.yaml
    │       └── verify_{ts}.yaml
    └── {run_id_2}/             # Subsequent run (chain, re-search)
        └── ...
```
