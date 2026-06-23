# Informe de Exploración SDD: paper-core-preflight

**Fecha:** 2026-06-19
**Rama:** main
**Estado:** Exploración completa, SDD generados, apply NO ejecutado
**Cobertura:** 100% de capas del repositorio

---

## 1. Resumen Ejecutivo

Paper Writer tiene un core sólido: Orchestrator 3-phase (PREPARE/APPLY/VERIFY), state machine forward-only con 13 hard gates y 2 soft gates, persistencia atómica YAML, fail-closed enforcement. El problema no es el core — es que el core no expone su estado de forma estructurada a agentes externos. El cambio es: un resolvedor read-only que computa una vista estructurada del estado existente. 8 tareas, ~4 archivos nuevos, ~4 modificados, sin cambios al dominio.

**Key facts verified:**
- `ManuscriptState` en `harness/domain/state.py:12` — 232 lines, 8 stages, 13 required gates, 2 soft gates
- `Orchestrator` en `harness/services/orchestrator.py:56` — 696 lines, 3-phase execute()
- `PIPELINE_MAP` en `cli/paper/dispatch.py:192` — 16 pipeline commands
- `build_orchestrator_dependencies()` en `harness/services/orchestrator_builder.py:61` — full DI wiring
- 14 tool wrappers registered in builder (lines 99-114)
- 2 skill adapters wired: `LiteratureSearchAdapter`, `AcademicWriterAdapter` (lines 87-90)

---

## 2. Arquitectura General del Repositorio

Hexagonal architecture: **ports** (interfaces) → **adapters** (implementations) → **services** (domain logic) → **CLI** (entry).

```
paper-writer/
├── cli/paper/           # CLI entry, parser, dispatch, output, errors, commands/
├── harness/
│   ├── domain/state.py  # ManuscriptState — THE domain entity
│   ├── ports/           # 7 interfaces: ActionRunner, ArtifactChecker, StateRepository,
│   │                    #   ToolResolver, ToolWrapper, SkillAdapter, PaperSearchProvider
│   ├── adapters/        # 4 implementations: filesystem, yaml, local_tool_resolver
│   └── services/        # Orchestrator, StateManager, Gates, Doctor, Assembler,
│                        #   VerifyArtifacts, ReviewConfig, OrchestratorBuilder
├── integrations/tools/  # 14 concrete tool wrappers (bibtex-tidy, vale, pandoc, etc.)
├── clients/             # 9 HTTP clients (crossref, semantic_scholar, openalex, arxiv, zotero, etc.)
├── skills/
│   ├── imported/        # literature_search (scoring.py, chaining.py, search.py)
│   │                    # academic_writer (prompt-only with pyzotero)
│   └── local/           # adapters.py, thesaurus/, mesh-import/, trifecta-mcp/, essay_crafter/, science-bundle/
├── validators/          # 23 validators (refs, citations, citation_verify, bibliography, structure, prose, etc.)
├── rules/               # 6 rule modules (prose, claims, ethics, citations, writing_quality, method_gate)
├── schemas/             # 4 JSON schemas (claim_audit, finding, method_gate, prose_audit)
├── engine/              # deduplicator.py, formatter.py, loader.py
├── parsers/             # manuscript.py (IMRAD detection), source_map.py (position tracking)
├── templates/           # journals/ (nature, elsevier, springer), manuscript.qmd, references.bib
├── styles/              # vale/ (4 rules), csl/ (APA, Vancouver)
├── verification/        # run_real_validation.py (local-data cases)
├── benchmarks/          # Performance baselines
├── .github/workflows/   # ci.yml, release.yml, security.yml, live-smoke.yml
├── tests/               # pytest, e2e/ subdirectory
├── Makefile             # init, test, lint, typecheck, verify, validate
└── pyproject.toml       # v0.1.0, Python>=3.10, mcp[cli], pyyaml, pyzotero
```

**Entry flow:** `cli/paper/main.py:22` → `parser.py:46` (build_parser) → `dispatch.py:224` (execute) → `Orchestrator.execute()` → `ActionRunner.run_action()` → adapters/skills → gate verification → state update → manifest.

**Error taxonomy** (`cli/paper/errors.py`): `UserInputError` → exit 2, `ExternalServiceError` → exit 3, catch-all → exit 1, `KeyboardInterrupt` → exit 130.

---

## 3. Core del Workflow — Mapa Estructural Completo

### 3a. ManuscriptState

| Attribute | Value | File:Line |
|-----------|-------|-----------|
| Stage order | bootstrap → search → screen → outline → drafting → validating → rendering → rendered | `harness/domain/state.py:31-40` |
| Required gates | 13 (repo_initialized, search_completed, screened_evidence, outline_drafted, sections_completed, bib_imported, bib_normalized, citations_resolved, refs_validated, style_passed, reporting_passed, render_passed, ready_for_delivery) | `harness/domain/state.py:44-60` |
| Soft gates | 2 (citation_verified, ethics_passed) | `harness/domain/state.py:62-67` |
| LEGACY_STAGE_MAP | {"verified": "rendered"} | `harness/domain/state.py:70` |
| Transition enforcement | Forward-only, no skip, DomainStateError on violation | `harness/domain/state.py:149-182` |
| Gate reset | reset_downstream_gates(draft/bib/search) — clears dependent gates + downgrades stage | `harness/domain/state.py:184-232` |
| Stage preconditions | STAGE_PRECONDITIONS maps each stage to required gates | `harness/domain/state.py:73-91` |
| Validate | Validates stage name, gate types, stage-gates consistency | `harness/domain/state.py:93-141` |

### 3b. Ports (Interfaces)

| Port | File | Methods | Purpose |
|------|------|---------|---------|
| ActionRunner | `harness/ports/action_runner.py:5` | run_action, emit_manifest, write_command_log | Execute side-effect actions |
| ArtifactChecker | `harness/ports/artifact_checker.py:4` | check_dir_exists, check_file_exists, check_any_file_exists, get_full_path_str | Artifact presence checks |
| StateRepository | `harness/ports/state_repository.py:12` | exists, load, save | ManuscriptState persistence |
| ToolResolver | `harness/ports/tool_resolver.py:21` | resolve(tool_id, min_version) → ToolResolution | External tool binary resolution |
| ToolWrapper | `harness/ports/tool_wrapper.py:47` | run(artifacts, context) → ValidatorResult, is_available(), name, gate | External validation tool wrappers |
| SkillAdapter | `harness/ports/skill_adapter.py:49` | execute(command, inputs, context) → SkillResult, name | Domain skill adapters |
| PaperSearchProvider | `harness/ports/paper_search_provider.py:162` | search(query, sources, limit, **kwargs) → SearchProviderResult | Paper search providers |

### 3c. Adapters

| Adapter | File | Lines | Key behavior |
|---------|------|-------|-------------|
| FilesystemActionRunner | `harness/adapters/filesystem_action_runner.py:18` | 717 | Command dispatch, run lineage (.run_id, run.yaml, latest symlink), best-effort writes, path traversal prevention |
| FilesystemArtifactChecker | `harness/adapters/filesystem_artifact_checker.py` | ~30 | check_dir_exists, check_file_exists, check_any_file_exists |
| LocalToolResolver | `harness/adapters/local_tool_resolver.py` | ~50 | Waterfall: ENV → local bin → global PATH |
| YamlFileStateRepository | `harness/adapters/yaml_repository.py:9` | 72 | Atomic write via .tmp + rename, legacy stage upgrade, validate on load |

### 3d. Services

| Service | File | Lines | Purpose |
|---------|------|-------|---------|
| Orchestrator | `harness/services/orchestrator.py:56` | 696 | 3-phase execute(): PREPARE (load state, validate preconditions) → APPLY (run_action + downstream gate reset) → VERIFY (gate evaluation, stage transition, manifest emit) |
| OrchestratorBuilder | `harness/services/orchestrator_builder.py:61` | 126 | DI wiring: builds StateManager, ArtifactChecker, ActionRunner, 14 ToolWrappers, 2 SkillAdapters |
| StateManager | `harness/services/state_manager.py:13` | 94 | Coordinates ManuscriptState + StateRepository: load, save, set_gate, set_stage, reset_downstream_gates |
| Gates | `harness/services/gates.py:32` | 461 | run_gate() + 12 concrete validators: repo_initialized, search_completed, screened_evidence, outline_drafted, sections_completed, bib_normalized, render_passed, ready_for_delivery, citation_verify, ethics_passed, validator_gate, citation_verdict |
| Doctor | `harness/services/doctor.py:14` | 388 | check_tool() + check_all_tools() — reports tool availability and degraded mode |
| Assembler | `harness/services/assembler.py:26` | 96 | 7-section canonical order (abstract→conclusion), ANSI sanitization |
| Verify Artifacts | `harness/services/verify_artifacts.py:29` | 477 | 4 mandatory artifacts: search_manifest.yaml, evidence_matrix.csv, included_excluded_ledger.yaml, claim_citation_audit.yaml |
| Review Config | `harness/services/review_config.py:25` | 73 | load/save review_config.yaml (mode, search_window, amendments) |

### 3e. Tool Wrappers (14 total)

Registered in `harness/services/orchestrator_builder.py:99-114`:

| Wrapper | Class | Gate | External Tool |
|---------|-------|------|--------------|
| lint_bib | BibliographyNormalizer | bib_normalized | bibtex-tidy |
| check_refs | RefsValidator | citations_resolved | pure Python |
| check_refs_metadata | RefsMetadataValidator | refs_validated | pure Python |
| lint_style | StyleLinter | style_passed | vale |
| audit_reporting | ReportingAuditor | reporting_passed | pure Python |
| audit_ethics | EthicsAuditor | ethics_passed | pure Python |
| audit_prose | ProseAuditor | style_passed | pure Python |
| audit_claims | ClaimsAuditor | style_passed | pure Python |
| audit_citations | CitationsAuditor | citations_resolved | pure Python |
| audit_writing_quality | WritingQualityAuditor | style_passed | pure Python |
| audit_code_health | CodeHealthAuditor | style_passed | Trifecta |
| render | PandocRenderer | render_passed | Pandoc |
| import_bib | ZoteroImporter | bib_imported | pyzotero |
| zotero_sync | ZoteroSyncImporter | bib_imported | pyzotero |

### 3f. SkillAdapters

Wired in `harness/services/orchestrator_builder.py:87-90`:

| Adapter | Commands | Source Logic |
|---------|----------|-------------|
| LiteratureSearchAdapter | search, screen, chain, export_bib | `skills/imported/literature_search/search.py`, `scoring.py` (589 lines), `chaining.py` |
| AcademicWriterAdapter | draft_outline, draft_section, draft_all | `skills/imported/academic_writer/drafting.py` (prompt-based) |

---

## 4. CLI — Inventario Completo

### 4a. Architecture

```
cli/paper/main.py:22       → main() — entrypoint + error boundary
cli/paper/parser.py:46     → build_parser() — argparse with subparsers
cli/paper/dispatch.py:224  → execute() — routes to Phase 0 or PIPELINE_MAP
cli/paper/output.py:45     → configure() + summary() — 5-channel output
cli/paper/errors.py:13     → UserInputError (exit 2), ExternalServiceError (exit 3)
cli/paper/project.py       → resolve_project_root() — CWD ascending
cli/paper/runtime.py       → configure_logging(), temporary_sigint_handler()
```

**Error codes:** 0 (success), 1 (internal/gate), 2 (UserInputError), 3 (ExternalServiceError), 130 (KeyboardInterrupt).

### 4b. PIPELINE_MAP Commands (16)

Defined in `cli/paper/dispatch.py:192-221`:

| CLI Key | Orchestrator Command | Failure Policy | Notes |
|---------|---------------------|----------------|-------|
| init | init | stop_on_error | needs_review_config=False |
| search | search | stop_on_error | |
| chain | chain | stop_on_error | |
| export-bib | export_bib | stop_on_error | |
| screen | screen | stop_on_error | |
| draft:outline | draft_outline | stop_on_error | |
| draft:section | draft_section | stop_on_error | |
| draft:all | draft_all | stop_on_error | |
| protocol | protocol | stop_on_error | |
| lint:bib | lint_bib | continue_on_error | |
| lint:style | lint_style | continue_on_error | |
| check:refs | check_refs | continue_on_error | |
| audit:reporting | audit_reporting | continue_on_error | |
| import:bib | import_bib or zotero_sync | stop_on_error | runtime resolver |
| render | render | stop_on_error | |
| verify | verify | stop_on_error | |

### 4c. Phase 0 Commands (direct callback, bypass PIPELINE_MAP)

Defined in `cli/paper/parser.py` with `set_defaults(func=...)`:

| Command | Handler | Output Policy |
|---------|---------|---------------|
| doctor | `commands/doctor.py` | text-only |
| audit:prose | `_cmd_audit_prose` | json-capable |
| audit:claims | `_cmd_audit_claims` | json-capable |
| audit:citations | `_cmd_audit_citations` | json-capable |
| audit:ethics | `_cmd_audit_ethics` | json-capable |
| audit:writing-quality | `_cmd_audit_writing_quality` | json-capable |
| audit:factuality | `_cmd_audit_factuality` | json-capable |
| audit:tables | `_cmd_audit_tables` | json-capable |
| audit:quality-appraisal | `_cmd_audit_quality_appraisal` | json-capable |
| audit:code-health | `_cmd_audit_code_health` | json-capable |
| gate:method | `_cmd_gate_method` | json-capable |
| trace | `_cmd_trace` | json-capable |
| graph-overview | `_cmd_graph_overview` | json-capable |
| zotero (7 subcommands) | `commands/zotero.py` | mixed |
| thesaurus (6 subcommands) | `commands/thesaurus.py` | mixed |
| mesh (5 subcommands) | `commands/mesh.py` | mixed |

### 4d. Global Flags

Defined in `cli/paper/parser.py:47-83`:

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| --version / -V | action=version | — | Package version |
| --project / -C | Path | None (auto-detect CWD) | Project root |
| --output-format | text/json | text | Output format |
| --quiet | flag | False | Suppress stderr info/warnings |
| --verbose | flag | False | DEBUG logging to stderr |

---

## 5. Estado y Persistencia

### 5a. state.yaml — Fuente Única de Verdad

- **Writer:** `YamlFileStateRepository.save()` (`harness/adapters/yaml_repository.py:48`) — atomic write via .tmp + rename
- **Readers:** StateManager, Orchestrator, gate validators
- **NOT regenerable** — contains the canonical stage + gates state
- **Schema:** `{stage: str, gates: {gate_name: bool, ...}}` with header `# Schema version: 1.0`

### 5b. review_config.yaml

- **File:** `harness/services/review_config.py:25`
- **Contents:** `{mode: rapid|academic, search_window: {start_year, end_year}|null, amendments: [...]}`
- **Created at:** `paper init` via `save_review_config()`
- **Read at:** Every PIPELINE_MAP command dispatch (`dispatch.py:265-273`)

### 5c. Run Lineage

- **`.run_id`:** `outputs/.run_id` — stores current run ID (timestamp-based: `YYYYMMDDTHHMMSS`)
- **`run.yaml`:** `outputs/runs/{run_id}/run.yaml` — metadata: run_id, command, created_at, status, artifacts
- **`latest` symlink:** `outputs/latest` → `outputs/runs/{run_id}/` — updated on every run
- **Best-effort:** All writes are try/except wrapped; failure doesn't block command execution

### 5d. Artifact Inventory

| Artifact | Path | Source of Truth | Regenerable | Best-Effort |
|----------|------|----------------|-------------|-------------|
| state.yaml | outputs/state.yaml | Orchestrator | No | No |
| review_config.yaml | outputs/review_config.yaml | CLI init | No | No |
| manifest.yaml | outputs/manifest.yaml | Orchestrator (verify) | Yes | No |
| .run_id | outputs/.run_id | ActionRunner | Yes | Yes |
| run.yaml | outputs/runs/{id}/run.yaml | ActionRunner | Yes | Yes |
| latest symlink | outputs/latest | ActionRunner | Yes | Yes |
| search/ | outputs/latest/search/ | LiteratureSearchAdapter | Yes | No |
| drafts/ | outputs/latest/drafts/ | AcademicWriterAdapter | Yes | No |
| render/ | outputs/latest/render/ | PandocRenderer | Yes | No |
| verify/ | outputs/latest/verify/ | VerifyArtifacts | Yes | No |
| logs/ | outputs/logs/ | ActionRunner.write_command_log | Yes | Yes |

---

## 6. Flujo de Datos y Artefactos

```
                    ┌─────────────────────────────────────────────────┐
                    │              CLI (parser.py → dispatch.py)      │
                    │   Global flags → Phase 0 or PIPELINE_MAP       │
                    └────────────────────┬────────────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────────────┐
                    │              Orchestrator.execute()              │
                    │  PREPARE → APPLY → VERIFY (3-phase)            │
                    └────────────────────┬────────────────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
    ┌─────────▼──────────┐   ┌──────────▼──────────┐   ┌──────────▼──────────┐
    │    PREPARE PHASE   │   │    APPLY PHASE      │   │   VERIFY PHASE      │
    │  Load state.yaml   │   │  ActionRunner       │   │  Gate validators    │
    │  Validate gates    │   │    .run_action()    │   │  Stage transition   │
    │  Preconditions     │   │    → SkillAdapters  │   │  Gate updates       │
    └────────────────────┘   │    → ToolWrappers   │   │  State persist      │
                             │    → Adapters        │   │  Manifest emit      │
                             └──────────┬──────────┘   └──────────┬──────────┘
                                        │                          │
                    ┌───────────────────┼──────────────────────────┘
                    │                   │
          ┌─────────▼──────────┐  ┌────▼──────────────┐
          │    ARTIFACTS       │  │    STATE UPDATE    │
          │  search/           │  │  state.yaml        │
          │  drafts/           │  │  stage transition  │
          │  render/           │  │  gate values       │
          │  verify/           │  │  manifest.yaml     │
          │  logs/             │  │  run.yaml          │
          └────────────────────┘  └────────────────────┘
```

---

## 7. Mapa de Invocación

| CLI Command | Dispatch Handler | Orchestrator Command | Gate(s) Verified | Next Stage |
|-------------|-----------------|---------------------|-----------------|------------|
| paper init | PIPELINE_MAP['init'] | init | repo_initialized | search |
| paper search | PIPELINE_MAP['search'] | search | search_completed | screen |
| paper chain | PIPELINE_MAP['chain'] | chain | search_completed | screen |
| paper screen | PIPELINE_MAP['screen'] | screen | screened_evidence | outline |
| paper export-bib | PIPELINE_MAP['export-bib'] | export_bib | screened_evidence | — |
| paper draft outline | PIPELINE_MAP['draft:outline'] | draft_outline | outline_drafted | drafting |
| paper draft section | PIPELINE_MAP['draft:section'] | draft_section | sections_completed | validating (if complete) |
| paper draft all | PIPELINE_MAP['draft:all'] | draft_all | sections_completed | validating (if complete) |
| paper lint bib | PIPELINE_MAP['lint:bib'] | lint_bib | bib_normalized (via wrapper) | rendering (if all ready) |
| paper lint style | PIPELINE_MAP['lint:style'] | lint_style | style_passed (via wrapper) | rendering (if all ready) |
| paper check refs | PIPELINE_MAP['check:refs'] | check_refs | citations_resolved + refs_validated + citation_verified | rendering (if all ready) |
| paper audit reporting | PIPELINE_MAP['audit:reporting'] | audit_reporting | reporting_passed (via wrapper) | rendering (if all ready) |
| paper import bib | PIPELINE_MAP['import:bib'] | import_bib | bib_imported + bib_normalized | — |
| paper render | PIPELINE_MAP['render'] | render | render_passed + render wrapper | rendered |
| paper verify | PIPELINE_MAP['verify'] | verify | ready_for_delivery + citation_verified + ethics_passed | rendered |
| paper audit prose | Phase 0 callback | — | — (standalone) | — |
| paper gate method | Phase 0 callback | — | — (standalone) | — |

---

## 8. Mapa de Autoridad de Estado

| Authority | Artifact | Owner | Mutated By |
|-----------|----------|-------|-----------|
| Pipeline stage + gates | state.yaml | ManuscriptState (domain) | Orchestrator via StateManager |
| Review mode | review_config.yaml | ReviewConfig service | CLI init only |
| Run lineage | .run_id, run.yaml, latest symlink | FilesystemActionRunner | Every command |
| Final snapshot | manifest.yaml | Orchestrator (verify only) | paper verify |
| Search results | search/*.json | LiteratureSearchAdapter | paper search/chain |
| Drafts | drafts/*.md | AcademicWriterAdapter | paper draft:* |
| Rendered output | render/* | PandocRenderer | paper render |
| Verify artifacts | verify/* | VerifyArtifacts service | paper verify |

**No duplicate authorities.** state.yaml is the single source of truth for stage + gates. review_config.yaml is the single source of truth for mode. No other artifact can override these.

---

## 9. Grafo de Dependencias de Capabilidades

```
Orchestrator
  ├── StateManager
  │     └── StateRepository (YamlFileStateRepository)
  ├── ActionRunner (FilesystemActionRunner)
  │     ├── SkillAdapter: LiteratureSearchAdapter
  │     │     ├── PaperSearchProvider (fixture/mcp/consensus/consensus_mcp)
  │     │     │     └── Clients (crossref, semantic_scholar, openalex, arxiv)
  │     │     └── scoring.py (deduplicate, classify_tier, calculate_final_score)
  │     └── SkillAdapter: AcademicWriterAdapter
  │           └── drafting.py (draft_outline, draft_section, draft_all)
  ├── ArtifactChecker (FilesystemArtifactChecker)
  ├── ToolWrapper × 14
  │     ├── BibliographyNormalizer → ToolResolver → bibtex-tidy
  │     ├── StyleLinter → ToolResolver → vale
  │     ├── PandocRenderer → ToolResolver → pandoc
  │     ├── RefsValidator (pure Python)
  │     ├── RefsMetadataValidator (pure Python)
  │     ├── ReportingAuditor (pure Python)
  │     ├── EthicsAuditor (pure Python)
  │     ├── ProseAuditor (pure Python)
  │     ├── ClaimsAuditor (pure Python)
  │     ├── CitationsAuditor (pure Python)
  │     ├── WritingQualityAuditor (pure Python)
  │     ├── CodeHealthAuditor → Trifecta MCP
  │     ├── ZoteroImporter → pyzotero
  │     └── ZoteroSyncImporter → pyzotero
  └── Gates (run_gate + 12 validators)
        └── ArtifactChecker (for filesystem checks)
```

---

## 10. MCP Ecosystem

| MCP Server | Transport | Location | Purpose |
|------------|-----------|----------|---------|
| Paper MCP | stdio, Node.js | External | Paper search (search_papers, get_paper) |
| Consensus REST | HTTP | External | 200M+ peer-reviewed papers |
| Consensus MCP | streamable_http | External | Consensus via MCP protocol |
| Trifecta MCP | stdio | External | Code graph analysis (callers, callees, ast_hover) |

**Paper Writer is NOT an MCP server.** It is a CLI tool that consumes MCP servers as clients.

**Future planned MCP tools** (from `openspec/`): `paper_status`, `paper_continue`, `paper_preflight`, `paper_execute`, `paper_get_artifacts`, `paper_get_blockers`.

---

## 11. Search Providers y Clients

### Search Providers

Registered in `harness/ports/paper_search_provider.py:461-513`:

| Provider | Env Value | Implementation | Source |
|----------|-----------|---------------|--------|
| FixturePaperSearchProvider | `fixture` | Deterministic JSON fixture | `paper_search_provider.py:410` |
| McpPaperSearchProvider | `mcp` | Paper MCP server | `integrations/tools/mcp_paper_client.py` |
| ConsensusSearchProvider | `consensus` | Consensus REST API | `integrations/tools/consensus_client.py` |
| ConsensusRemoteMcpSearchProvider | `consensus_mcp_remote` | Consensus via MCP | `integrations/tools/consensus_mcp_client.py` |

**No fallback.** Provider must be explicitly set via `PAPER_SEARCH_PROVIDER` env var. Missing env → `ValueError`.

### HTTP Clients

Located in `clients/`:

| Client | File | Purpose |
|--------|------|---------|
| CrossRef | `clients/crossref.py` | DOI resolution, metadata |
| Semantic Scholar | `clients/semantic_scholar.py` | Citations, paper details |
| OpenAlex | `clients/openalex.py` | Open access, citations |
| ArXiv | `clients/arxiv.py` | Preprint search |
| Zotero | `clients/zotero.py` | Library sync |
| Trifecta | `clients/trifecta.py` | Code graph API |
| LLM Content | `clients/llm_content.py` | LLM content generation |
| Text Similarity | `clients/_text_similarity.py` | Embedding similarity |
| Retry | `clients/_retry.py` | Retry decorator |

---

## 12. Skills y Adaptadores

### Imported Skills

| Skill | Path | Type | Key Files |
|-------|------|------|-----------|
| literature_search | `skills/imported/literature_search/` | Executable | search.py, scoring.py (589 lines), chaining.py, SKILL.md |
| academic_writer | `skills/imported/academic_writer/` | Prompt-only | drafting.py (uses pyzotero>=1.13.1) |

### Local Skills

| Skill | Path | Type | Purpose |
|-------|------|------|---------|
| thesaurus | `skills/local/thesaurus/` | Separate package (SQLite+FTS5) | Medical terminology |
| mesh-import | `skills/local/mesh-import/` | Separate package (lxml) | MeSH descriptor parsing |
| trifecta-mcp | `skills/local/trifecta-mcp/` | MCP integration | Code graph analysis |
| essay_crafter | `skills/local/essay_crafter/` | Skill | Essay generation |
| science-bundle | `skills/local/science-bundle/` | Legacy scripts | Science utilities |
| workflow_skill_creator | `skills/local/` | 9 agents, 84 Python files | Skill creation |

### Adapters

`skills/local/adapters.py` — 759 lines, bridges imported skills into harness ports:

| Adapter | Commands | Real Logic Used |
|---------|----------|-----------------|
| LiteratureSearchAdapter | search, screen, chain, export_bib | scoring.deduplicate(), scoring.classify_tier(), scoring.calculate_final_score(), search.search(), search.screen(), search.papers_to_bibtex(), chaining.iterative_search() |
| AcademicWriterAdapter | draft_outline, draft_section, draft_all | writer_module.draft_outline(), writer_module.draft_section(), writer_module.draft_all() |

---

## 13. Validadores y Reglas

### Validators (24)

Located in `validators/`:

| Validator | File | Purpose |
|-----------|------|---------|
| refs | refs.py | Citation-to-bib consistency |
| citations | citations.py | Citation format checking |
| citation_verify | citation_verify.py | DOI resolution verification |
| bibliography | bibliography.py | BibTeX structure validation |
| structure | structure.py | Manuscript structure checks |
| prose | prose.py | Scientific prose analysis |
| claims | claims.py | Claim detection |
| claim_alignment | claim_alignment.py | Claim-evidence alignment |
| ethics | ethics.py | AI disclosure compliance |
| writing_quality | writing_quality.py | AI-typical writing patterns |
| style | style.py | Style rules |
| reporting | reporting.py | Reporting checklist audit |
| method_gate | method_gate.py | EQUATOR-derived checklist gate |
| code_health | code_health.py | Dead code detection |
| quality_appraisal | quality_appraisal.py | Study quality scoring (5 dimensions) |
| preset | preset.py | Journal preset validation |
| gate_verdict | gate_verdict.py | 4-tier severity system (none/low_warn/med_warn/high_warn) |
| contamination_signals | contamination_signals.py | Data contamination detection |
| academic_evidence | academic_evidence.py | Academic evidence quality |
| table_figure | table_figure.py | Table/figure validation |
| citation_format | citation_format.py | Citation format enforcement |
| claim_evidence | claim_evidence.py | Claim-evidence mapping |
| protocol_generator | protocol_generator.py | Reproducibility protocol |
| doctor | (via services/doctor.py) | Tool/capability checks |

### GateVerdict System

`validators/gate_verdict.py:1-156` — 4-tier severity:

| Tier | Behavior | Example |
|------|----------|---------|
| none | Gate passes cleanly | All citations verified |
| low_warn | Gate passes, advisory finding | Coverage gap in citations |
| med_warn | Gate passes, flagged for review | Title mismatch |
| high_warn | **Gate REFUSED**, blocks progression | Fabricated reference detected |

### Rules (6 modules)

Located in `rules/`:

| Module | Path | Purpose |
|--------|------|---------|
| prose | rules/prose/ | Prose quality rules |
| claims | rules/claims/ | Claim validation rules |
| ethics | rules/ethics/ | Ethics compliance rules |
| citations | rules/citations/ | Citation rules |
| writing_quality | rules/writing_quality/ | Writing quality rules |
| method_gate | rules/method_gate/ | Methodological gate rules |

### Schemas (4)

Located in `schemas/`:

| Schema | File |
|--------|------|
| claim_audit | claim_audit.schema.json |
| finding | finding.schema.json |
| method_gate | method_gate.schema.json |
| prose_audit | prose_audit.schema.json |

---

## 14. Parsers y Engine

### Parsers

| Parser | File | Lines | Purpose |
|--------|------|-------|---------|
| ManuscriptParser | `parsers/manuscript.py:10` | 235 | IMRAD heading detection (8 patterns), format detection by extension (.md, .tex, .txt), sentence extraction with abbreviation awareness |
| SourceMap | `parsers/source_map.py:16` | 139 | Position tracking (line, column, char_offset), clean↔original text mapping |

**Key data structures:**
- `Manuscript(path, format, clean_text, source_map, sections, sentences)` — `manuscript.py:32`
- `Section(heading, text, line_start, line_end)` — `manuscript.py:22`
- `Sentence(text, line, col, char_start, char_end)` — `manuscript.py:11`

### Engine

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| Deduplicator | `engine/deduplicator.py:6` | 56 | Sweep-line algorithm, SSOT for all validators, preserves findings by rule_id |
| Formatter | `engine/formatter.py:7` | 106 | format_json(), format_terminal(), format_gate_result() — 4 output formats |
| Loader | `engine/loader.py` | — | YAML rules/checklists loading |

---

## 15. Zotero y Bibliografía

### Zotero Client Modes

`clients/zotero.py` — 3-mode operation:

| Mode | When | API |
|------|------|-----|
| cloud | Default | Zotero Web API v3 |
| local | BBT local endpoint | Better BibTeX HTTP API |
| BBT | --bbt-local flag | Better BibTeX local endpoint |

### Importers

| Importer | File | Lines | Key Behavior |
|----------|------|-------|-------------|
| ZoteroImporter | `integrations/tools/zotero_import.py` | ~400 | Brace-depth-aware BibTeX parser, incremental merge, existing-entry detection |
| ZoteroSyncImporter | `integrations/tools/zotero_sync.py` | ~300 | API sync with since_version, optimistic concurrency, rate limiting, 429 handling |

**BibTeX parsing:** Brace-counting for nested braces (e.g., `{A {Bold} New Approach}`), field-level merge, duplicate detection by cite_key.

---

## 16. Templates, Estilos y Presets

### Journal Presets

Located in `templates/journals/`:

| Preset | Path | Contents |
|--------|------|----------|
| Nature | templates/journals/nature/ | preset.yaml, template.qmd, references.bib |
| Elsevier | templates/journals/elsevier/ | preset.yaml, template.qmd, references.bib |
| Springer | templates/journals/springer/ | preset.yaml, template.qmd, references.bib |

### Templates

| Template | Path | Purpose |
|----------|------|---------|
| manuscript.qmd | templates/manuscript.qmd | Quarto manuscript template |
| references.bib | templates/references.bib | Default bibliography |
| preset.yaml | templates/preset.yaml | Default preset config |

### CSL Styles

Located in `styles/csl/`:

| Style | File |
|-------|------|
| APA | styles/csl/apa.csl |
| Vancouver | styles/csl/vancouver.csl |

### Vale Rules

Located in `styles/vale/paper-writer/`:

| Rule | File | Purpose |
|------|------|---------|
| ForbiddenPhrases | ForbiddenPhrases.yml | Ban overused AI phrases |
| InformalLanguage | InformalLanguage.yml | Enforce formal register |
| StrongClaims | StrongClaims.yml | Flag overclaiming |
| UnbackedClaims | UnbackedClaims.yml | Flag unsupported assertions |

---

## 17. Plataforma y Operaciones

### Makefile Targets

`Makefile:1-41`:

| Target | Command | Purpose |
|--------|---------|---------|
| init | uv venv + pip install -e . + dev deps | Setup dev environment |
| test | .venv/bin/pytest | Run tests |
| lint | ruff check + ruff format --check | Lint + format check |
| typecheck | mypy harness/ cli/ validators/ ... | Type checking (explicit package list) |
| verify | lint + typecheck + test | Full verification |
| validate | python verification/run_real_validation.py | Real-material validation (local-only) |
| setup-github | ./scripts/setup-github.sh | One-time GitHub bootstrap |
| setup-github-checks | CHECKS_SHA=<sha> make setup-github-checks | Enforce required checks |

### pyproject.toml

`pyproject.toml:1-117`:

- **Name:** paper-writer, **Version:** 0.1.0
- **Python:** >=3.10
- **Dependencies:** mcp[cli]>=1,<2, pyyaml>=6.0.1, pyzotero>=1.13.1
- **Dev deps:** pytest>=8.0.0, ruff>=0.3.0, mypy>=1.9.0, types-pyyaml, pytest-cov
- **Entry point:** `paper = "cli.paper.main:main"`
- **Ruff:** line-length=100, excludes _scratch/, tools/, sub-projects
- **Mypy:** strict mode, explicit package list (NEVER `mypy .`)

### CI/CD Pipeline

`.github/workflows/ci.yml:1-199` — 5 jobs:

| Job | Purpose | Dependencies |
|-----|---------|-------------|
| quality | Ruff (root + scripts + thesaurus + mesh-import) + mypy | — |
| tests-core | pytest (3.10, 3.12, 3.13 matrix) | — |
| local-skills | thesaurus tests + mesh-import tests | — |
| offline-e2e | E2E tests with Pandoc | quality + tests-core + local-skills |
| build-smoke | Build wheel + install + asset verification | all above |

**Security:** `.github/workflows/security.yml` — pip-audit, CodeQL, dependency-review.
**Release:** `.github/workflows/release.yml` — tag-based (v*.*.*), wheel verification.
**Live smoke:** `.github/workflows/live-smoke.yml` — manual-only Zotero tests.

---

## 18. Hechos Confirmados y Brechas

### 18a. Hypotheses Verified

| ID | Hypothesis | Evidence | Status |
|----|-----------|----------|--------|
| H1 | Orchestrator uses 3-phase execute() | `orchestrator.py:104` — PREPARE/APPLY/VERIFY phases | **VERIFIED** |
| H2 | State machine is forward-only with domain enforcement | `state.py:149-182` — transition_to() checks target_idx > current_idx | **VERIFIED** |
| H3 | 13 required gates + 2 soft gates | `state.py:44-67` — REQUIRED_GATES (frozenset of 13) + SOFT_GATES (2) | **VERIFIED** |
| H4 | Gate verification uses fail-closed pattern | `orchestrator.py:556-614` — _run_wrapper_gate() fails if no wrapper registered | **VERIFIED** |
| H5 | State persistence is atomic | `yaml_repository.py:48-72` — .tmp + rename pattern | **VERIFIED** |
| H6 | PIPELINE_MAP has 16 explicit entries | `dispatch.py:192-221` — 16 dict entries, no implicit defaults | **VERIFIED** |
| H7 | 14 tool wrappers registered in builder | `orchestrator_builder.py:99-114` — 14 entries in wrappers dict | **VERIFIED** |

### 18b. Brechas Priorizadas

| Priority | Breach | Impact | Evidence |
|----------|--------|--------|----------|
| **P0** | No structured state query for external agents | Agents cannot programmatically read pipeline status | OrchestratorResult is transient, state.yaml requires YAML parsing |
| **P1** | No preflight check command | Users cannot validate readiness before executing | No `paper preflight` in PIPELINE_MAP or Phase 0 |
| **P1** | No artifact listing command | No way to enumerate what artifacts exist | No `paper artifacts` command |
| **P2** | MCP exposure gap | Paper Writer cannot be consumed as MCP server | Not an MCP server, no tool definitions |
| **P2** | No resume/continue command | Must re-run full pipeline from start | No `paper continue` command |

### 18c. Decisiones Arquitectónicas

| # | Decision | Rationale | Tradeoff |
|---|---------|-----------|----------|
| D1 | Hexagonal architecture with ports/adapters | Testability, swappable implementations | More files, more indirection |
| D2 | Forward-only state machine | Prevents invalid state regressions | Cannot undo; must reset_downstream_gates() |
| D3 | Fail-closed gate enforcement | Safety: unknown tools = failure, not silent pass | May block when tools are legitimately unavailable |
| D4 | Atomic YAML persistence | Prevents corrupted state files | Slight performance cost from .tmp + rename |
| D5 | PIPELINE_MAP declarative dispatch | Testable, explicit routing, no implicit defaults | More code than if/elif chain |

### 18d. Preguntas Abiertas

| ID | Question | Impact | Recommendation |
|----|----------|--------|----------------|
| Q1 | Should the preflight resolver be a new service or extend Orchestrator? | Affects coupling and testability | New read-only service (Orchestrator is 696 lines already) |
| Q2 | Should MCP exposure use FastMCP or raw JSON-RPC? | Affects deployment complexity | FastMCP (already a dependency via mcp[cli]) |
| Q3 | Should artifact listing be a separate command or flag on existing commands? | Affects CLI surface area | Separate command (`paper artifacts`) for discoverability |
| Q4 | Should the state query include gate verdict details or just gate booleans? | Affects information density | Include verdict tier + annotation for P0/P1 gates |
| Q5 | Should preflight be blocking (exit 1) or advisory (exit 0 + warnings)? | Affects CI integration | Advisory by default, `--strict` flag for blocking |

---

## Sources

1. **Exploration delegation 1:** CLI + dispatch + parser — `cli/paper/` full inventory
2. **Exploration delegation 2:** Harness core — `harness/domain/`, `harness/ports/`, `harness/adapters/`, `harness/services/`
3. **Exploration delegation 3:** Integrations + validators + engine — `integrations/tools/`, `validators/`, `engine/`, `parsers/`
4. **Exploration delegation 4:** Skills + templates + platform — `skills/`, `templates/`, `styles/`, `.github/`, `Makefile`, `pyproject.toml`

**All file paths and line numbers verified against codebase on 2026-06-19.**
