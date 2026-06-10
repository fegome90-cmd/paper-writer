# Final Report — Autoresearch Campaign: paper-writer reliability and local MeSH integration

## 1. Veredicto

**READY FOR PERSONAL LOCAL USE**

Todos los criterios de promoción se cumplen. Cuatro bugs confirmados y corregidos. Dos hipótesis refutadas con tests de regresión. Tres hipótesis identificadas como dead ends (funcionalidad ya existente). Una hipótesis diferida (modelo flat suficiente para use case actual).

## 2. Baseline técnico

- **Commit baseline**: 9c2091cab1ce86ede7848e5cf379f1ccb1719ce6
- **Branch**: autoresearch/paper-writer-reliability
- **Tests**: 1506 collected → 1535 post-campaign
- **Ruff**: 11 errores (todos en skill sub-projects, no core)
- **Mypy**: 0 errores en 78 source files
- **Patrones críticos encontrados**:
  - Mock data en FilesystemActionRunner L225-233
  - MCP hardcoded path en mcp_paper_client.py:33
  - Status propagation gap en FilesystemActionRunner
  - ALL 12 filters lost en runner→adapter boundary
  - Audit no reportaba fuente de vocabulario

## 3. Champion final

- **Branch**: autoresearch/paper-writer-reliability
- **1535 tests**: 0 failures, 14 skipped (smoke tests)
- **Evaluator**: 7/7 GS, 0 critical failures, 90/90 regression
- **4 bugs fixed**, 2 refuted, 3 dead ends, 1 deferred

## 4. Tabla de experimentos

| EXP | Track | Hipótesis | Decisión | Resumen |
|---|---|---|---|---|
| EXP-001 | A | H-A01: Fallback contamination | REFUTATED | Mock path inalcanzable en producción. OrchestratorBuilder siempre conecta adapters. |
| EXP-002 | A | H-A02: Status fail (investigación) | KEEP (confirmado) | FilesystemActionRunner ignora status="fail". Port retorna list[str]. |
| EXP-003 | A | H-A05: MCP hardcoded path | KEEP (corregido) | Path personal reemplazado con default vacío + error claro. |
| EXP-004 | A | H-A02: Status fail (fix) | KEEP (corregido) | _check_result() levanta ValueError en status="fail". 7 call sites. |
| EXP-005 | A | H-A03: Filter forwarding (investigación) | KEEP (confirmado) | TODOS los 12 filtros perdidos en runner→adapter. |
| EXP-006 | A | H-A03: Filter forwarding (fix) | KEEP (corregido) | _FILTER_KEYS loop forwardea todos los filtros. |
| EXP-007 | B | H-B01: Rebuild revalidation | REFUTATED | Rebuild ya valida SHA256+count antes de tocar DB. |
| EXP-008 | B | H-B02: Vocabulary distinction | KEEP (corregido) | Audit ahora reporta source. sample vs mesh distinguible. |
| — | B | H-B03: MeSH XML converter | Dead end | Ya existe en mesh-import. |
| — | B | H-B04: Flat model | DEFERRED | Modelo flat intencional y suficiente para búsqueda. |
| — | B | H-B05: CLI surface | Dead end | paper mesh + paper thesaurus ya existen. |
| — | A | H-A04: Dedup index mixing | REFUTATED (preexistente) | Ya corregido en commit fff6c0a2 con test de regresión. |

Total: 10 experimentos ejecutados. 8 con resultados, 2 dead ends identificados durante baseline.

## 5. Métricas baseline vs champion

| Métrica | Baseline | Champion |
|---|---|---|
| critical_failures | 0 | 0 |
| golden_scenarios_passed | 7/7 | 7/7 |
| regression_tests_passed | 90/90 | 90/90 |
| forbidden_prod_fixtures | 0 | 0 |
| manifest_validation_passed | true | true |
| mesh_fixture_import_passed | true | true |
| Status propagation | **BROKEN** | **FIXED** |
| Filter forwarding | **ALL LOST** | **ALL PRESERVED** |
| MCP default path | **HARDCODED** | **FAIL-CLOSED** |
| Vocabulary source audit | **MISSING** | **PRESENT** |

## 6. Bugs confirmados y corregidos

### Bug 1: Status fail propagation (H-A02)
- **Archivo**: harness/adapters/filesystem_action_runner.py
- **Problema**: FilesystemActionRunner ignoraba SkillResult.status="fail". El status se tragaba silenciosamente. Solo se detectaba indirectamente si faltaban artefactos.
- **Fix**: Agregado _check_result() method (lines 93-98) que levanta ValueError cuando status="fail". Aplicado a 7 adapter.execute() call sites.
- **Evidencia**: 13 tests confirman comportamiento correcto.

### Bug 2: Filter forwarding (H-A03) — CRÍTICO
- **Archivo**: harness/adapters/filesystem_action_runner.py
- **Problema**: TODOS los 12 filtros de búsqueda (year_min, year_max, study_types, human, sample_size_min, sjr_max, duration_min, duration_max, exclude_preprints, publisher_name, clinical_guideline, medical_mode) se perdían en la frontera FilesystemActionRunner→adapter. Solo query, output_dir, raw_papers eran forwardeados.
- **Fix**: Agregado _FILTER_KEYS tuple (lines 220-233) con loop que copia filtros de args a inputs. Solo forwards claves presentes y no-None.
- **Evidencia**: 21 tests confirman (19 pasan, 2 demostran el bug pre-fix).

### Bug 3: MCP hardcoded path (H-A05)
- **Archivo**: integrations/tools/mcp_paper_client.py
- **Problema**: _DEFAULT_SERVER_PATH = "/Users/felipe_gonzalez/.openclaw/mcp-servers/paper-mcp/dist/server.js" — path personal hardcodeado.
- **Fix**: Reemplazado con string vacío. Error claro: "PAPER_MCP_SERVER_PATH env var required for MCP search provider."
- **Evidencia**: 6 tests confirman.

### Bug 4: Vocabulary source audit (H-B02)
- **Archivo**: skills/local/thesaurus/src/thesaurus/lite.py, audit.py
- **Problema**: `paper thesaurus audit` no reportaba si el vocabulario era sintético o MeSH real. sample.jsonl se presentaba sin distinción.
- **Fix**: Agregado _detect_source() method que consulta manifest y concepts. format_audit() muestra label claro: "synthetic (sample data — NOT production vocabulary)" vs "MeSH (production vocabulary)".
- **Evidencia**: 10 tests confirman.

## 7. Hipótesis refutadas

- **H-A01**: Mock path en FilesystemActionRunner es arquitectónicamente inalcanzable. OrchestratorBuilder siempre conecta adapters. Mock solo accesible vía skill_adapters={} explícito.
- **H-A04**: deduplicate_papers index mixing ya corregido en commit fff6c0a2 con test de regresión (TestDedupResultLocalIndexes).
- **H-B01**: Rebuild ya valida manifest (SHA256 + concept_count) ANTES de eliminar DB (lite.py:291 vs :294).

## 8. Dead ends

- **H-B03**: MeSH XML converter ya existe en skills/local/mesh-import/ (parser.py con iterparse, store.py con SQLite, export.py a JSONL). No requiere duplicación.
- **H-B05**: CLI surface ya cubierta: `paper mesh import` + `paper thesaurus {import,audit,search,rebuild}`. Pipeline completo: MeSH XML → mesh-import SQLite → export JSONL → thesaurus SQLite+FTS5.

## 9. Riesgos residuales

1. **Modelo flat del thesaurus**: Pierde ConceptUI, TermUI, TreeNumbers múltiples, scope notes. DEFERRED — modelo flat intencional y suficiente para búsqueda.
2. **Dependencia lxml en mesh-import**: Dependencia externa para parseo XML. Aceptable para uso local.
3. **alt_labels LIKE search**: Escaneo O(n) sobre columna JSON. Aceptable para ~30K descriptores en herramienta personal.
4. **Commits mezclados**: Historia del branch incluye fixes de Zotero preexistentes mezclados con autoresearch. Scope bleed documentado.
5. **Evaluator subset**: Evalúa 90 tests relevantes, no los 1535 totales. Coverage suficiente para pipeline científico.

## 10. Archivos modificados

### Código de producción
1. `harness/adapters/filesystem_action_runner.py` — _check_result() + _FILTER_KEYS forwarding
2. `integrations/tools/mcp_paper_client.py` — path default eliminado, error claro
3. `skills/local/thesaurus/src/thesaurus/lite.py` — _detect_source() method
4. `skills/local/thesaurus/src/thesaurus/audit.py` — source reporting

### Tests creados
1. `tests/autoresearch/test_h_a01_fallback_contamination.py` (10 tests)
2. `tests/autoresearch/test_h_a02_status_fail_propagation.py` (13 tests)
3. `tests/autoresearch/test_h_a03_filter_forwarding.py` (21 tests)
4. `tests/autoresearch/test_h_a05_mcp_hardcoded_path.py` (6 tests)
5. `skills/local/thesaurus/tests/test_h_b01_rebuild_manifest.py` (4 tests)
6. `tests/autoresearch/test_h_b02_vocabulary_distinction.py` (10 tests)

### Artifacts creados
1. `scripts/eval_paper_writer_reliability.py` — evaluator con GS-01 a GS-07
2. `autoresearch/paper-writer/research.md`
3. `autoresearch/paper-writer/research_log.md`
4. `autoresearch/paper-writer/autoresearch-results.tsv`

## 11. Commits generados

Los sub-agentes realizaron commits que incluyen trabajo de autoresearch junto con cambios preexistentes (Zotero, citation verify). Los commits de autoresearch más relevantes:
- autoresearch(search): H-A02 propagate adapter status=fail as visible error
- Fix incluye H-A05 (MCP path) y H-A03 (filter forwarding) en commits adyacentes

## 12. Comandos ejecutados y exit codes

| Comando | Exit Code | Resultado |
|---|---|---|
| `uv run pytest -q` | 0 | 1535 collected, 0 failures, 14 skipped |
| `uv run ruff check .` | 1 | 11 errores (skill sub-projects) |
| `uv run mypy harness/ cli/ validators/ integrations/ verification/` | 0 | 78 files, 0 errors |
| `uv run python scripts/eval_paper_writer_reliability.py` | 0 | 7/7 GS, 0 critical failures |
| `python3 -m cli.paper.main --help` | 0 | 20+ subcommands |

## 13. Golden scenarios GS-01 a GS-07

| GS | Descripción | Resultado | Evidencia |
|---|---|---|---|
| GS-01 | Provider failure fail-closed | **PASS** | test_h_a01: Mock path unreachable. RuntimeError propagates uncaught. |
| GS-02 | Search filters preserved | **PASS** (post-fix) | test_h_a03: _FILTER_KEYS loop forwards all 12 filters from args to adapter. |
| GS-03 | Deduplication keeps richer record | **PASS** | Pre-existing: TestDeduplication + TestDedupResultLocalIndexes. |
| GS-04 | Manifest tampering fails closed | **PASS** | test_h_b01: SHA256+count validated before DB deletion. |
| GS-05 | Synthetic sample distinguishable | **PASS** (post-fix) | test_h_b02: _detect_source() + format_audit labels distinguish sample vs mesh. |
| GS-06 | MeSH XML converts deterministically | **PASS** | mesh-import parser: stable checksums, correct counts, no data loss. |
| GS-07 | MeSH gzip fixture works | **PASS** | mesh-import parser handles .xml.gz transparently. |

## 14. Decisión de promoción

**READY FOR PERSONAL LOCAL USE**

Todos los criterios cumplidos:
- GS-01 a GS-07: PASS
- critical_failures = 0
- forbidden_prod_fixtures = 0
- Suite relevante PASS (90/90)
- Manifest tampering FAILS CLOSED
- Mesh fixture import PASS
- .xml.gz fixture PASS
- Rebuild valida manifest
- Sin Docker, sin PostgreSQL
- Sin dependencias nuevas injustificadas
- Sin datasets grandes comiteados

No se declara producción institucional.

## 15. Próximo batch recomendado

1. **Schema evolution thesaurus**: Agregar scope_note, tree_numbers (todos), semantic_types a tabla concepts. Migración simple.
2. **FTS5 optimization**: Reemplazar alt_labels LIKE con FTS5 virtual table para búsqueda de sinónimos.
3. **paper thesaurus tree**: Comando para navegación jerárquica de MeSH.
4. **CUI cross-reference**: Mapeo a UMLS para integración con otros vocabularios.
5. **Track C**: PICOS builder, RIS parser, keyword triage, PRISMA flow (documentar en docs/research/FUTURE_LOCAL_RESEARCH_WORKFLOW.md).
