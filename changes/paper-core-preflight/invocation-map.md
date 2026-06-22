# Invocation Map — CLI Commands → Internal Functions

> Generated from codebase exploration on 2026-06-19.

## Section 1: PIPELINE_MAP Commands (16)

Pipeline commands are dispatched through `cli/paper/dispatch.py:PIPELINE_MAP` → `Orchestrator.execute()`.

| # | CLI Command | Key | Dispatch Handler | Orchestrator Command | Gate(s) Verified | Next Stage |
|---|-------------|-----|------------------|---------------------|-------------------|------------|
| 1 | `paper init` | `init` | `_resolve_init` | `init` | `repo_initialized` | `search` |
| 2 | `paper search` | `search` | `_resolve_search` | `search` | `search_completed` | `screen` |
| 3 | `paper chain` | `chain` | `_resolve_chain` | `chain` | `search_completed` | `screen` |
| 4 | `paper screen` | `screen` | `_resolve_screen` | `screen` | `screened_evidence` | `outline` |
| 5 | `paper export-bib` | `export-bib` | `_resolve_export_bib` | `export_bib` | `screened_evidence` | *(no advance)* |
| 6 | `paper draft outline` | `draft:outline` | lambda | `draft_outline` | `outline_drafted` | `drafting` |
| 7 | `paper draft section <name>` | `draft:section` | `_resolve_draft_section` | `draft_section` | `sections_completed` | `validating` (if all sections pass) |
| 8 | `paper draft all` | `draft:all` | lambda | `draft_all` | `sections_completed` | `validating` (if all sections pass) |
| 9 | `paper protocol` | `protocol` | `_resolve_protocol` | `protocol` | `screened_evidence` | *(no advance)* |
| 10 | `paper lint bib` | `lint:bib` | lambda | `lint_bib` | `bib_imported` (via wrapper) | `rendering` (when all rendering preconditions met) |
| 11 | `paper lint style` | `lint:style` | lambda | `lint_style` | `style_passed` (via wrapper) | `rendering` (when all rendering preconditions met) |
| 12 | `paper check refs` | `check:refs` | lambda | `check_refs` | `citations_resolved` + `refs_validated` + `citation_verified` (soft) | `rendering` (when all rendering preconditions met) |
| 13 | `paper audit reporting` | `audit:reporting` | lambda | `audit_reporting` | `reporting_passed` (via wrapper) | `rendering` (when all rendering preconditions met) |
| 14 | `paper import bib` | `import:bib` | `_resolve_import_bib` | `import_bib` or `zotero_sync` | `bib_imported` + `bib_normalized` | *(no advance)* |
| 15 | `paper render` | `render` | `_resolve_render` | `render` | `render_passed` + wrapper result | `rendered` |
| 16 | `paper verify` | `verify` | lambda | `verify` | `ready_for_delivery` + `citation_verified` (soft) + `ethics_passed` (soft) | `rendered` (stays) |
| — | *(unknown key)* | — | — | — | Raises `UserInputError` | — |

### Pipeline Stage Flow

```
bootstrap → search → screen → outline → drafting → validating → rendering → rendered
     ↑                                                              │
     └──────────────────── import:bib (can run anytime) ────────────┘
```

### Gate Precondition Matrix

| Stage | Required Gates |
|-------|---------------|
| `bootstrap` | *(none)* |
| `search` | `repo_initialized` |
| `screen` | `search_completed` |
| `outline` | `screened_evidence` |
| `drafting` | `outline_drafted` |
| `validating` | `sections_completed` |
| `rendering` | `bib_imported`, `bib_normalized`, `citations_resolved`, `refs_validated`, `style_passed`, `reporting_passed` |
| `rendered` | `render_passed` |

---

## Section 2: Phase 0 Commands (Direct Callbacks)

Phase 0 commands bypass the `PIPELINE_MAP` and run directly via argparse `func` callback.

### Audit Subcommands (9)

| # | CLI Command | Handler Function | Reads | Writes | Exit Code |
|---|-------------|-----------------|-------|--------|-----------|
| 1 | `paper audit prose <file>` | `_cmd_audit_prose` | manuscript file | stdout/JSON | 0 (always), 1 if P0 findings |
| 2 | `paper audit claims <file>` | `_cmd_audit_claims` | manuscript file | stdout/JSON | 0 |
| 3 | `paper audit citations <file>` | `_cmd_audit_citations` | manuscript file | stdout/JSON | 0, 1 if P0 findings |
| 4 | `paper audit ethics <file>` | `_cmd_audit_ethics` | manuscript file | stdout/JSON | 0, 1 if P0 findings |
| 5 | `paper audit writing-quality <file>` | `_cmd_audit_writing_quality` | manuscript file | stdout/JSON | 0, 1 if P0 findings |
| 6 | `paper audit factuality <file> --evidence <path>` | `_cmd_audit_factuality` | manuscript + screened_evidence.json | stdout/JSON | 0, 1 if findings |
| 7 | `paper audit tables <draft_dir>` | `_cmd_audit_tables` | draft sections directory | stdout/JSON | 0, 1 if findings |
| 8 | `paper audit quality-appraisal --evidence <path>` | `_cmd_audit_quality_appraisal` | screened_evidence.json | stdout/JSON | 0, 1 if findings |
| 9 | `paper audit code-health` | `_cmd_audit_code_health` | Trifecta graph index | stdout/JSON | 0, 1 if findings or Trifecta error |

### Gate Subcommand (1)

| # | CLI Command | Handler Function | Reads | Writes | Exit Code |
|---|-------------|-----------------|-------|--------|-----------|
| 10 | `paper gate method <file>` | `_cmd_gate_method` | manuscript file | stdout/JSON | 0 if gate passed, 1 if blocked |

### Graph Subcommands (2)

| # | CLI Command | Handler Function | Reads | Writes | Exit Code |
|---|-------------|-----------------|-------|--------|-----------|
| 11 | `paper trace <symbol>` | `_cmd_trace` | Trifecta graph index | stdout/JSON | 0 |
| 12 | `paper graph-overview` | `_cmd_graph_overview` | Trifecta graph index | stdout/JSON | 0 |

### Doctor Subcommand (1)

| # | CLI Command | Handler Function | Reads | Writes | Exit Code |
|---|-------------|-----------------|-------|--------|-----------|
| 13 | `paper doctor` | `_cmd_doctor` | PATH, environment, project assets | stdout | 0 |

### Zotero Subcommands (8)

| # | CLI Command | Handler Function | Reads | Writes | Exit Code |
|---|-------------|-----------------|-------|--------|-----------|
| 14 | `paper zotero collections` | `_cmd_zotero_collections` | Zotero API | stdout/JSON | 0 |
| 15 | `paper zotero search <query>` | `_cmd_zotero_search` | Zotero API | stdout/JSON | 0 |
| 16 | `paper zotero get <key>` | `_cmd_zotero_get` | Zotero API | stdout/JSON | 0 |
| 17 | `paper zotero create <file>` | `_cmd_zotero_create` | JSON file + Zotero API | stdout | 0 |
| 18 | `paper zotero template <type>` | `_cmd_zotero_template` | Zotero API | stdout/JSON | 0 |
| 19 | `paper zotero update <key> <file>` | `_cmd_zotero_update` | JSON file + Zotero API | stdout | 0 |
| 20 | `paper zotero delete <keys>` | `_cmd_zotero_delete` | Zotero API | stdout | 0 |
| 21 | `paper zotero upload <key> <file>` | `_cmd_zotero_upload` | File + Zotero API | stdout | 0 |

### Thesaurus Subcommands (5)

| # | CLI Command | Handler Function | Reads | Writes | Exit Code |
|---|-------------|-----------------|-------|--------|-----------|
| 22 | `paper thesaurus import <file>` | `_cmd_import` (external) | JSONL file | thesaurus.db | 0 |
| 23 | `paper thesaurus search <query>` | `_cmd_search` (external) | thesaurus.db | stdout | 0 |
| 24 | `paper thesaurus list` | `_cmd_list` (external) | thesaurus.db | stdout | 0 |
| 25 | `paper thesaurus audit` | `_cmd_audit` (external) | thesaurus.db | stdout | 0 |
| 26 | `paper thesaurus rebuild` | `_cmd_rebuild` (external) | JSONL file | thesaurus.db | 0 |

### Mesh Subcommands (4)

| # | CLI Command | Handler Function | Reads | Writes | Exit Code |
|---|-------------|-----------------|-------|--------|-----------|
| 27 | `paper mesh import` | `_cmd_mesh_import` (external) | MeSH data | mesh.db | 0 |
| 28 | `paper mesh resolve` | `_cmd_mesh_resolve` (external) | mesh.db | stdout | 0 |
| 29 | `paper mesh expand` | `_cmd_mesh_expand` (external) | mesh.db | stdout | 0 |
| 30 | `paper mesh export` | `_cmd_mesh_export` (external) | mesh.db | stdout/file | 0 |

---

## Section 3: Complete Command → Handler → Orchestrator → Gate → Artifact Matrix

```
CLI Command                    Phase   Handler/Dispatch              Orchestrator Command    Gate(s)                              Artifacts Created
─────────────────────────────  ─────   ───────────────────────────   ─────────────────────   ──────────────────────────────────   ──────────────────────────────
paper init                     Pipeline PIPELINE_MAP["init"]          init                    repo_initialized                     state.yaml, manuscript.qmd,
                                                                                                                              references.bib, review_config.yaml
paper search                   Pipeline PIPELINE_MAP["search"]        search                  search_completed                      raw_results.json, search_plan.json
paper chain                    Pipeline PIPELINE_MAP["chain"]         chain                   search_completed                      raw_results.json (expanded)
paper screen                   Pipeline PIPELINE_MAP["screen"]        screen                  screened_evidence                     screened_evidence.json
paper export-bib               Pipeline PIPELINE_MAP["export-bib"]    export_bib              screened_evidence                     references.bib
paper draft outline            Pipeline PIPELINE_MAP["draft:outline"] draft_outline           outline_drafted                       outline.md
paper draft section <name>     Pipeline PIPELINE_MAP["draft:section"] draft_section           sections_completed                    <name>.md
paper draft all                Pipeline PIPELINE_MAP["draft:all"]     draft_all               sections_completed                    all section .md files
paper protocol                 Pipeline PIPELINE_MAP["protocol"]      protocol                screened_evidence                     protocol.md
paper lint bib                 Pipeline PIPELINE_MAP["lint:bib"]      lint_bib                bib_imported                          bib normalizer log
paper lint style               Pipeline PIPELINE_MAP["lint:style"]    lint_style              style_passed                          style linter log
paper check refs               Pipeline PIPELINE_MAP["check:refs"]    check_refs              citations_resolved + refs_validated  refs validation log
paper audit reporting          Pipeline PIPELINE_MAP["audit:reporting"] audit_reporting        reporting_passed                      reporting audit log
paper import bib               Pipeline PIPELINE_MAP["import:bib"]    import_bib/zotero_sync  bib_imported + bib_normalized         references.bib (updated)
paper render                   Pipeline PIPELINE_MAP["render"]        render                  render_passed                         manuscript.docx, manuscript.pdf
paper verify                   Pipeline PIPELINE_MAP["verify"]        verify                  ready_for_delivery + citation/ethics  manifest.yaml + 4 verify artifacts

paper audit prose              Phase 0 _cmd_audit_prose                —                       —                                     stdout/JSON
paper audit claims             Phase 0 _cmd_audit_claims               —                       —                                     stdout/JSON
paper audit citations          Phase 0 _cmd_audit_citations            —                       —                                     stdout/JSON
paper audit ethics             Phase 0 _cmd_audit_ethics               —                       —                                     stdout/JSON
paper audit writing-quality    Phase 0 _cmd_audit_writing_quality      —                       —                                     stdout/JSON
paper audit factuality         Phase 0 _cmd_audit_factuality           —                       —                                     stdout/JSON
paper audit tables             Phase 0 _cmd_audit_tables               —                       —                                     stdout/JSON
paper audit quality-appraisal  Phase 0 _cmd_audit_quality_appraisal    —                       —                                     stdout/JSON
paper audit code-health        Phase 0 _cmd_audit_code_health          —                       —                                     stdout/JSON
paper gate method              Phase 0 _cmd_gate_method                —                       —                                     stdout/JSON
paper trace                    Phase 0 _cmd_trace                      —                       —                                     stdout/JSON
paper graph-overview           Phase 0 _cmd_graph_overview             —                       —                                     stdout/JSON
paper doctor                   Phase 0 _cmd_doctor                     —                       —                                     stdout
paper zotero collections       Phase 0 _cmd_zotero_collections         —                       —                                     stdout/JSON
paper zotero search            Phase 0 _cmd_zotero_search              —                       —                                     stdout/JSON
paper zotero get               Phase 0 _cmd_zotero_get                 —                       —                                     stdout/JSON
paper zotero create            Phase 0 _cmd_zotero_create              —                       —                                     stdout
paper zotero template          Phase 0 _cmd_zotero_template            —                       —                                     stdout/JSON
paper zotero update            Phase 0 _cmd_zotero_update              —                       —                                     stdout
paper zotero delete            Phase 0 _cmd_zotero_delete              —                       —                                     stdout
paper zotero upload            Phase 0 _cmd_zotero_upload              —                       —                                     stdout
paper thesaurus import         Phase 0 _cmd_import (external)          —                       —                                     thesaurus.db
paper thesaurus search         Phase 0 _cmd_search (external)          —                       —                                     stdout
paper thesaurus list           Phase 0 _cmd_list (external)            —                       —                                     stdout
paper thesaurus audit          Phase 0 _cmd_audit (external)           —                       —                                     stdout
paper thesaurus rebuild        Phase 0 _cmd_rebuild (external)         —                       —                                     thesaurus.db
paper mesh import              Phase 0 external register               —                       —                                     mesh.db
paper mesh resolve             Phase 0 external register               —                       —                                     stdout
paper mesh expand              Phase 0 external register               —                       —                                     stdout
paper mesh export              Phase 0 external register               —                       —                                     stdout/file
```

---

## Section 4: Exit Code Semantics

### Current Behavior (Before Task B5a)

| Exit Code | Meaning | Trigger |
|-----------|---------|---------|
| `0` | Success | ALL commands (dispatch always returns 0, discards callback return value) |
| `2` | User input error | `UserInputError` raised by callback (caught by dispatch, returns 0) |
| `130` | Interrupted | `KeyboardInterrupt` (Ctrl+C) |

**Note:** Currently, `dispatch.py` executes `func(args)` and discards the return value. ALL Phase 0 callbacks return exit code 0, even when they raise `UserInputError` (which is caught and printed to stderr, but the process still exits 0).

### Proposed Behavior (After Task B5a)

| Exit Code | Meaning | Trigger |
|-----------|---------|---------|
| `0` | Success | Command completed without blockers, callback returns `None` or `0` |
| `1` | Internal error / blocked | Callback returns `1`, gate `fail` status, P0 findings in audit |
| `2` | User input error | Callback returns `2`, `UserInputError` raised |
| `3` | External service error | Callback returns `3`, `ExternalServiceError` raised |
| `130` | Interrupted | `KeyboardInterrupt` (Ctrl+C) |

**Change:** `dispatch.py` captures `callback_result = func(args)`. If `type(callback_result) is int` (NOT `isinstance` — avoids `bool` as exit code 1), use as exit code. Otherwise, default to 0. Existing callbacks return `None` → exit code 0 (backward compatible). Preflight will return explicit exit codes (0, 1, 2).

### Output Policy

| Policy | Meaning |
|--------|---------|
| `text-only` | Only text output allowed; `--output-format json` rejected with exit 2 |
| `json-capable` | Both text and JSON output supported |
| `external` | Output managed by external module (thesaurus, mesh) |
