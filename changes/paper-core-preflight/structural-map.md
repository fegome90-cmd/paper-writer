# Structural Map — Paper Writer Repository

> Generated from codebase exploration on 2026-06-19.

## Directory → Capability Mapping

### `harness/` — Core Pipeline Engine

| Directory | Key Files | Capability |
|-----------|-----------|------------|
| `harness/domain/` | `state.py` | State machine: `ManuscriptState` with 8 pipeline stages, 13 required gates, 2 soft gates, forward-only transitions, and `reset_downstream_gates` cascade logic. |
| `harness/ports/` | `action_runner.py`, `artifact_checker.py`, `paper_search_provider.py`, `skill_adapter.py`, `state_repository.py`, `tool_resolver.py`, `tool_wrapper.py`, `assets.py` | 7 abstract interfaces + 1 asset resolution port. Decouples orchestrator from infrastructure. |
| `harness/adapters/` | `filesystem_action_runner.py`, `yaml_repository.py`, `filesystem_artifact_checker.py`, `local_tool_resolver.py` | Concrete filesystem implementations of all 4 internal ports. Action runner handles run_id lineage, `outputs/latest` symlink, and run.yaml metadata. |
| `harness/services/` | `orchestrator.py`, `state_manager.py`, `gates.py`, `doctor.py`, `assembler.py`, `verify_artifacts.py`, `review_config.py`, `orchestrator_builder.py` | Orchestrator (3-phase: prepare → apply → verify), 11 gate validators, doctor environment checks, manuscript assembler, 4 verify artifacts generator, review config loader, and dependency builder. |

### `cli/paper/` — CLI Layer

| File | Capability |
|------|------------|
| `main.py` | Entrypoint + single error boundary. Translates exceptions to exit codes (0/1/2/3/130). |
| `parser.py` | argparse construction: 16 pipeline commands, 9 zotero subcommands, 5 thesaurus subcommands, 4 mesh subcommands, 9 audit subcommands, 2 graph commands, 1 gate command, 1 doctor command. |
| `dispatch.py` | Declarative `PIPELINE_MAP` (16 entries) + Phase 0 callback routing. Orchestrator wiring and summary rendering. |
| `output.py` | Output contract: text/json formatting, `emit_result`, `emit_json`, `emit_error`, `emit_warning`, `emit_info`. |
| `errors.py` | `UserInputError` (exit 2), `ExternalServiceError` (exit 3). |
| `project.py` | `resolve_project_root()` with ancestor-walking heuristic. |
| `runtime.py` | `configure_logging()`, `temporary_sigint_handler()` for clean Ctrl+C. |
| `commands/audit.py` | 9 audit handlers: prose, claims, citations, ethics, writing-quality, factuality, tables, code-health, quality-appraisal. |
| `commands/zotero.py` | 8 Zotero CRUD handlers: collections, search, get, create, template, update, delete, upload. |
| `commands/thesaurus.py` | 5 thesaurus handlers: import, search, list, audit, rebuild. Graceful degradation. |
| `commands/mesh.py` | 4 MeSH handlers: import, resolve, expand, export. Graceful degradation. |
| `commands/doctor.py` | Environment checker with `--live` and `--live-search-probe` modes. |
| `commands/gate.py` | Methodological gate: EQUATOR-derived checklists (CONSORT, STROBE, PRISMA). |
| `commands/graph.py` | Trifecta graph: `trace` (callers/callees/path) and `graph-overview`. |

### `validators/` — 23 Validators

| Validator | Domain |
|-----------|--------|
| `academic_evidence.py` | Academic evidence quality |
| `bibliography.py` | BibTeX structure |
| `citation_format.py` | Citation formatting |
| `citation_verify.py` | Crossref + Semantic Scholar verification |
| `citations.py` | Inline citation checks |
| `claim_alignment.py` | Claim-evidence alignment |
| `claim_evidence.py` | Claim-evidence overlap (factuality) |
| `claims.py` | Claim candidate detection |
| `code_health.py` | Dead code / orphan detection via Trifecta |
| `contamination_signals.py` | Data contamination detection |
| `ethics.py` | AI disclosure compliance |
| `gate_verdict.py` | 3-class verdict: TIER_NONE / TIER_LOW_WARN / TIER_HIGH_WARN |
| `method_gate.py` | EQUATOR checklists (CONSORT, STROBE, PRISMA, generic) |
| `preset.py` | Journal preset validation |
| `prose.py` | Scientific prose quality (hedging, nominalization, weasel, etc.) |
| `protocol_generator.py` | Reproducibility protocol generation |
| `quality_appraisal.py` | 5-dimension study scoring |
| `refs.py` | Reference consistency |
| `reporting.py` | Reporting checklist compliance |
| `structure.py` | Manuscript structure validation |
| `style.py` | Style rules |
| `table_figure.py` | Table/figure presence in drafts |
| `writing_quality.py` | AI-typical writing pattern detection |

### `integrations/tools/` — 15 Tool Wrappers + 2 MCP Clients + 1 Search Provider

#### Tool Wrappers (15)

| Wrapper | Gate | Tool |
|---------|------|------|
| `BibliographyNormalizer` | `bib_imported` | bibtex-tidy |
| `RefsValidator` | `citations_resolved` | Inline |
| `RefsMetadataValidator` | `refs_validated` | Crossref API |
| `StyleLinter` | `style_passed` | Vale |
| `StyleAuditToolWrapper` | `style_passed` | Inline |
| `ReportingAuditor` | `reporting_passed` | Inline |
| `EthicsAuditor` | `ethics_passed` | Inline |
| `ProseAuditor` | `style_passed` | Inline |
| `ClaimsAuditor` | `style_passed` | Inline |
| `CitationsAuditor` | `citations_resolved` | Crossref + S2 |
| `WritingQualityAuditor` | `style_passed` | Inline |
| `CodeHealthAuditor` | `style_passed` | Trifecta MCP |
| `PandocRenderer` | `render_passed` | Pandoc + tectonic |
| `ZoteroImporter` | `bib_imported` | Zotero API |
| `ZoteroSyncImporter` | `bib_imported` | Zotero API |

#### MCP Clients (2)

| Client | Service |
|--------|---------|
| `ConsensusClient` | Consensus API |
| `ConsensusMcpClient` | Consensus MCP |

#### Search Providers (1)

| Provider | Service |
|----------|---------|
| `McpPaperSearchProvider` | paper-mcp server |

### `clients/` — 9 HTTP Clients

| Client | Service |
|--------|---------|
| `arxiv.py` | arXiv API |
| `crossref.py` | Crossref REST API |
| `llm_content.py` | LLM content generation |
| `openalex.py` | OpenAlex API |
| `semantic_scholar.py` | Semantic Scholar API |
| `trifecta.py` | Trifecta MCP client |
| `zotero.py` | Zotero Cloud + Local API |
| `_retry.py` | Retry/backoff utilities |
| `_text_similarity.py` | Text similarity helpers |

### `skills/` — Domain Skills

| Directory | Capability |
|-----------|------------|
| `skills/imported/literature_search/` | Literature search + screening adapter |
| `skills/imported/academic_writer/` | Academic writing adapter |
| `skills/local/thesaurus/` | Biomedical concept normalization (MeSH/DeCS) — separate package |
| `skills/local/mesh-import/` | MeSH vocabulary import — separate package |
| `skills/local/trifecta-mcp/` | Trifecta code graph MCP integration |
| `skills/local/science-bundle/` | Science utility bundle |
| `skills/local/essay_crafter/` | Essay crafting skill |
| `skills/local/workflow_skill_creator/` | Skill creation workflow |

### `engine/` — Processing Engine

| File | Capability |
|------|------------|
| `deduplicator.py` | Paper deduplication (DOI, PMID, title similarity) |
| `formatter.py` | Terminal/claims/gate result formatting |
| `loader.py` | Data loading utilities |

### `parsers/` — Input Parsers

| File | Capability |
|------|------------|
| `manuscript.py` | Parse .md/.tex/.txt manuscripts into structured sections |
| `source_map.py` | Source mapping for citation provenance |

### `rules/` — 6 Rule Modules (24 YAML files)

| Module | Files | Purpose |
|--------|-------|---------|
| `citations/` | `crossref_verification.yml`, `semantic_scholar_verification.yml` | Citation verification rules |
| `claims/` | `causal.yml`, `comparative.yml`, `descriptive.yml`, `prescriptive.yml`, `risk_by_section.yml` | Claim detection rules |
| `ethics/` | `ai_disclosure.yml` | AI disclosure compliance |
| `method_gate/` | `consort.yml`, `generic.yml`, `prisma.yml`, `strobe.yml` | EQUATOR checklist rules |
| `prose/` | `causal_language.yml`, `hedging.yml`, `nominalization.yml`, `overclaim.yml`, `unsupported_certainty.yml`, `vague_quantifiers.yml`, `weasel.yml` | Prose quality rules |
| `writing_quality/` | `ai_typical_terms.yml` | AI writing pattern detection |

### `schemas/` — 5 JSON Schemas

| File | Purpose |
|------|---------|
| `claim_audit.schema.json` | Claim audit output validation |
| `finding.schema.json` | Finding structure validation |
| `method_gate.schema.json` | Method gate output validation |
| `preflight.schema.json` | PreflightResult v1 output validation |
| `prose_audit.schema.json` | Prose audit output validation |

### `templates/` — Journal Presets & Manuscript Template

| Path | Purpose |
|------|---------|
| `templates/journals/nature/` | Nature journal preset |
| `templates/journals/elsevier/` | Elsevier journal preset |
| `templates/journals/springer/` | Springer journal preset |
| `templates/manuscript.qmd` | Default Quarto manuscript template |
| `templates/references.bib` | Default BibTeX template |
| `templates/preset.yaml` | Default preset configuration |

### `styles/` — Formatting Rules

| Directory | Contents |
|-----------|----------|
| `styles/csl/` | `vancouver.csl`, `apa.csl` — citation style language files |
| `styles/vale/` | `.vale.ini` + `paper-writer/` style pack — prose linting rules |

### `verification/` — Real-Material Validation

| Path | Purpose |
|------|---------|
| `verification/local-data/` | Local validation test cases |
| `verification/run_real_validation.py` | Real-material validation runner |
| `verification/reports/` | Validation reports |
| `verification/manifest.example.yaml` | Example manifest |

### `benchmarks/` — Performance Benchmarks

| Path | Purpose |
|------|---------|
| `benchmarks/fair/` | FAIR principles benchmark (arms, fixtures, reports, runner) |
| `benchmarks/trifecta_integration_bench.py` | Trifecta integration benchmark |

### `autoresearch/` — Research Logs

| Path | Purpose |
|------|---------|
| `autoresearch/paper-writer/` | Autoresearch output logs |

### `outputs/` — Runtime Artifacts

| Path | Purpose |
|------|---------|
| `outputs/state.yaml` | Pipeline state (current stage + gates) |
| `outputs/manifest.yaml` | Final delivery manifest |
| `outputs/review_config.yaml` | Review mode configuration (tracked) |
| `outputs/latest` | Symlink → current run directory |
| `outputs/runs/{run_id}/` | Per-run artifacts: search/, drafts/, render/, verify/, logs/, run.yaml |
| `outputs/.run_id` | Current run identifier |

### `tests/` — Test Suite

| Metric | Count |
|--------|-------|
| Total tests | ~1903 |
| Core tests | `harness/`, `cli/`, `validators/`, `engine/`, `parsers/`, `rules/`, `schemas/` |
| E2E tests | `@pytest.mark.e2e` — Pandoc/render tests |
| Integration tests | `@pytest.mark.integration` — Real adapter tests |

### `.github/workflows/` — CI/CD

| Workflow | Purpose |
|----------|---------|
| `ci.yml` | 7-job pipeline: quality, tests-core (3.10/3.12/3.13), local-skills, offline-e2e, build-smoke |
| `release.yml` | Tag-based release (`v*.*.*`) with wheel verification |
| `security.yml` | dependency-audit, CodeQL, dependency-review |
| `live-smoke.yml` | Manual-only Zotero live tests |

---

## Layer Classification

| Layer | Count | Purpose |
|-------|-------|---------|
| **CLI** | 8 files | User-facing entrypoint, argument parsing, output formatting |
| **Domain** | 1 file | Pure business logic — state machine, no infrastructure |
| **Ports** | 7 interfaces | Abstract contracts decoupling domain from infrastructure |
| **Adapters** | 4 implementations | Filesystem-based concrete adapters |
| **Services** | 8 modules | Orchestrator, gates, assembler, doctor, verify, config, builder |
| **Validators** | 23 validators | Input validation, quality checks, compliance gates |
| **Tool Wrappers** | 14 wrappers (registered in OrchestratorBuilder) | External tool integration (Pandoc, Vale, bibtex-tidy, etc.) |
| **Clients** | 9 HTTP clients | External API integrations (Crossref, S2, Zotero, etc.) |
| **Skills** | 8 skills | Domain-specific capabilities (search, writing, thesaurus, MeSH) |
| **Engine** | 3 modules | Deduplication, formatting, data loading |
| **Parsers** | 2 parsers | Manuscript and source map parsing |
| **Rules** | 6 modules (24 YAML) | Declarative validation rules |
| **Schemas** | 5 schemas | JSON output validation |
| **Templates** | 3 presets + 1 template | Journal presets and manuscript template |
| **Styles** | 2 CSL + Vale pack | Citation and prose formatting rules |
| **Verification** | 1 runner | Real-material validation |
| **Benchmarks** | 2 suites | FAIR + Trifecta performance |
| **CI/CD** | 4 workflows | CI, release, security, live-smoke |
| **Tests** | ~1903 tests | Unit, integration, E2E coverage |
