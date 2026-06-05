# Code-Path Cartographer Report

## Path Summary
Mode: entrypoint-reachability + dead-candidate-scan
Target: Full paper-writer codebase (ARS cross-reference validation)
Repository: /Users/felipe_gonzalez/Developer/paper-writer
Scope: cli, integrations, skills, validators, clients, verification
Adapters used: rg (AST grep), LSP (partial), direct code trace
Scan date: 2026-06-04

---

## Section 2: Mini Diagram

```
ENTRYPOINT TREE 1: CLI paper (main.py) — 30 commands
├── [Orchestrated path] 18 commands → Orchestrator.execute()
│   ├── StateManager → state.yaml (AUTHORITATIVE WRITE)
│   ├── FilesystemActionRunner → outputs/ (DELEGATED WRITE)
│   │   ├── LiteratureSearchAdapter → search_module → raw_results.json, screened_evidence.json
│   │   └── AcademicWriterAdapter → writer_module → outline.md, section.md
│   ├── 13 ToolWrappers → ValidatorResult (EVIDENCE, no state write)
│   │   ├── BibliographyNormalizer → validate_bibliography()
│   │   ├── RefsValidator → validate_citation_consistency()
│   │   ├── RefsMetadataValidator → validate_refs_metadata()
│   │   ├── StyleLinter → validate_style()
│   │   ├── ReportingAuditor → validate_reporting() + validate_section_structure()
│   │   ├── EthicsAuditor → EthicsValidator
│   │   ├── ProseAuditor → ProseValidator
│   │   ├── ClaimsAuditor → ClaimsValidator
│   │   ├── CitationsAuditor → CitationVerifyValidator → CrossrefClient + S2Client
│   │   ├── WritingQualityAuditor → WritingQualityValidator
│   │   ├── CodeHealthAuditor → TrifectaClient
│   │   ├── PandocRenderer → assembler → manuscript.docx/pdf
│   │   └── ZoteroImporter → references.bib
│   └── 12 Gate Validators → GateResult → StateManager.set_gate()
│
├── [func= bypass] 12 commands → direct execution, stdout only
│   ├── _cmd_audit_prose → ProseValidator
│   ├── _cmd_audit_claims → ClaimsValidator
│   ├── _cmd_audit_citations → CitationVerifyValidator → CrossrefClient + S2Client
│   ├── _cmd_audit_ethics → EthicsValidator
│   ├── _cmd_audit_writing_quality → WritingQualityValidator
│   ├── _cmd_audit_code_health → TrifectaClient
│   ├── _cmd_audit_factuality → ClaimEvidenceValidator
│   ├── _cmd_audit_tables → validate_tables_figures()
│   ├── _cmd_audit_quality_appraisal → QualityAppraisalValidator
│   ├── _cmd_gate_method → MethodGateValidator
│   ├── _cmd_trace → TrifectaClient
│   └── _cmd_graph_overview → TrifectaClient
│
└── [inline] doctor → check_all_tools + check_internal_capabilities

ENTRYPOINT TREE 2: verification/run_real_validation.py
├── Direct filesystem writes to state.yaml (SHADOW — bypasses StateManager)
├── Direct filesystem writes to references.bib
└── No imports from harness/ domain layer

ENTRYPOINT TREE 3: skills/imported/ (invoked via Tree 1)
├── literature_search/search.py → scored results
├── literature_search/chaining.py → S2 API → expanded corpus
│   └── References arXiv IDs as data strings (no arXiv API client)
└── academic_writer/drafting.py → section skeletons
    └── clients/llm_content.py → LLM client (for future content generation)
```

---

## Section 3: Connectivity Table

### High-Traffic Symbols (reached by 2+ entrypoint trees)

| Symbol | File:Line | Inbound | Outbound | Scope | Confidence | Notes |
|--------|-----------|---------|----------|-------|------------|-------|
| ProseValidator | validators/prose.py:30 | 2 | ~10 | cross-module | HIGH | Path-A (bypass) + Path-B (ProseAuditor) |
| ClaimsValidator | validators/claims.py:30 | 2 | ~8 | cross-module | HIGH | Path-A (bypass) + Path-B (ClaimsAuditor) |
| CitationVerifyValidator | validators/citation_verify.py:20 | 3 | ~6 | cross-module | HIGH | Path-A + Path-B + CitationVerifyAdapter |
| EthicsValidator | validators/ethics.py:16 | 3 | ~4 | cross-module | HIGH | Path-A + Path-B + EthicsAdapter |
| WritingQualityValidator | validators/writing_quality.py:20 | 3 | ~4 | cross-module | HIGH | Path-A + Path-B + WritingQualityAdapter |
| CrossrefClient | clients/crossref.py:15 | 1 | ~3 | cross-module | HIGH | Only CitationVerifyValidator |
| SemanticScholarClient | clients/semantic_scholar.py:15 | 1 | ~3 | cross-module | HIGH | Only CitationVerifyValidator |
| TrifectaClient | clients/trifecta.py | 2 | ~5 | cross-module | HIGH | CodeHealthAuditor + CLI trace/graph |
| state.yaml | outputs/state.yaml | 2 | N/A | filesystem | HIGH | StateManager (official) + run_real_validation.py (shadow) |

### Single-Path Symbols (reached by 1 entrypoint only)

| Symbol | File:Line | Inbound | Outbound | Scope | Confidence | Notes |
|--------|-----------|---------|----------|-------|------------|-------|
| MethodGateValidator | validators/method_gate.py:31 | 1 | ~20 | cross-module | HIGH | CLI bypass ONLY — no ToolWrapper |
| ClaimEvidenceValidator | validators/claim_evidence.py:154 | 1 | ~8 | cross-module | HIGH | CLI bypass ONLY |
| QualityAppraisalValidator | validators/quality_appraisal.py:22 | 1 | ~12 | cross-module | HIGH | CLI bypass ONLY |
| ClaimAlignmentValidator | validators/claim_alignment.py:16 | 0 | ~6 | internal | HIGH | TEST-ONLY — no production path |
| llm_content.get_llm_client | clients/llm_content.py:14 | 1 | ~3 | cross-module | MEDIUM | Only drafting.py (future use) |
| llm_content.generate_section | clients/llm_content.py:N/A | 1 | ~2 | cross-module | MEDIUM | Only drafting.py |

### ARS Cross-Reference Connectivity

| ARS Module | paper-writer Equivalent | Connectivity | Gap |
|------------|------------------------|-------------|-----|
| crossref_client.py | clients/crossref.py | **CONNECTED** — same pattern, same API, different docstrings | None |
| semantic_scholar_client.py | clients/semantic_scholar.py | **CONNECTED** — same pattern, same API | None |
| _text_similarity.py | clients/_text_similarity.py | **CONNECTED** — ported directly (our file says "Ported from ARS") | None |
| arxiv_client.py | — | **ZERO** — no arXiv client in paper-writer | Full gap |
| openalex_client.py | — | **ZERO** — no OpenAlex client | Full gap |
| temporal_integrity_audit.py | — | **ZERO** — no temporal verification | Full gap |
| contamination_signals.py | — | **ZERO** — no contamination tracking | Full gap |
| claim_audit_pipeline.py | validators/claim_alignment.py + validators/claim_evidence.py | **PARTIAL** — we have claim checking but not 6-step LLM-as-judge pipeline | Partial gap |
| verification_gate/ | validators/citation_verify.py | **PARTIAL** — we verify via Crossref+S2 but not with 4-resolver gate | Partial gap |

---

## Section 4: Evidence

### ProseValidator (validators/prose.py:30)
- Inbound: ProseAuditor.run() at integrations/tools/prose_auditor.py:55 [HIGH — import trace]
- Inbound: _cmd_audit_prose() at cli/paper/commands/audit.py:14 [HIGH — import trace]
- Outbound: engine/loader.py (loads rules) [HIGH — call chain]

### CitationVerifyValidator (validators/citation_verify.py:20)
- Inbound: CitationsAuditor.run() at integrations/tools/citations_auditor.py:54 [HIGH — import trace]
- Inbound: _cmd_audit_citations() at cli/paper/commands/audit.py:97 [HIGH — import trace]
- Inbound: CitationVerifyAdapter.execute() at skills/local/adapters.py:403-437 [HIGH — but ADAPTER NOT WIRED]
- Outbound: CrossrefClient at clients/crossref.py:15 [HIGH — direct import]
- Outbound: SemanticScholarClient at clients/semantic_scholar.py:15 [HIGH — direct import]

### MethodGateValidator (validators/method_gate.py:31)
- Inbound: _cmd_gate_method() at cli/paper/commands/gate.py:14 [HIGH — import trace]
- Inbound: NO TOOLWRAPPER — not registered in orchestrator_builder.py [HIGH — grep confirmed absence]
- Outbound: engine/loader.py (loads rules from rules/method_gate/) [HIGH — call chain]

### ClaimAlignmentValidator (validators/claim_alignment.py:16)
- Inbound: ZERO production references [HIGH — rg scan]
- Inbound: test_validators/test_claim_alignment.py (tests only) [MEDIUM — test ref]
- Outbound: internal logic only [HIGH — no external calls]

### CrossrefClient (clients/crossref.py)
- Inbound: CitationVerifyValidator at validators/citation_verify.py:12 [HIGH — import]
- Inbound: ZERO other production references [HIGH — rg confirmed]
- Outbound: urllib (stdlib) [HIGH — stdlib boundary]

### llm_content module (clients/llm_content.py)
- Inbound: drafting.py:481 (lazy import inside function) [MEDIUM — dynamic import]
- Inbound: llm_content.py:14 (self-import in __init__) [MEDIUM — circular reference]
- Outbound: external LLM API [HIGH — network boundary]

### ARS _text_similarity.py → paper-writer clients/_text_similarity.py
- Our file header: "Ported from ARS scripts/_text_similarity.py"
- Same algorithm: SequenceMatcher ratio with threshold 0.70
- Same normalization: lowercase + strip punctuation + collapse whitespace
- Byte-equivalent behavior confirmed by diff

---

## Section 5: Dead/Unwired Candidates

| Symbol | File:Line | Tier | Reason | Dynamic? | Confidence |
|--------|-----------|------|--------|----------|------------|
| CitationVerifyAdapter | skills/local/adapters.py:366 | 1 | Defined but NOT imported in orchestrator_builder.py | No | HIGH |
| EthicsAdapter | skills/local/adapters.py:406 | 1 | Defined but NOT imported in orchestrator_builder.py | No | HIGH |
| WritingQualityAdapter | skills/local/adapters.py:445 | 1 | Defined but NOT imported in orchestrator_builder.py | No | HIGH |
| ClaimAlignmentValidator | validators/claim_alignment.py:16 | 1 | Zero production refs (test-only) | No | HIGH |
| llm_content.get_llm_client | clients/llm_content.py:14 | 3 | Referenced only from drafting.py (lazy import, future use) | No | MEDIUM |
| llm_content.generate_section | clients/llm_content.py | 3 | Referenced only from drafting.py (lazy import, future use) | No | MEDIUM |

### Wired-by-Architecture (excluded from unwired scan)

| Symbol | File:Line | Wiring Type | Wiring Point |
|--------|-----------|-------------|-------------|
| BibliographyNormalizer | integrations/tools/bibtex_tidy.py | CONTAINER_WIRED | orchestrator_builder.py:95 |
| RefsValidator | integrations/tools/refs_validator.py | CONTAINER_WIRED | orchestrator_builder.py:96 |
| RefsMetadataValidator | integrations/tools/refs_metadata_validator.py | CONTAINER_WIRED | orchestrator_builder.py:97 |
| StyleLinter | integrations/tools/style_auditor.py | CONTAINER_WIRED | orchestrator_builder.py:98 |
| ReportingAuditor | integrations/tools/reporting_auditor.py | CONTAINER_WIRED | orchestrator_builder.py:99 |
| EthicsAuditor | integrations/tools/ethics_auditor.py | CONTAINER_WIRED | orchestrator_builder.py:100 |
| ProseAuditor | integrations/tools/prose_auditor.py | CONTAINER_WIRED | orchestrator_builder.py:101 |
| ClaimsAuditor | integrations/tools/claims_auditor.py | CONTAINER_WIRED | orchestrator_builder.py:102 |
| CitationsAuditor | integrations/tools/citations_auditor.py | CONTAINER_WIRED | orchestrator_builder.py:103 |
| WritingQualityAuditor | integrations/tools/writing_quality_auditor.py | CONTAINER_WIRED | orchestrator_builder.py:104 |
| CodeHealthAuditor | integrations/tools/code_health_auditor.py | CONTAINER_WIRED | orchestrator_builder.py:105 |
| PandocRenderer | integrations/tools/pandoc.py | CONTAINER_WIRED | orchestrator_builder.py:106 |
| ZoteroImporter | integrations/tools/zotero_import.py | CONTAINER_WIRED | orchestrator_builder.py:107 |
| LiteratureSearchAdapter | skills/local/adapters.py:25 | CONTAINER_WIRED | orchestrator_builder.py:88 |
| AcademicWriterAdapter | skills/local/adapters.py:258 | CONTAINER_WIRED | orchestrator_builder.py:89 |

---

## Section 6: Dynamic Dispatch / Uncertainty

| Location | Mechanism | Config Point | Impact |
|----------|-----------|-------------|--------|
| orchestrator_builder.py:82 | dict[str, ToolWrapper] lookup | self.wrappers[command] | 13 symbols resolved at runtime by command name |
| orchestrator_builder.py:87 | dict[str, SkillAdapter] lookup | self._skill_adapters[name] | 2 symbols resolved at runtime by skill name |
| filesystem_action_runner.py:193 | adapter presence check | `if adapter:` branch | 5 commands have dual paths (adapter vs fallback) |
| drafting.py:481 | lazy import | `from clients.llm_content import generate_section` | llm_content module only loaded when needed |
| main.py:51 | ascending filesystem search | outputs/state.yaml marker | project root resolved dynamically |

---

## Section 7: Handoff to Authority Flow Audit

### Connectivity Evidence
- Total symbols mapped: 42
- Symbols with multiple inbound paths: **9** (5 validators with dual path via bypass+wrapper, 4 shared symbols)
- Symbols with zero inbound paths (candidates): **5** (3 adapters + ClaimAlignmentValidator + partial llm_content)
- Symbols with dynamic dispatch gaps: **5** (dict lookups, adapter presence checks, lazy imports)

### Confirmed Findings from Authority-Flow Audit

| Finding | Cartographer Evidence | Confirmed? |
|---------|----------------------|-----------|
| **F-02: 12 commands bypass Orchestrator** | 12 `set_defaults(func=)` in main.py, 18 commands go through Orchestrator. Confirmed by tracing `func=args` vs `OrchestratorRequest` paths. | ✅ CONFIRMED |
| **F-03: 3 adapters not wired** | CitationVerifyAdapter, EthicsAdapter, WritingQualityAdapter defined in skills/local/adapters.py but NOT imported in orchestrator_builder.py. rg confirms zero production refs outside adapters.py. | ✅ CONFIRMED |
| **F-04: run_real_validation.py shadow writer** | Tree 2 writes state.yaml without importing StateManager. No harness/domain imports in verification/run_real_validation.py. | ✅ CONFIRMED |

### New Findings from Cartographer Scan

| Finding | Evidence | Severity |
|---------|----------|----------|
| **C-01: MethodGateValidator has NO ToolWrapper** | Only reached via CLI bypass (_cmd_gate_method). Not registered in builder. Gate "style_passed" cannot be set by this validator through the Orchestrator. | MEDIUM |
| **C-02: ClaimEvidenceValidator has NO ToolWrapper** | Only reached via _cmd_audit_factuality bypass. No gate update path. | MEDIUM |
| **C-03: QualityAppraisalValidator has NO ToolWrapper** | Only reached via _cmd_audit_quality_appraisal bypass. No gate update path. | MEDIUM |
| **C-04: ClaimAlignmentValidator is TEST-ONLY** | Zero production references. Not imported by any ToolWrapper or CLI command. Only referenced by tests. | LOW |
| **C-05: CrossrefClient and S2Client have single consumer** | Only CitationVerifyValidator uses them. No other validator or ToolWrapper reaches the API clients directly. | INFO |
| **C-06: llm_content module is future-use only** | Lazy-imported by drafting.py but not actively used in production pipeline. | INFO |
| **C-07: ARS _text_similarity was ported correctly** | Byte-equivalent behavior, same threshold (0.70), header says "Ported from ARS". | INFO |

### ARS Gap Validation

| Gap Claimed in Previous Analysis | Cartographer Evidence | Confirmed? |
|--------------------------------|----------------------|-----------|
| arXiv client missing | ZERO imports of arXiv API in entire codebase. Only arXiv ID strings as data in chaining.py and search.py. | ✅ CONFIRMED |
| OpenAlex client missing | ZERO references to "openalex" anywhere in codebase. | ✅ CONFIRMED |
| Temporal verification missing | ZERO references to "temporal" in any production code. | ✅ CONFIRMED |
| Contamination signals missing | ZERO references to "contamination" in any production code. | ✅ CONFIRMED |
| PRISMA support partial | rules/prisma.yml exists (146 lines) but no dedicated PRISMA ToolWrapper or gate. | ✅ CONFIRMED (partial) |
| No review/revise pipeline | State machine has 8 stages. No "review" or "revise" stage exists. | ✅ CONFIRMED |
| No Material Passport | No passport schema, no passport.yaml handling, no passport adapter. | ✅ CONFIRMED |

### Mini Diagrams for Authority Traces

```
DUAL-PATH VALIDATORS (bypass + ToolWrapper):

  CLI bypass ──→ ProseValidator ──→ stdout (no gate update)
  CLI orch  ──→ ProseAuditor ──→ ProseValidator ──→ ValidatorResult ──→ GateResult ──→ state.yaml

SINGLE-PATH VALIDATORS (bypass only, NO ToolWrapper):

  CLI bypass ──→ MethodGateValidator ──→ stdout (no gate update)
                  ↑ NO ToolWrapper path exists

  CLI bypass ──→ ClaimEvidenceValidator ──→ stdout (no gate update)
                  ↑ NO ToolWrapper path exists

  CLI bypass ──→ QualityAppraisalValidator ──→ stdout (no gate update)
                  ↑ NO ToolWrapper path exists

ORPHANED ADAPTERS (defined, never wired):

  CitationVerifyAdapter ← defined in skills/local/adapters.py:366
    └── NEVER imported by orchestrator_builder.py
    └── Competes with CitationsAuditor (ToolWrapper that IS wired)
    └── Both wrap CitationVerifyValidator — redundant

  EthicsAdapter ← defined in skills/local/adapters.py:406
    └── NEVER imported by orchestrator_builder.py
    └── Competes with EthicsAuditor (ToolWrapper that IS wired)

  WritingQualityAdapter ← defined in skills/local/adapters.py:445
    └── NEVER imported by orchestrator_builder.py
    └── Competes with WritingQualityAuditor (ToolWrapper that IS wired)
```

### Suggested Next Steps

1. **Resolve C-01/C-02/C-03** — Either create ToolWrappers for MethodGate, ClaimEvidence, and QualityAppraisal (consistent with the 13 existing wrappers), or document that they are intentionally bypass-only.
2. **Resolve F-03/C-07 orphaned adapters** — The 3 skill adapters duplicate functionality already covered by ToolWrappers. Decide: remove them or merge them.
3. **Resolve C-04** — ClaimAlignmentValidator has zero production reachability. Either wire it into a ToolWrapper or remove it.
4. **Port ARS gaps in priority order** — arXiv client (S), temporal verification (M), PRISMA expansion (M), contamination signals (S).
