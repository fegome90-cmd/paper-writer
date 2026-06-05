# Authority-Flow Audit Report

**Mode:** repo-audit (Tier 2 escalation)
**Scope:** paper-writer — full repository architectural inspection
**Date:** 2026-06-04
**Auditor:** el Gentleman (authority-flow-audit v2.1)

---

## 1. Verdict

**NEEDS ATTENTION:** No competing writes or race conditions detected. The state machine is single-source and well-governed. However, 12 of 30+ CLI commands bypass the Orchestrator entirely (direct `func=` dispatch), and the `FilesystemActionRunner` has dual-path writes (skill adapter vs fallback mock) for 5 critical artifacts. These are not data-loss risks but they create **authority ambiguity** and **orphaned pipeline surfaces**.

---

## 2. Surface Inventory

### Tier 1: Authority-Critical Surfaces

| # | Surface | Type | File:Lines | Calls | Called By |
|---|---------|------|------------|-------|-----------|
| 1 | `main()` | cli | cli/paper/main.py:67-488 | Orchestrator.execute, resolve_project_root, build_orchestrator_dependencies | sys.argv |
| 2 | `Orchestrator.execute()` | method | harness/services/orchestrator.py:103-292 | StateManager, ArtifactChecker, ActionRunner, ToolWrappers | main() |
| 3 | `StateManager.save_state()` | writer | harness/services/state_manager.py:48-50 | YamlFileStateRepository.write | Orchestrator (only) |
| 4 | `StateManager.set_gate()` | writer | harness/services/state_manager.py:57-66 | ManuscriptState.set_gate + save_state | Orchestrator (only) |
| 5 | `StateManager.set_stage()` | writer | harness/services/state_manager.py:70-79 | ManuscriptState.transition_to + save_state | Orchestrator (only) |
| 6 | `FilesystemActionRunner.run_action()` | writer | harness/adapters/filesystem_action_runner.py:94-497 | SkillAdapters, filesystem writes | Orchestrator (only) |
| 7 | `_cmd_audit_prose()` | cli-direct | cli/paper/commands/audit.py:10-62 | ProseAuditor, format_json/terminal | main() via func= bypass |
| 8 | `_cmd_audit_citations()` | cli-direct | cli/paper/commands/audit.py:92-138 | CitationsAuditor, format_json/terminal | main() via func= bypass |
| 9 | `_cmd_audit_ethics()` | cli-direct | cli/paper/commands/audit.py:140-179 | EthicsAuditor, format_json/terminal | main() via func= bypass |
| 10 | `_cmd_audit_writing_quality()` | cli-direct | cli/paper/commands/audit.py:181-228 | WritingQualityAuditor, format_json/terminal | main() via func= bypass |
| 11 | `_cmd_audit_code_health()` | cli-direct | cli/paper/commands/audit.py:230-284 | CodeHealthAuditor, format_json/terminal | main() via func= bypass |
| 12 | `_cmd_audit_factuality()` | cli-direct | cli/paper/commands/audit.py:286-340 | ClaimEvidenceValidator, format_json/terminal | main() via func= bypass |
| 13 | `_cmd_audit_tables()` | cli-direct | cli/paper/commands/audit.py:341-369 | TableFigureValidator, format_json/terminal | main() via func= bypass |
| 14 | `_cmd_audit_quality_appraisal()` | cli-direct | cli/paper/commands/audit.py:371-399 | QualityAppraisalValidator, format_json/terminal | main() via func= bypass |
| 15 | `_cmd_gate_method()` | cli-direct | cli/paper/commands/gate.py:10-80 | MethodGateValidator, format_json/terminal | main() via func= bypass |
| 16 | `_cmd_trace()` | cli-direct | cli/paper/commands/graph.py:8-78 | TrifectaClient, format_json/terminal | main() via func= bypass |
| 17 | `_cmd_graph_overview()` | cli-direct | cli/paper/commands/graph.py:80-150 | TrifectaClient, format_json/terminal | main() via func= bypass |
| 18 | `doctor` block | cli-direct | cli/paper/main.py:384-398 | check_all_tools, format_doctor_report | main() inline |
| 19 | `emit_manifest()` | writer | harness/adapters/filesystem_action_runner.py:483-502 | yaml.dump | Orchestrator (only) |
| 20 | `write_command_log()` | writer | harness/adapters/filesystem_action_runner.py:471-480 | json.dump | Orchestrator (only) |

### Tier 2: Mutation-Affecting Surfaces

| # | Surface | Type | File:Lines | Between |
|---|---------|------|------------|---------|
| 21 | `LiteratureSearchAdapter.execute()` | transformer | skills/local/adapters.py:42-175 | main() → ActionRunner → Adapter → filesystem |
| 22 | `AcademicWriterAdapter.execute()` | transformer | skills/local/adapters.py:177-400 | main() → ActionRunner → Adapter → filesystem |
| 23 | `CitationVerifyAdapter.execute()` | transformer | skills/local/adapters.py:403-437 | (unused in production — only wired in imports) |
| 24 | `EthicsAdapter.execute()` | transformer | skills/local/adapters.py:440-476 | (unused in production — only wired in imports) |
| 25 | `WritingQualityAdapter.execute()` | transformer | skills/local/adapters.py:479-513 | (unused in production — only wired in imports) |
| 26 | 13 ToolWrapper `.run()` methods | transformer | integrations/tools/*.py | Orchestrator → _run_wrapper_gate → Wrapper → ValidatorResult |
| 27 | `build_orchestrator_dependencies()` | assembler | harness/services/orchestrator_builder.py:32-115 | main() → builder → Orchestrator constructor |
| 28 | `run_real_validation.py` | script | verification/run_real_validation.py | Standalone script, bypasses Orchestrator |

---

## 3. Authority Table

| Surface | Type | Primary Action | State Reads | State Writes | Authority | Competes With | Pipeline Affected | Risk | Confidence | Evidence Class |
|---------|------|---------------|-------------|-------------|-----------|--------------|------------------|------|------------|----------------|
| Orchestrator.execute() | method | 3-phase command execution | state.yaml | state.yaml (via StateManager) | **authoritative** | none | ALL | INFO | high | direct-write |
| StateManager | writer | Persist gates + stage | state.yaml (load) | state.yaml (save) | **delegated** | none | ALL | INFO | high | call-chain |
| FilesystemActionRunner | writer | Execute actions, write artifacts | templates/, outputs/ | outputs/latest/ | **delegated** | SkillAdapters | search, screen, draft, render | MEDIUM | high | direct-write |
| _cmd_audit_* (9 funcs) | cli | Run validators directly | manuscript files | stdout only | **reader-only** | none | validating | INFO | high | direct-write |
| _cmd_gate_method() | cli | Run method gate directly | manuscript files | stdout only | **reader-only** | none | validating | INFO | high | direct-write |
| _cmd_trace/graph_overview | cli | Query Trifecta graph | .trifecta/ | stdout only | **reader-only** | none | none | INFO | high | direct-write |
| doctor block | cli | Check environment | filesystem | stdout only | **reader-only** | none | none | INFO | high | direct-write |
| LiteratureSearchAdapter | transformer | Score + classify papers | raw_papers | raw_results.json, screened_evidence.json | **delegated** | ActionRunner fallback | search → screen | MEDIUM | high | call-chain |
| AcademicWriterAdapter | transformer | Generate section skeletons | outline, evidence, bib | outline.md, section.md | **delegated** | ActionRunner fallback | draft | MEDIUM | high | call-chain |
| 13 ToolWrappers | transformer | Run validators | manuscripts, bib | ValidatorResult (memory) | **evidence** | none | validating | INFO | high | call-chain |
| CitationVerifyAdapter | transformer | (unused in production) | manuscripts | SkillResult (memory) | **orphaned** | CitationsAuditor wrapper | validating | LOW | high | call-chain |
| EthicsAdapter | transformer | (unused in production) | manuscripts | SkillResult (memory) | **orphaned** | EthicsAuditor wrapper | validating | LOW | high | call-chain |
| WritingQualityAdapter | transformer | (unused in production) | manuscripts | SkillResult (memory) | **orphaned** | WritingQualityAuditor wrapper | validating | LOW | high | call-chain |
| run_real_validation.py | script | End-to-end validation | state.yaml, manuscripts | state.yaml, reports | **competing** | Orchestrator | ALL | HIGH | high | direct-write |

---

## 4. Pipelines Detected

### Pipeline: state.yaml (gates + stage)

| Path | Entry Point | Steps | Active | Authority | Notes |
|------|------------|-------|--------|-----------|-------|
| Official | `paper <command>` CLI | main() → Orchestrator.execute() → StateManager.set_gate/set_stage → save_state | **yes** | Orchestrator | Single writer, fail-closed |
| Shadow | `run_real_validation.py` | Script → direct filesystem writes to state.yaml | **yes** | none | Bypasses StateManager domain validation |

**Pipeline type: official + tolerated** (script is a verification tool, not production path)

### Pipeline: raw_results.json / screened_evidence.json

| Path | Entry Point | Steps | Active | Authority | Notes |
|------|------------|-------|--------|-----------|-------|
| Official | `paper search` CLI | main() → Orchestrator → ActionRunner → LiteratureSearchAdapter.execute() → search_module.search() | **yes** | LiteratureSearchAdapter | Real scoring engine |
| Fallback | `paper search` (no adapter) | main() → Orchestrator → ActionRunner → mock JSON write | **tests only** | ActionRunner | Mock data, never in production |
| Post-adapter safety net | `paper search` (adapter runs but no file) | ActionRunner writes fallback raw_results.json | **edge case** | ActionRunner | **FINDING F-01**: Adapter claimed success but file doesn't exist |

**Pipeline type: official + tolerated** (fallback is for tests only, but safety net is a real path)

### Pipeline: outline.md / section drafts

| Path | Entry Point | Steps | Active | Authority | Notes |
|------|------------|-------|--------|-----------|-------|
| Official | `paper draft outline/section/all` | main() → Orchestrator → ActionRunner → AcademicWriterAdapter.execute() → writer_module.draft_*() | **yes** | AcademicWriterAdapter | Real skeleton generation |
| Fallback | `paper draft outline/section` (no adapter) | main() → Orchestrator → ActionRunner → mock content write | **tests only** | ActionRunner | Mock content |

**Pipeline type: official + tolerated**

### Pipeline: references.bib

| Path | Entry Point | Steps | Active | Authority | Notes |
|------|------------|-------|--------|-----------|-------|
| Official-A | `paper export-bib` | main() → Orchestrator → ActionRunner → LiteratureSearchAdapter._handle_export_bib() | **yes** | LiteratureSearchAdapter | Converts screened evidence to BibTeX |
| Official-B | `paper import bib` | main() → Orchestrator → _run_wrapper_gate("import_bib") → ZoteroImporter.run() | **yes** | ZoteroImporter | Imports from external .bib |
| Manual | User editing | Direct file edit | **yes** | none | User is the human in the loop |

**Pipeline type: official + tolerated** (two official import paths + manual editing)

### Pipeline: manuscript.docx / manuscript.pdf

| Path | Entry Point | Steps | Active | Authority | Notes |
|------|------------|-------|--------|-----------|-------|
| Official | `paper render` | main() → Orchestrator → ActionRunner (assemble_manuscript + PandocRenderer) | **yes** | PandocRenderer | Assembled from sections |
| Manual | User editing | Direct file edit | **possible** | none | |

**Pipeline type: single-pipeline** (rendered output is write-once per render)

### Pipeline: Validation audit results (stdout)

| Path | Entry Point | Steps | Active | Authority | Notes |
|------|------------|-------|--------|-----------|-------|
| Path-A | `paper audit <sub>` (9 commands) | main() → func=bypass → direct validator → stdout | **yes** | _cmd_audit_* | Bypasses Orchestrator, no gate updates |
| Path-B | `paper lint/style/check/audit_reporting` | main() → Orchestrator → _run_wrapper_gate() → ToolWrapper → ValidatorResult → GateResult | **yes** | Orchestrator | Updates gates |

**Pipeline type: competing** — Two paths produce validation output. Only Path-B updates gates.

---

## 5. Duplications and Conflicts

| # | Conflict Type | Surfaces Involved | State/Artifact | Evidence | Severity | Confidence | Evidence Class |
|---|--------------|------------------|---------------|----------|----------|------------|----------------|
| F-01 | **post-adapter safety net** | ActionRunner:204-210, LiteratureSearchAdapter | raw_results.json | ActionRunner writes fallback JSON after adapter.execute() succeeds but file may not exist | LOW | high | direct-write |
| F-02 | **competing validation paths** | _cmd_audit_* (Path-A), ToolWrapper via Orchestrator (Path-B) | Gate state (gates not updated by Path-A) | main.py:381 `func=args` bypasses orchestrator | **MEDIUM** | high | direct-write |
| F-03 | **orphaned skill adapters** | CitationVerifyAdapter, EthicsAdapter, WritingQualityAdapter | SkillResult (never consumed) | adapters.py:403-513 — defined but not registered in builder | LOW | high | call-chain |
| F-04 | **competing state writer** | run_real_validation.py | state.yaml | verification/run_real_validation.py:558-559 writes state.yaml directly | **HIGH** | high | direct-write |

---

## 6. Side Effects and Contention Points

| # | Side Effect | Triggering Surface | Target | Concurrent With | Coordination | Severity | Confidence | Evidence Class |
|---|-------------|-------------------|--------|-----------------|-------------|----------|------------|----------------|
| SE-01 | Gate reset on draft modification | Orchestrator:163-164 (reset_downstream_gates) | state.yaml: 6 gates reset to False | No concurrent surfaces | Sequential by design | INFO | high | direct-write |
| SE-02 | Symlink update on every run_action | ActionRunner:_resolve_run() | outputs/latest symlink | No concurrent surfaces | Sequential by design | INFO | high | direct-write |
| SE-03 | Command log write on every Orchestrator.execute | Orchestrator:93-99 | outputs/logs/{command}.json | No concurrent surfaces | best_effort (silently fails) | INFO | high | direct-write |
| SE-04 | Direct state.yaml write | run_real_validation.py:558-559 | state.yaml | Production Orchestrator | **none** — script runs independently | HIGH | high | direct-write |

---

## 7. Proposed Official Entrypoints

| Artifact/State | Proposed Authority | Current Authority | Rationale |
|---------------|-------------------|------------------|-----------|
| state.yaml (gates) | Orchestrator via StateManager | Orchestrator (official) + run_real_validation.py (shadow) | Script should use StateManager API instead of raw YAML writes |
| raw_results.json | LiteratureSearchAdapter via ActionRunner | LiteratureSearchAdapter (official) | Remove ActionRunner fallback safety net (F-01) |
| Validation gate updates | Orchestrator._run_wrapper_gate() only | Orchestrator (Path-B) + _cmd_audit_* bypass (Path-A) | All audit commands should flow through Orchestrator |

---

## 8. Surfaces That Must Not Mutate Official State

| Surface | Currently Mutates | Should Be | Required Change |
|---------|------------------|-----------|----------------|
| run_real_validation.py | state.yaml directly | reader-only (read state, write reports only) | Import and use StateManager API instead of raw file writes |
| _cmd_audit_* (9 functions) | No state mutation (correct!) | reader-only (already correct) | No change needed — these are correctly read-only |
| ActionRunner (fallback paths) | raw_results.json, section drafts (mock data) | delegated (only when no adapter) | Keep for tests but add assertion that adapters are always wired in production |

---

## 9. Prioritized Risks

| Priority | Risk | Severity | Impact | Effort to Fix | Depends On | Confidence | Evidence Class |
|----------|------|----------|--------|---------------|------------|------------|----------------|
| P1 | **F-04: run_real_validation.py writes state.yaml without domain validation** | HIGH | State inconsistency if run while CLI is active | S | Import StateManager | none | high | direct-write |
| P2 | **F-02: 12 audit commands bypass Orchestrator — no gate updates** | MEDIUM | Validation results don't affect pipeline state | M | Route through Orchestrator or add gate-updating side channel | Design decision on routing | high | direct-write |
| P3 | **F-03: 3 skill adapters defined but never wired in builder** | LOW | Dead code, confusing for contributors | S | Remove or wire in | none | high | call-chain |
| P4 | **F-01: ActionRunner writes fallback after adapter succeeds** | LOW | Benign but masks adapter bugs (file should exist after success) | S | Add assertion or remove fallback | none | high | direct-write |
| P5 | **GAP: No review/revise pipeline stage** | MEDIUM | ARS has 10-stage pipeline; we have 8. Missing: review, revise, integrity gates | L | New stages + state machine extension | Design decision on scope | high | docs-only |
| P6 | **GAP: No Material Passport or provenance tracking** | MEDIUM | No end-to-end traceability of artifacts | L | New schema + integration | P5 decision | high | docs-only |
| P7 | **GAP: arXiv client missing — citation verification incomplete** | MEDIUM | ~30% of CS/physics papers are arXiv-only | S | New clients/arxiv.py following crossref.py pattern | none | high | docs-only |
| P8 | **GAP: Temporal verification missing — no anachronism detection** | MEDIUM | Citations can claim future papers as evidence | M | New validators/temporal_integrity.py | arXiv client (P7) for preprints | high | docs-only |

---

## 10. Recommended Intervention Order

1. **Fix F-04 (run_real_validation.py)** — Import StateManager, stop raw YAML writes. This is the only CRITICAL authority conflict. [Effort: S]
2. **Resolve F-03 (orphaned adapters)** — Either wire CitationVerifyAdapter, EthicsAdapter, WritingQualityAdapter into orchestrator_builder.py, or remove them. Currently dead code. [Effort: S]
3. **Decide F-02 routing strategy** — Two options:
   - (A) Route all audit commands through Orchestrator (consistent, gate-updating) — **recommended**
   - (B) Keep current bypass but add a lightweight gate-update mechanism for audit commands
   The current design is *correct* (audit commands are read-only, they don't need state mutation) but *inconsistent* (some audits update gates, others don't). [Effort: M, requires design decision]
4. **Port arXiv client (P7)** — New `clients/arxiv.py` following `clients/crossref.py` pattern. Register as ToolWrapper. [Effort: S]
5. **Port temporal verification (P8)** — New `validators/temporal_integrity.py`. Register as ToolWrapper. [Effort: M]
6. **Port PRISMA expansion (P5 partial)** — Expand `rules/prisma.yml` with full PRISMA checklist items. [Effort: M]
7. **Decide review/revise stages (P5)** — Architectural decision: do we add review/revise to the state machine or keep paper-writer as validation-only? [Effort: L, requires product decision]
8. **Remove F-01 safety net** — After adapters are proven stable, remove the fallback JSON write in ActionRunner. [Effort: S]

---

## 11. Uncertainties and Evidence Gaps

| # | Uncertainty | What Cannot Be Determined | What Would Resolve It |
|---|------------|--------------------------|----------------------|
| U-01 | Whether run_real_validation.py is ever run concurrently with CLI | No locking mechanism visible in code | Runtime testing with concurrent execution |
| U-02 | Whether the 9 bypass audit commands are intentionally separate from the Orchestrator | Code comment says "Phase 0 commands — run directly" but doesn't explain why | Original design intent discussion |
| U-03 | Whether F-01 safety net has ever masked a real adapter bug | No production incident data | Audit of adapter output files after production runs |
| U-04 | Extent of arXiv coverage needed for target journals | Depends on research domain (CS/physics = high, medicine = low) | User research on citation sources |
| U-05 | Whether PRISMA rules should be a gate or a standalone validator | Method gate exists but PRISMA support is partial | Design decision aligned with #10.6 |

---

## 12. Authority Map

```
                        ┌─────────────────────────┐
                        │       CLI (main.py)      │
                        └─────────┬───────────────┘
                                  │
                 ┌────────────────┼──────────────────┐
                 │                │                   │
          func=bypass       Orchestrator         func=bypass
         (12 commands)      (18 commands)        (doctor)
                 │                │                   │
                 ▼                ▼                   ▼
          Validators*      3-phase flow        check_all_tools
         (read-only)     (prepare→apply→verify)  (read-only)
                              │       │      │
                              │       │      │
                     ┌────────┘       │      └── stdout
                     │                │
              StateManager    ActionRunner
              (state.yaml     (filesystem writes)
               = AUTHORITATIVE)    │
                              ┌────┼────┐
                              │    │    │
                         SkillAdapters ToolWrappers
                         (search/    (13 validators)
                          draft)         │
                              │     ValidatorResult
                              │     (evidence only)
                              ▼
                        outputs/latest/
                        (run artifacts)

    SHADOW: run_real_validation.py → writes state.yaml directly
    ORPHANED: CitationVerifyAdapter, EthicsAdapter, WritingQualityAdapter
```

---

## 13. Pipeline Map

| Artifact | Path Name | Entrypoint → ... → Writer | Active | Authority |
|----------|-----------|---------------------------|--------|-----------|
| state.yaml | Official | main() → Orchestrator.execute() → StateManager.set_gate/set_stage() → YamlFileStateRepository.write() | yes | StateManager |
| state.yaml | Shadow | run_real_validation.py → Path.write_text() | yes | none |
| raw_results.json | Official | main() → Orchestrator → ActionRunner → LiteratureSearchAdapter → search_module.search() | yes | LiteratureSearchAdapter |
| screened_evidence.json | Official | main() → Orchestrator → ActionRunner → LiteratureSearchAdapter → search_module.screen() | yes | LiteratureSearchAdapter |
| outline.md | Official | main() → Orchestrator → ActionRunner → AcademicWriterAdapter → writer_module.draft_outline() | yes | AcademicWriterAdapter |
| section drafts | Official | main() → Orchestrator → ActionRunner → AcademicWriterAdapter → writer_module.draft_section() | yes | AcademicWriterAdapter |
| references.bib | Export path | main() → Orchestrator → ActionRunner → LiteratureSearchAdapter._handle_export_bib() | yes | LiteratureSearchAdapter |
| references.bib | Import path | main() → Orchestrator → _run_wrapper_gate("import_bib") → ZoteroImporter.run() | yes | ZoteroImporter |
| manuscript.docx/pdf | Official | main() → Orchestrator → ActionRunner (assemble + PandocRenderer) | yes | PandocRenderer |
| Validation results | Path-A (bypass) | main() → _cmd_audit_*() → Validator → stdout | yes | _cmd_audit_* (no gate) |
| Validation results | Path-B (orchestrated) | main() → Orchestrator → _run_wrapper_gate() → ToolWrapper → ValidatorResult → GateResult | yes | Orchestrator |
| manifest.yaml | Official | Orchestrator.execute() → ActionRunner.emit_manifest() | yes | Orchestrator |
| command logs | Official | Orchestrator._write_command_log_best_effort() → ActionRunner.write_command_log() | yes | Orchestrator |

---

## Appendix: Methodology

- [x] Phase 1: Surface Discovery — grep for argparse, save_state, write_text, ValidatorResult, SkillResult, set_gate, set_stage
- [x] Phase 2: State Mapping — File (state.yaml, outputs/), Process state (run_id), External services (Crossref, S2, Trifecta APIs)
- [x] Phase 3: Authority Assignment — Single-writer verification for each artifact, competing path detection
- [x] Phase 4: Pipeline Detection — Full path tracing from CLI entrypoints to filesystem writes
- [x] Phase 5: Conflict Analysis — H1 (multiple entrypoints), H2 (script bypass), H4 (double writer on state.yaml), H5 (evidence vs authority distinction for validation results)
- [x] Phase 6: Report Generation — authority-flow-audit v2.1 template, Tier 2 escalation (no Tier 3 needed)

### Heuristics Applied

| Heuristic | Finding | Status |
|-----------|---------|--------|
| H1: Multiple entrypoints → same mutation | F-04: run_real_validation.py + Orchestrator both write state.yaml | Confirmed |
| H2: Script bypass of official path | F-04: run_real_validation.py bypasses StateManager domain validation | Confirmed |
| H4: Double writer on same file | F-04: Two writers to state.yaml without coordination | Confirmed |
| H5: Evidence used as authority | Not detected — validation results are correctly treated as evidence | Clear |
